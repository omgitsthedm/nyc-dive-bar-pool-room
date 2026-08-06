"""Generate regulation-style, equirectangular gameplay ball markings.

The locked static ball textures are intentionally untouched.  These images are
used only by the derived gameplay collection.  Number circles are projected as
spherical caps, the duplicate numeral is inverted, and 6/9 are underscored.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "textures" / "balls_game"
REPORT = ROOT / "assets" / "data" / "game_ball_markings.json"
FONT_PATH = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
WIDTH, HEIGHT = 2048, 1024
BALL_RADIUS_M = 0.028575
NUMBER_CIRCLE_DIAMETER_M = 0.022
IVORY = np.array([237, 232, 216], dtype=np.uint8)
BLACK = (10, 10, 9, 255)
RED_DOT = (150, 16, 12, 255)

# Restrained, familiar WPA color families in texture-space sRGB.
HUES = {
    1: (225, 177, 24),
    2: (30, 64, 150),
    3: (177, 34, 27),
    4: (93, 48, 119),
    5: (219, 99, 24),
    6: (36, 116, 61),
    7: (116, 34, 42),
    8: (20, 20, 18),
}
for number in range(9, 16):
    HUES[number] = HUES[number - 8]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def spherical_base(number: int) -> Image.Image:
    """Build the solid/stripe color field and opposed spherical number caps."""
    if number == 0:
        array = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
        array[:] = IVORY
        return Image.fromarray(array, "RGB").convert("RGBA")

    y = (np.arange(HEIGHT, dtype=np.float64) + 0.5) / HEIGHT
    x = (np.arange(WIDTH, dtype=np.float64) + 0.5) / WIDTH
    latitude = math.pi * (0.5 - y)[:, None]
    longitude = 2.0 * math.pi * x[None, :] - math.pi
    cos_latitude = np.cos(latitude)
    direction_y = cos_latitude * np.sin(longitude)

    color = np.asarray(HUES[number], dtype=np.uint8)
    array = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
    if number <= 8:
        array[:] = color
    else:
        array[:] = IVORY
        # Approximately 49 degrees of colored equatorial belt, consistent
        # with common phenolic pool sets without copying a proprietary layout.
        stripe = np.abs(latitude) <= math.radians(24.5)
        array[np.broadcast_to(stripe, array.shape[:2])] = color

    angular_radius = math.asin(
        (NUMBER_CIRCLE_DIAMETER_M * 0.5) / BALL_RADIUS_M)
    cap = np.abs(direction_y) >= math.cos(angular_radius)
    array[cap] = IVORY
    return Image.fromarray(array, "RGB").convert("RGBA")


def glyph_patch(number: int, inverted: bool) -> Image.Image:
    size = 300
    patch = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(patch)
    font_size = 174 if number < 10 else 139
    font = ImageFont.truetype(str(FONT_PATH), font_size)
    text = str(number)
    box = draw.textbbox((0, 0), text, font=font, stroke_width=1)
    text_w = box[2] - box[0]
    text_h = box[3] - box[1]
    x = (size - text_w) * 0.5 - box[0]
    y = (size - text_h) * 0.5 - box[1] - 5
    draw.text((x, y), text, font=font, fill=BLACK, stroke_width=1,
              stroke_fill=BLACK)
    if number in (6, 9):
        underline_y = int(y + text_h + 13)
        draw.line(
            (int(size * 0.31), underline_y, int(size * 0.69), underline_y),
            fill=BLACK,
            width=10,
        )
    if inverted:
        patch = patch.rotate(180, resample=Image.Resampling.BICUBIC)
    return patch


def add_number_glyphs(image: Image.Image, number: int) -> None:
    for center_x, inverted in ((WIDTH // 4, False), (3 * WIDTH // 4, True)):
        patch = glyph_patch(number, inverted)
        image.alpha_composite(
            patch,
            dest=(center_x - patch.width // 2, HEIGHT // 2 - patch.height // 2),
        )


def add_cue_reference_mark(image: Image.Image) -> None:
    """One traditional red-circle mark makes cue-ball spin readable."""
    draw = ImageDraw.Draw(image)
    center = (WIDTH // 4, HEIGHT // 2)
    radius = 43
    draw.ellipse(
        (center[0] - radius, center[1] - radius,
         center[0] + radius, center[1] + radius),
        fill=RED_DOT,
    )


def main() -> int:
    if not FONT_PATH.exists():
        raise FileNotFoundError(FONT_PATH)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    assets = {}
    for number in range(16):
        image = spherical_base(number)
        if number == 0:
            add_cue_reference_mark(image)
            filename = "ball_cue.png"
        else:
            add_number_glyphs(image, number)
            filename = "ball_%02d.png" % number
        path = OUTPUT / filename
        image.convert("RGB").save(path, format="PNG", optimize=True)
        assets[str(path.relative_to(ROOT))] = {
            "sha256": sha256(path),
            "width": WIDTH,
            "height": HEIGHT,
            "number": number,
            "class": "cue" if number == 0 else (
                "solid" if number <= 8 else "stripe"),
            "opposed_number_circles": 0 if number == 0 else 2,
            "duplicate_number_inverted": number != 0,
            "underscored": number in (6, 9),
        }
    report = {
        "schema": "pool-ball-markings/v1",
        "font": str(FONT_PATH),
        "resolution": [WIDTH, HEIGHT],
        "projection": "equirectangular spherical caps",
        "number_circle_diameter_m": NUMBER_CIRCLE_DIAMETER_M,
        "cue_reference": "single red-circle spin mark",
        "assets": assets,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("  [game ball decals] %d images -> %s" % (len(assets), OUTPUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

