"""filmgrain.py - deterministic temporal film grain, applied after denoising.

Cycles denoises inside the render, so grain has to go on afterwards or the
denoiser simply eats it. Blender 5.2's compositor has no film-grain node that
can be driven per-frame from Python without rebuilding a texture graph every
frame, so this runs over the finished frames instead - which the brief names
as the sanctioned alternative, and which has the advantage that every
parameter is inspectable and testable.

It runs as a stream filter between two ffmpeg processes:

    ffmpeg ... -f rawvideo -pix_fmt rgb24 - \
      | python filmgrain.py --width W --height H --sha <trajectory sha> \
      | ffmpeg -f rawvideo -pix_fmt rgb24 ...

so no second copy of the sequence ever lands on disk. Decoding the PNGs in
Python was the first design and it was thrown away: Blender writes adaptively
filtered PNGs, and undoing Paeth in a Python loop cost about 3 s a frame, or
half an hour for the film.

Three properties the brief asks for, and how each is met:

  * different on every frame - the RNG is seeded per frame from the frozen
    trajectory SHA-256, so frame 417 always gets the same grain and never the
    same grain as frame 416
  * fine in highlights, stronger in midtones and shadows - amplitude scales by
    (1 - HIGHLIGHT_ROLLOFF * luma), which is the way real emulsion behaves
  * mostly monochromatic - MONO_WEIGHT of the noise is one luminance channel
    shared across R, G and B, so it reads as grain and not as colour speckle
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys

import numpy as np

SIGMA = 0.0135              # midtone amplitude in 0..1 units (~3.4/255)
HIGHLIGHT_ROLLOFF = 0.72    # how much the highlights calm down
SHADOW_FLOOR = 0.30         # grain never drops below this fraction of SIGMA
MONO_WEIGHT = 0.85          # the remainder is independent per-channel chroma


def frame_seed(traj_sha, frame):
    """Stable per-frame seed derived from the take, never from the clock."""
    h = hashlib.sha256(("%s:%d" % (traj_sha, frame)).encode()).digest()
    return struct.unpack("<Q", h[:8])[0]


def apply(img, traj_sha, frame, sigma=SIGMA):
    """img: HxWx3 float32 in 0..1 -> same, grained. Pure function."""
    rng = np.random.default_rng(frame_seed(traj_sha, frame))
    luma = (0.2126 * img[..., 0] + 0.7152 * img[..., 1] + 0.0722 * img[..., 2])
    amp = 1.0 - HIGHLIGHT_ROLLOFF * luma
    np.clip(amp, SHADOW_FLOOR, 1.0, out=amp)
    mono = rng.standard_normal(luma.shape, dtype=np.float32)
    chroma = rng.standard_normal(img.shape, dtype=np.float32)
    noise = MONO_WEIGHT * mono[..., None] + (1.0 - MONO_WEIGHT) * chroma
    out = img + noise * (sigma * amp)[..., None]
    return np.clip(out, 0.0, 1.0, out=out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, required=True)
    ap.add_argument("--height", type=int, required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--sigma", type=float, default=SIGMA)
    ap.add_argument("--start-frame", type=int, default=0)
    ap.add_argument("--stats", default="")
    args = ap.parse_args()

    n = args.width * args.height * 3
    fin, fout = sys.stdin.buffer, sys.stdout.buffer
    frame = args.start_frame
    rows = []
    while True:
        buf = fin.read(n)
        if not buf or len(buf) < n:
            break
        img = (np.frombuffer(buf, dtype=np.uint8)
               .reshape(args.height, args.width, 3).astype(np.float32) / 255.0)
        before = float(img.mean())
        out = apply(img, args.sha, frame, args.sigma)
        rows.append((frame, before, float(out.mean()),
                     float(np.abs(out - img).mean())))
        fout.write((out * 255.0 + 0.5).astype(np.uint8).tobytes())
        frame += 1
    fout.flush()
    if args.stats:
        import json
        with open(args.stats, "w") as fh:
            json.dump(dict(frames=len(rows), sigma=args.sigma,
                           sha=args.sha,
                           mean_abs_delta=(sum(r[3] for r in rows) / len(rows)
                                           if rows else 0.0),
                           rows=[dict(frame=r[0], mean_in=round(r[1], 6),
                                      mean_out=round(r[2], 6),
                                      mean_abs_delta=round(r[3], 6))
                                 for r in rows]), fh)
    print("filmgrain: %d frames, sigma %.4f, mean |delta| %.5f"
          % (len(rows), args.sigma,
             sum(r[3] for r in rows) / len(rows) if rows else 0.0),
          file=sys.stderr)


if __name__ == "__main__":
    main()
