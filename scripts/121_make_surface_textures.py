"""121_make_surface_textures.py - author the big flat surfaces properly.

The scene had 52 texture files and every one of them was a pool-ball decal.
Everything else - plaster, oak, brass, tin - was procedural noise, which is why
the wall behind the register reads as a brown smear rather than as a wall that
has had cigarettes smoked in front of it for forty years.

This writes tileable 2K maps (colour + roughness + a height field for bump) for
the surfaces that occupy the most pixels:

  plaster_tobacco : nicotine-stained plaster, patch repairs, hairline cracks,
                    a darker tide line where the wainscot used to be
  oak_stained     : quarter-sawn oak with real grain runout, ring figure,
                    dents and a worn sheen along the bar's leading edge
  tin_ceiling     : pressed-tin panel with a repeating relief and rust bloom

Deterministic from a seed. Runs in the project venv (Pillow + numpy), NOT in
Blender, whose bundled Python has no PIL.
"""
from __future__ import annotations

import argparse
import math
import os

import numpy as np
from PIL import Image

SIZE = 2048


def _rng(seed):
    return np.random.default_rng(seed)


def fbm(rng, size, octaves=7, lac=2.0, gain=0.5, base=4):
    """Tileable value-noise fBm via periodic lattice interpolation."""
    out = np.zeros((size, size), np.float32)
    amp, total = 1.0, 0.0
    res = base
    for _ in range(octaves):
        g = rng.random((res, res), dtype=np.float32)
        # wrap for tileability, then bilinear upsample to full size
        gg = np.concatenate([g, g[:1]], 0)
        gg = np.concatenate([gg, gg[:, :1]], 1)
        ys = np.linspace(0, res, size, endpoint=False, dtype=np.float32)
        xs = ys
        y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int)
        fy = (ys - y0)[:, None]; fx = (xs - x0)[None, :]
        fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)
        a = gg[y0][:, x0]; b = gg[y0][:, x0 + 1]
        c = gg[y0 + 1][:, x0]; d = gg[y0 + 1][:, x0 + 1]
        out += amp * ((a * (1 - fx) + b * fx) * (1 - fy) +
                      (c * (1 - fx) + d * fx) * fy)
        total += amp
        amp *= gain
        res = int(res * lac)
    return out / total


def norm(a):
    lo, hi = float(a.min()), float(a.max())
    return (a - lo) / (hi - lo + 1e-9)


def to_img(a):
    return Image.fromarray(np.clip(a * 255.0, 0, 255).astype(np.uint8))


def save_set(out, name, colour, rough, height):
    to_img(colour).save(os.path.join(out, "%s_col.png" % name))
    to_img(rough).save(os.path.join(out, "%s_rgh.png" % name))
    to_img(height).save(os.path.join(out, "%s_hgt.png" % name))
    print("  [tex] %s  colour/roughness/height @ %dpx" % (name, SIZE))


# ------------------------------------------------------------- plaster ------
def plaster_tobacco(seed, out):
    rng = _rng(seed)
    n = fbm(rng, SIZE, octaves=8, base=3)
    fine = fbm(rng, SIZE, octaves=5, base=48)

    # Nicotine does not stain evenly: it collects high and in still corners.
    yy = np.linspace(0.0, 1.0, SIZE, dtype=np.float32)[:, None]
    smoke = np.clip(0.45 + 0.75 * (1.0 - yy) + 0.35 * (n - 0.5), 0.0, 1.4)

    base = np.stack([
        0.62 * smoke + 0.10 * fine,
        0.52 * smoke + 0.09 * fine,
        0.38 * smoke + 0.07 * fine,
    ], -1)

    # Patch repairs: somebody filled holes and never repainted to match.
    patches = np.zeros((SIZE, SIZE), np.float32)
    for _ in range(14):
        cx, cy = rng.integers(0, SIZE, 2)
        r = int(rng.integers(60, 260))
        y, x = np.ogrid[:SIZE, :SIZE]
        d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        edge = 1.0 - np.clip((d - r * 0.7) / (r * 0.3), 0, 1)
        patches = np.maximum(patches, edge * float(rng.uniform(0.25, 0.55)))
    patches *= (0.6 + 0.8 * fine)
    base += patches[..., None] * np.array([0.20, 0.19, 0.17], np.float32)

    # Hairline cracks. The first pass thresholded a ridged field at 0.955 and
    # got a river delta drawn in marker pen: plaster cracks are one or two
    # pixels wide at 2K and they only run where the substrate has moved, not
    # across the whole wall. So: a much tighter threshold, and a coarse mask
    # so most of the wall has none at all.
    ridged = 1.0 - np.abs(fbm(rng, SIZE, octaves=7, base=9) * 2.0 - 1.0)
    where = np.clip(fbm(rng, SIZE, octaves=3, base=3) * 1.9 - 0.95, 0, 1)
    cracks = np.clip((ridged - 0.992) * 150.0, 0, 1) * where
    base -= cracks[..., None] * np.array([0.16, 0.15, 0.13], np.float32)

    # Tide line where a wainscot once was.
    band = np.exp(-((yy - 0.72) ** 2) / (2 * 0.012 ** 2))
    base -= band * 0.10

    colour = np.clip(base, 0.02, 1.0)
    rough = np.clip(0.70 + 0.22 * fine - 0.10 * cracks, 0.25, 0.98)
    height = np.clip(0.5 + 0.35 * (n - 0.5) + 0.30 * patches - 0.35 * cracks,
                     0, 1)
    save_set(out, "plaster_tobacco", colour, rough, height)


# ----------------------------------------------------------------- oak ------
def oak_stained(seed, out):
    rng = _rng(seed)
    x = np.linspace(0.0, 1.0, SIZE, dtype=np.float32)[None, :]
    y = np.linspace(0.0, 1.0, SIZE, dtype=np.float32)[:, None]
    wob = fbm(rng, SIZE, octaves=6, base=5) - 0.5
    # Growth rings. The first attempt used one fixed frequency and produced
    # corduroy. Real timber has rings that crowd and open out across the
    # board, a few knots that the grain sweeps around, and soft rays cutting
    # across - so the frequency is modulated by a low field, the bands are
    # wider, and knots warp the coordinate before the sine is taken.
    freq = 14.0 + 12.0 * fbm(rng, SIZE, octaves=3, base=3)
    warp = np.zeros((SIZE, SIZE), np.float32)
    for _ in range(5):
        kx, ky = rng.random(2)
        kr = float(rng.uniform(0.03, 0.075))
        d = np.sqrt((x - kx) ** 2 + (y - ky) ** 2) + 1e-4
        warp += np.clip(1.0 - d / (kr * 6.0), 0, 1) ** 2 * (kr / d) * 0.35
    phase = (x * freq + wob * 2.2 + warp * 6.0 + y * 0.35)
    rings = 0.5 + 0.5 * np.sin(phase * math.pi * 2.0)
    rings = rings ** 1.6                       # dark latewood, wide earlywood
    rays = np.clip(fbm(rng, SIZE, octaves=4, base=90) * 1.6 - 0.72, 0, 1)
    pore = fbm(rng, SIZE, octaves=4, base=120)
    figure = fbm(rng, SIZE, octaves=5, base=7)

    light = np.array([0.30, 0.185, 0.105], np.float32)
    dark = np.array([0.135, 0.078, 0.042], np.float32)
    t = np.clip(0.42 + 0.38 * rings + 0.28 * (figure - 0.5)
                + 0.10 * rays, 0, 1)[..., None]
    colour = dark + (light - dark) * t
    colour *= (0.92 + 0.14 * pore)[..., None]

    # Dents and scuffs, heavier along one edge - the side people lean on.
    wear = np.clip(fbm(rng, SIZE, octaves=6, base=9) * 1.4 - 0.55, 0, 1)
    edge = np.exp(-((y - 0.06) ** 2) / (2 * 0.05 ** 2))
    wear = np.clip(wear + edge * 0.5, 0, 1)
    colour = np.clip(colour * (1.0 - 0.22 * wear[..., None]), 0.01, 1.0)

    rough = np.clip(0.34 + 0.40 * wear + 0.12 * (1.0 - rings), 0.16, 0.92)
    height = np.clip(0.5 + 0.26 * (rings - 0.5) + 0.22 * (pore - 0.5)
                     - 0.20 * wear, 0, 1)
    save_set(out, "oak_stained", colour, rough, height)


# ------------------------------------------------------------------ tin -----
def tin_ceiling(seed, out):
    rng = _rng(seed)
    u = np.linspace(0, 1, SIZE, endpoint=False, dtype=np.float32)
    X, Y = np.meshgrid(u, u)
    # 4x4 pressed panels with a bordered rosette
    px, py = (X * 4.0) % 1.0, (Y * 4.0) % 1.0
    d = np.maximum(np.abs(px - 0.5), np.abs(py - 0.5))
    relief = (np.clip((0.46 - d) * 26, 0, 1) * 0.55 +
              np.clip((0.38 - d) * 26, 0, 1) * 0.25)
    r = np.sqrt((px - 0.5) ** 2 + (py - 0.5) ** 2)
    relief += np.clip(np.cos(r * math.pi * 11.0), 0, 1) * \
        np.clip((0.30 - r) * 12, 0, 1) * 0.45

    grime = fbm(rng, SIZE, octaves=7, base=5)
    rust = np.clip(fbm(rng, SIZE, octaves=6, base=14) * 1.5 - 0.72, 0, 1)

    paint = np.array([0.30, 0.295, 0.275], np.float32)
    colour = paint[None, None, :] * (0.72 + 0.46 * grime)[..., None]
    colour += relief[..., None] * 0.06
    colour = colour * (1 - rust[..., None]) + \
        rust[..., None] * np.array([0.34, 0.17, 0.08], np.float32)

    rough = np.clip(0.52 + 0.34 * grime + 0.30 * rust, 0.25, 0.97)
    height = np.clip(relief * 0.8 + 0.12 * grime, 0, 1)
    save_set(out, "tin_ceiling", np.clip(colour, 0.01, 1), rough, height)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", default="16b5aafa")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    base = int(args.seed[:8], 16)
    plaster_tobacco(base, args.out)
    oak_stained(base + 101, args.out)
    tin_ceiling(base + 202, args.out)
    print("  [tex] done -> %s" % args.out)


if __name__ == "__main__":
    raise SystemExit(main())
