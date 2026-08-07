"""119_make_bottle_labels.py - generate real artwork for the back-bar labels.

WHY THIS EXISTS. The back bar is 213 individually placed bottles, and every one
of them wore the same blank rectangle: MAT_Prop_Paper_Aged, procedural, no
artwork. A 200-sample render of that shelf is indistinguishable from an
8-sample render of it - measured, not assumed - because the thing missing was
never noise. It was type.

So this draws labels: a wordmark, a rule, a sub-line, a spirit class, a year,
and some small print, in real typefaces, on aged paper, with the edges dirtied
and the corners knocked about. Twenty-four of them, deterministic from a seed
so the shelf is identical on every rebuild.

Runs in the project venv (needs Pillow), NOT in Blender - Blender's bundled
Python has no PIL. It writes PNGs that 120_apply_bottle_labels.py then wires
into materials.
"""
from __future__ import annotations

import argparse
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 400, 560                       # portrait label, ~2:3

FONT_DIRS = ("/System/Library/Fonts/Supplemental", "/Library/Fonts",
             "/System/Library/Fonts")
SERIF = ("Didot.ttc", "Baskerville.ttc", "Times New Roman.ttf",
         "Georgia.ttf", "Palatino.ttc", "Bodoni 72.ttc",
         "Academy Engraved LET Fonts.ttf", "Copperplate.ttc")
GROTESK = ("Futura.ttc", "Gill Sans.ttc", "Helvetica.ttc", "Optima.ttc",
           "Avenir.ttc", "Arial Narrow.ttf")

# Paper, ink, accent. Chosen to read at 30 cm on a shelf in a dark bar, which
# is the only place any of this will ever be seen.
PALETTES = [
    ((0.94, 0.90, 0.80), (0.10, 0.09, 0.08), (0.62, 0.13, 0.11)),  # cream/red
    ((0.90, 0.86, 0.76), (0.09, 0.11, 0.13), (0.18, 0.28, 0.22)),  # cream/green
    ((0.12, 0.11, 0.10), (0.88, 0.84, 0.72), (0.76, 0.60, 0.24)),  # black/gold
    ((0.55, 0.13, 0.12), (0.94, 0.90, 0.82), (0.86, 0.74, 0.36)),  # oxblood
    ((0.86, 0.82, 0.70), (0.16, 0.14, 0.12), (0.36, 0.30, 0.55)),  # cream/violet
    ((0.16, 0.24, 0.20), (0.90, 0.88, 0.78), (0.78, 0.66, 0.30)),  # bottle green
    ((0.93, 0.91, 0.86), (0.13, 0.13, 0.14), (0.20, 0.34, 0.56)),  # white/navy
    ((0.72, 0.58, 0.28), (0.14, 0.11, 0.08), (0.42, 0.16, 0.10)),  # tobacco
    ((0.90, 0.88, 0.83), (0.15, 0.14, 0.13), (0.55, 0.42, 0.14)),  # bone/brass
]

HOUSES = ["OLD DOMINION", "HARLAN & SON", "CROWN STREET", "BLACKWATER",
          "ST. AUGUSTINE", "REDHOOK", "THE ALDERMAN", "FIVE POINTS",
          "J. HOLLOWAY", "MERIDIAN", "GRAND UNION", "KEEPER'S",
          "IRONBOUND", "DELANCEY", "WEST BROADWAY", "MORRISON'S",
          "CANAL & VINE", "THE ORCHARD", "PARK ROW", "STUYVESANT",
          "GOWANUS", "BOWERY LANE", "ASTOR HOUSE", "LUDLOW"]

CLASSES = ["KENTUCKY STRAIGHT BOURBON", "BLENDED SCOTCH WHISKY",
           "LONDON DRY GIN", "CARIBBEAN RUM", "STRAIGHT RYE WHISKEY",
           "BLANCO TEQUILA", "AMARO", "VERMOUTH DI TORINO",
           "SINGLE MALT", "TENNESSEE WHISKEY", "AGED RUM", "CANADIAN WHISKY"]

SUBS = ["DISTILLED & BOTTLED BY", "SMALL BATCH", "BOTTLED IN BOND",
        "CASK STRENGTH", "AGED IN OAK", "PROPRIETOR'S RESERVE",
        "SOUR MASH", "TRIPLE DISTILLED"]


def find_font(names, size):
    for n in names:
        for d in FONT_DIRS:
            p = os.path.join(d, n)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except OSError:
                    continue
    return ImageFont.load_default()


def rgb(c, mul=1.0):
    return tuple(int(max(0.0, min(1.0, v * mul)) * 255) for v in c)


def centred(draw, y, text, font, fill, tracking=0):
    if not text:
        return
    if tracking:
        widths = [draw.textlength(ch, font=font) + tracking for ch in text]
        total = sum(widths) - tracking
        x = (W - total) / 2.0
        for ch, adv in zip(text, widths):
            draw.text((x, y), ch, font=font, fill=fill)
            x += adv
    else:
        w = draw.textlength(text, font=font)
        draw.text(((W - w) / 2.0, y), text, font=font, fill=fill)


def make_label(seed):
    rng = random.Random(seed)
    paper, ink, accent = rng.choice(PALETTES)
    img = Image.new("RGB", (W, H), rgb(paper))
    d = ImageDraw.Draw(img)

    # paper tone variation before any ink goes down
    for _ in range(26):
        x, y = rng.randrange(W), rng.randrange(H)
        r = rng.randrange(40, 150)
        d.ellipse([x - r, y - r, x + r, y + r],
                  fill=rgb(paper, rng.uniform(0.94, 1.05)))
    img = img.filter(ImageFilter.GaussianBlur(18))
    d = ImageDraw.Draw(img)

    m = rng.choice((26, 32, 38))
    style = rng.choice(("rule", "box", "crest", "band"))
    if style in ("box", "crest"):
        d.rectangle([m, m, W - m, H - m], outline=rgb(ink), width=3)
        d.rectangle([m + 7, m + 7, W - m - 7, H - m - 7],
                    outline=rgb(ink), width=1)
    if style == "band":
        bh = rng.randrange(90, 130)
        d.rectangle([0, H // 2 - bh // 2, W, H // 2 + bh // 2], fill=rgb(accent))

    house = rng.choice(HOUSES)
    # Fit the wordmark to the plate instead of hoping it fits. "STUYVESANT"
    # and "ST. AUGUSTINE" ran off both edges at a fixed 58 pt, which is the
    # single most obvious way to make a label look generated rather than
    # printed.
    def fit_serif(text, start, limit):
        size = start
        while size > 22:
            f = find_font(SERIF, size)
            if ImageDraw.Draw(img).textlength(text, font=f) <= limit:
                return f
            size -= 2
        return find_font(SERIF, 22)

    inner = W - 2 * m - 24
    longest = max(([house] if len(house.split()) == 1 else
                   [house.split()[0], " ".join(house.split()[1:])]), key=len)
    f_house = fit_serif(longest, rng.choice((46, 52, 58)), inner)
    f_small = find_font(GROTESK, 17)
    f_class = find_font(GROTESK, 19)
    f_tiny = find_font(GROTESK, 13)

    y = m + rng.randrange(34, 60)
    centred(d, y, rng.choice(SUBS), f_small, rgb(ink, 0.7), tracking=2)
    y += 34

    words = house.split()
    for wline in ([house] if len(words) == 1 else
                  [" ".join(words[:1]), " ".join(words[1:])]):
        centred(d, y, wline, f_house, rgb(ink), tracking=1)
        y += f_house.size + 6

    y += 8
    d.line([(m + 30, y), (W - m - 30, y)], fill=rgb(accent), width=3)
    y += 20

    if style == "crest":
        cx, cy, r = W // 2, y + 52, 42
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=rgb(accent), width=3)
        d.ellipse([cx - r + 9, cy - r + 9, cx + r - 9, cy + r - 9],
                  outline=rgb(ink), width=1)
        f_est = find_font(SERIF, 30)
        centred(d, cy - 20, str(rng.randrange(18, 19) * 100 +
                                rng.randrange(10, 99)), f_est, rgb(ink))
        y = cy + r + 18

    on_band = (style == "band" and abs(y - H / 2) < 60)
    centred(d, y, rng.choice(CLASSES), f_class,
            rgb(paper) if on_band else rgb(ink, 0.85), tracking=1)
    y += 34
    proof = rng.choice((80, 86, 90, 92, 94, 100, 107, 114))
    centred(d, y, "%d PROOF  ·  %d%% ALC/VOL  ·  750 ML"
            % (proof, proof // 2), f_tiny, rgb(ink, 0.65))

    centred(d, H - m - 40, "NEW YORK", f_tiny, rgb(ink, 0.6), tracking=4)

    # age it: the label has been on a shelf in a bar for years
    px = img.load()
    for _ in range(rng.randrange(3, 7)):            # spill stains
        sx, sy = rng.randrange(W), rng.randrange(H)
        sr = rng.randrange(30, 90)
        for yy in range(max(0, sy - sr), min(H, sy + sr)):
            for xx in range(max(0, sx - sr), min(W, sx + sr)):
                dd = math.hypot(xx - sx, yy - sy)
                if dd < sr:
                    k = 1.0 - 0.20 * (1.0 - dd / sr) * rng.uniform(0.5, 1.0)
                    r_, g_, b_ = px[xx, yy]
                    px[xx, yy] = (int(r_ * k), int(g_ * k * 0.99),
                                  int(b_ * k * 0.96))
    for _ in range(900):                            # foxing / grain
        x, y2 = rng.randrange(W), rng.randrange(H)
        r_, g_, b_ = px[x, y2]
        k = rng.uniform(0.86, 1.10)
        px[x, y2] = (min(255, int(r_ * k)), min(255, int(g_ * k)),
                     min(255, int(b_ * k)))
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).rectangle([14, 14, W - 14, H - 14], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(16))
    img = Image.composite(img, Image.eval(img, lambda v: int(v * 0.80)), vig)
    return img.filter(ImageFilter.GaussianBlur(0.4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--count", type=int, default=24)
    ap.add_argument("--seed", default="16b5aafa")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    base = int(args.seed[:8], 16)
    for i in range(args.count):
        p = os.path.join(args.out, "label_%02d.png" % i)
        make_label(base + i * 7919).save(p)
    print("  [labels] wrote %d labels -> %s" % (args.count, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
