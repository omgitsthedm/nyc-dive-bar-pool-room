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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pngstats  # noqa: E402

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


def check_not_black(path: Path, min_mean=0.02, max_black_fraction=0.90):
    """A1 requires every stills camera to render non-black with the volume on.

    Uses the shared reader in pngstats.py. This function previously carried
    its own inline decoder that assumed 8 bits per channel. Blender writes
    16-bit PNGs, so that decoder read the high and low bytes of red as if
    they were red and green and reported confident nonsense - a pitch-black
    film passed a black-frame gate built on exactly this mistake. Any gate
    that measures a render must go through pngstats.
    """
    stats = pngstats.luminance_stats(path, stride_px=37)
    mean = stats["mean"]
    frac = stats["frac_below_0_05"]
    if mean < min_mean or frac > max_black_fraction:
        raise RuntimeError(
            "%s looks dead: mean luminance %.4f, %.1f%% near-black (%d-bit). "
            "A1 requires every stills camera to render non-black with the "
            "room haze enabled."
            % (path.name, mean, frac * 100, stats["bit_depth"]))
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
