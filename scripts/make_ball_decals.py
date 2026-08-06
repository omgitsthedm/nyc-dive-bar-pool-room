"""
make_ball_decals.py — equirectangular decal maps for the 16 balls.

Amendment Patch 4: numbers and stripes are masked decal layers consumed by the
shared ball material node graph. They are NOT curve objects, text objects, or
floating geometry parented to spheres, so nothing can drift off the sphere or
break silhouette at grazing angles.

Amendment Patch 7: 2048 x 1024 over a 57.15 mm sphere is roughly
2048 / (pi * 0.05715) = 11,400 px per metre of UV space, far above the
1024 px/m hero-surface floor.

Numbers are drawn as filled vector-style glyphs from a geometric stroke
description, so no font file is required and Patch 6 has nothing to license.
Run standalone with system Python; writes to assets/textures/balls/.
"""
import math
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import config as C          # noqa: E402

W, H = 2048, 1024
OUT = os.path.join(C.ROOT, "assets", "textures", "balls")

# WPA hues, 0-255
HUES = {
    1: (216, 158, 12), 2: (12, 42, 128), 3: (168, 22, 18),
    4: (58, 18, 82), 5: (206, 74, 12), 6: (14, 84, 34),
    7: (104, 26, 30), 8: (16, 16, 18),
}
for n in range(9, 16):
    HUES[n] = HUES[n - 8]

WHITE = (242, 238, 228)
CUE = (246, 243, 234)
INK = (22, 20, 20)

# Number circle: ~22 mm on a 57.15 mm ball (real Aramith proportion).
# Circumference = pi * d, so 22 mm spans 22/(pi*57.15) of the U axis.
CIRCLE_U = 0.022 / (math.pi * C.BALL_D)
CIRCLE_PX = int(CIRCLE_U * W)

# Stripe: ~half the ball diameter, centred on the equator.
# Half the diameter of arc corresponds to +/- 30 degrees of latitude.
STRIPE_HALF_V = 0.5 * (H / 2.0) * (60.0 / 90.0) * 0.5


def digit_polys(d):
    """
    Filled seven-segment digits with real segment width. Strokes drawn as
    lines read as thin scratches at ball scale; filled quads hold up at 100%
    crop, which is what the Patch 4 gate actually measures.

    Unit space: x 0..1, y 0..2. Returns a list of polygons.
    """
    w = 0.26                       # segment thickness
    h = w / 2.0
    S = {
        "a": [(h, 2 - h), (1 - h, 2 - h), (1 - w, 2 - w), (w, 2 - w)],
        "g": [(w, 1 + h), (1 - w, 1 + h), (1 - w, 1 - h), (w, 1 - h)],
        "d": [(w, w), (1 - w, w), (1 - h, h), (h, h)],
        "f": [(h, 2 - w), (w, 2 - w), (w, 1 + h), (h, 1 + w)],
        "b": [(1 - h, 2 - w), (1 - w, 2 - w), (1 - w, 1 + h), (1 - h, 1 + w)],
        "e": [(h, w), (w, w), (w, 1 - h), (h, 1 - w)],
        "c": [(1 - h, w), (1 - w, w), (1 - w, 1 - h), (1 - h, 1 - w)],
    }
    on = {0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc",
          5: "afgcd", 6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abfgcd"}[d]
    return [S[k] for k in on]


def draw_number(img, cx, cy, r, text, underline):
    """Filled circle with the number, and an underscore for 6 and 9."""
    d = ImageDraw.Draw(img)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
    n = len(text)
    gh = r * 1.16                       # glyph height
    gw = gh * 0.56
    total = n * gw + (n - 1) * gw * 0.26
    x0 = cx - total / 2.0
    for i, ch in enumerate(text):
        ox = x0 + i * (gw + gw * 0.26)
        oy = cy - gh / 2.0
        for poly in digit_polys(int(ch)):
            pts = [(ox + px * gw, oy + (2 - py) * (gh / 2.0))
                   for (px, py) in poly]
            d.polygon(pts, fill=INK)
    if underline:
        uy = cy + gh * 0.66
        d.line([cx - total * 0.62, uy, cx + total * 0.62, uy],
               fill=INK, width=max(3, int(gh * 0.13)))


def build_ball(num):
    if num == 0:
        img = Image.new("RGB", (W, H), CUE)
        d = ImageDraw.Draw(img)
        d.ellipse([W * 0.5 - 9, H * 0.5 - 9, W * 0.5 + 9, H * 0.5 + 9],
                  fill=(178, 44, 40))          # the single red spot
        return img

    hue = HUES[num]
    stripe = num >= 9
    img = Image.new("RGB", (W, H), WHITE if stripe else hue)
    d = ImageDraw.Draw(img)
    if stripe:
        d.rectangle([0, H / 2 - STRIPE_HALF_V, W, H / 2 + STRIPE_HALF_V],
                    fill=hue)
    # two number circles on opposite hemispheres, both upright
    r = CIRCLE_PX / 2.0
    for u in (0.25, 0.75):
        draw_number(img, u * W, H * 0.5, r, str(num), num in (6, 9))
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    for num in list(range(1, 16)) + [0]:
        name = "ball_cue.png" if num == 0 else "ball_%02d.png" % num
        build_ball(num).save(os.path.join(OUT, name))
    px_per_m = W / (math.pi * C.BALL_D)
    print("  [decals] 16 maps at %dx%d -> %.0f px/m of UV space (floor 1024)"
          % (W, H, px_per_m))


if __name__ == "__main__":
    main()
