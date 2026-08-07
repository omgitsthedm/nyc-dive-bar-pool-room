"""film_time.py - the one time map the picture and the sound both read.

There is exactly one definition of when the cue strikes. 105_render_film.py
used to hold it and 111_build_film_audio.py scraped it back out of that file
with a line-prefix match, which worked but meant the number lived inside a
renderer. It lives here now, and both sides import it.

    scene_time_s = film_time_s - FILM_OFFSET_S

so trajectory t=0 (the strike) lands on film frame 456, exactly 19.000 s in.

The strike moved from 12.5 s to 19.0 s on a direct note: the film has to earn
the break by showing the window, the bar and the glassware first, and each of
those wants to be held rather than glanced at. That leaves 19 s of room, the
7.806 s break in real time, and 3.2 s of settle - which is the shape the shot
list now has. Both the picture and the mix read this number from here, so
moving it moved both.

The baked playback in poolroom_gameplay_preview.blend starts at Blender frame
BAKE_START (=1) for trajectory t=0, so:

    scene_frame = BAKE_START + round((film_time_s - FILM_OFFSET_S) * FPS)

clamped to the baked range. Before the strike that clamp holds the rack set
and the cue addressing; after the last ball stops it holds the settled table.
The clamp is what lets the camera keep moving through 30 s while the physics
occupies only the 7.806 s it actually takes.

Importable from plain CPython (the audio mixer) and from Blender (the film
renderer). Nothing here imports bpy.
"""
from __future__ import annotations

FPS = 24
FILM_LEN_S = 30.0
TOTAL_FRAMES = 720                     # frames 0000..0719 inclusive
FILM_OFFSET_S = 19.0                   # the strike
STRIKE_FRAME = 456                     # == round(FILM_OFFSET_S * FPS)

# First Blender frame of the baked playback = trajectory t = 0.
BAKE_START = 1

assert TOTAL_FRAMES == int(round(FILM_LEN_S * FPS))
assert STRIKE_FRAME == int(round(FILM_OFFSET_S * FPS))


def film_frame(film_time_s):
    """film seconds -> global film frame index"""
    return int(round(film_time_s * FPS))


def film_time(frame):
    """global film frame index -> film seconds"""
    return frame / float(FPS)


def scene_time(frame):
    """global film frame index -> trajectory seconds (may be negative)"""
    return frame / float(FPS) - FILM_OFFSET_S


def scene_frame(frame, bake_start=BAKE_START, bake_end=None):
    """global film frame index -> baked Blender frame, clamped to the bake.

    Clamping is deliberate and is the only reason a 7.8 s break can carry a
    30 s film: outside the solved window the table simply holds its first or
    last solved state while the camera keeps moving.
    """
    f = bake_start + int(round(scene_time(frame) * FPS))
    if f < bake_start:
        f = bake_start
    if bake_end is not None and f > bake_end:
        f = bake_end
    return f
