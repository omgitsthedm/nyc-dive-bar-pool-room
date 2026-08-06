"""109_publish_stills.py - cinematic stills -> site webps, with verification.

The render writes ``renders/cinematic_stills/NN-CAM_Name.png``; the site wants
``site/img/opening/NN-slug.webp``. Both carry the same two-digit index, so the
map is derived from the filenames already on disk rather than hand-listed -
a hand-listed map silently rots the first time a camera is renamed.

Refuses to run unless all 15 renders exist and every one maps to exactly one
existing site slug. A partial gallery is worse than none: the page would ship
a mix of new and stale frames with nothing to indicate which was which.

Run with the project venv python from the repo root.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RENDERS = ROOT / "renders" / "cinematic_stills"
SITE_IMG = ROOT / "site" / "img" / "opening"
CWEBP = "/opt/homebrew/bin/cwebp"
EXPECTED = 15


def index_of(name: str) -> str | None:
    m = re.match(r"^(\d{2})[-.]", name)
    return m.group(1) if m else None


def build_map() -> dict[Path, Path]:
    renders = {}
    for p in sorted(RENDERS.glob("*.png")):
        idx = index_of(p.name)
        if idx:
            renders.setdefault(idx, p)
    slugs = {}
    for p in sorted(SITE_IMG.glob("*.webp")):
        idx = index_of(p.name)
        if idx:
            slugs.setdefault(idx, p)

    missing_render = sorted(set(slugs) - set(renders))
    missing_slug = sorted(set(renders) - set(slugs))
    if len(renders) != EXPECTED:
        raise RuntimeError("expected %d renders, found %d (have: %s)"
                           % (EXPECTED, len(renders), ", ".join(sorted(renders))))
    if missing_render:
        raise RuntimeError("site slugs with no render: %s"
                           % ", ".join(missing_render))
    if missing_slug:
        raise RuntimeError("renders with no site slug: %s"
                           % ", ".join(missing_slug))
    return {renders[i]: slugs[i] for i in sorted(renders)}


def _decode(path: Path):
    """Minimal PNG reader - no Pillow in this venv, and the check matters more
    than the dependency. Returns (width, height, channels, raw bytes)."""
    import struct
    import zlib
    data = path.read_bytes()
    pos, idat = 8, b""
    w = h = bd = ct = 0
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", chunk[:10])
        elif typ == b"IDAT":
            idat += chunk
        pos += 12 + ln
    raw = zlib.decompress(idat)
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ct]
    bpp = ch * (bd // 8)
    stride = w * bpp
    out = bytearray()
    prev = bytearray(stride)
    i = 0
    for _ in range(h):
        f = raw[i]
        i += 1
        line = bytearray(raw[i:i + stride])
        i += stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out += line
        prev = line
    return w, h, bpp, bytes(out)


def check_not_black(path: Path, min_mean=0.02, max_black_fraction=0.90):
    """A1 requires every stills camera to render non-black with the volume on.

    A camera that ends up inside a volume box renders to pure black in some
    engines, and a black frame is easy to miss in a 15-image gallery until it
    is live. Sampled rather than exhaustive - enough to catch a dead frame
    without decoding 7 MB per image twice.
    """
    w, h, bpp, px = _decode(path)
    step = bpp * 37                       # sparse stride, prime-ish
    total = black = 0
    acc = 0.0
    for o in range(0, len(px) - bpp, step):
        y = 0.2126 * px[o] + 0.7152 * px[o + 1] + 0.0722 * px[o + 2]
        acc += y
        total += 1
        if y < 4:
            black += 1
    mean = acc / total / 255.0
    frac = black / total
    if mean < min_mean or frac > max_black_fraction:
        raise RuntimeError(
            "%s looks dead: mean luminance %.4f, %.1f%% near-black. A1 "
            "requires every stills camera to render non-black with the room "
            "haze enabled." % (path.name, mean, frac * 100))
    return mean, frac


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quality", type=int, default=82)
    ap.add_argument("--method", type=int, default=6)
    args = ap.parse_args()

    pairs = build_map()
    print("  [publish] A1 black-frame gate over %d renders" % len(pairs))
    for png in pairs:
        mean, frac = check_not_black(png)
        print("    %-46s meanY=%.4f  near-black=%.1f%%"
              % (png.name, mean, frac * 100))
    print("  [publish] %d renders -> %d site webps" % (len(pairs), len(pairs)))
    total_before = total_after = 0
    for png, webp in pairs.items():
        before = webp.stat().st_size if webp.exists() else 0
        proc = subprocess.run(
            [CWEBP, "-quiet", "-q", str(args.quality), "-m", str(args.method),
             str(png), "-o", str(webp)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            sys.stderr.write(proc.stdout + proc.stderr)
            raise RuntimeError("cwebp failed for %s" % png.name)
        after = webp.stat().st_size
        total_before += before
        total_after += after
        sha = hashlib.sha256(webp.read_bytes()).hexdigest()[:12]
        print("    %-46s -> %-24s %7.1f KB  %s"
              % (png.name, webp.name, after / 1024.0, sha))
    print("  [publish] gallery %.1f KB -> %.1f KB"
          % (total_before / 1024.0, total_after / 1024.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
