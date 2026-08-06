"""70_build_cameras.py — required cameras plus environment review. Owns: 08_CAMERAS."""
import bpy, math, os, sys
from math import radians
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C
import lib as L

CAMS = "08_CAMERAS"
CX, CY = C.TABLE_CENTRE[0], C.TABLE_CENTRE[1]
HL = C.ROOM_L / 2.0

# Centroid of the presentation-critical 1, 8 and striped 9 balls. Keeping the
# focus plane here, rather than on the apex alone, gives the deep rack shot a
# useful distribution of sharpness without changing its established position.
RACK_KEY_BALL_CENTROID = (
    CX - C.BALL_D / 6.0,
    CY + C.FOOT_SPOT_Y - C.ROW_PITCH,
    C.BED_Z + C.BALL_R,
)

SPEC = [
    # name, lens, location, aim, fstop  (heights are eye-plausible)
    ("CAM_Hero_Entry_30mm", 30.0, (0.05, -HL + 0.85, 1.62),
     (CX, CY - 0.30, 1.02), 5.6),
    ("CAM_Table_ThreeQuarter_50mm", 50.0, (CX + 1.98, CY - 2.30, 1.34),
     (CX, CY - 0.05, C.BED_Z + 0.06), 3.5),
    ("CAM_Rack_Detail_85mm", 85.0, (CX + 0.46, CY - 1.24, C.BED_Z + 0.235),
     RACK_KEY_BALL_CENTROID, 16.0),
    ("CAM_Bar_Reverse_35mm", 35.0, (CX + 0.55, CY + 1.35, 1.55),
     (-C.ROOM_W / 2 + 1.1, -3.1, 1.15), 4.5),
    # Optional wide review from the front corner. It makes all three classic
    # billiard-light shades legible and shows the wall/bar relationship.
    ("CAM_Environment_Wide_35mm", 35.0, (2.48, -HL + 1.02, 1.64),
     (CX - 0.10, CY - 0.20, 1.12), 5.6),
    # Front-room proof: real entrance, concrete wear, cafe seating, register,
    # dense back bar and the narrow circulation aisle in one construction view.
    ("CAM_FrontRoom_22mm", 22.0, (0.42, 0.28, 1.58),
     (0.18, -4.32, 1.06), 5.6),
    # Forensic polish cameras: close enough to disprove unsupported hardware,
    # floating props, copied furniture and unmotivated light sources.
    ("CAM_Audit_Entrance_35mm", 35.0, (0.72, -1.80, 1.55),
     (C.DD_FRONT_DOOR_X, -HL + 0.08, 1.32), 5.6),
    # From the open south end of the now-physical bartender aisle: backbar is
    # on the west, underbar modules on the east, and neither occupies the other.
    ("CAM_Audit_BarWorkflow_45mm", 45.0, (-2.52, -5.00, 1.62),
     (-2.15, -2.45, 0.78), 5.6),
    ("CAM_Audit_FrontSeating_40mm", 40.0, (0.72, -0.68, 1.35),
     (2.43, -2.85, 0.72), 5.6),
    # Oblique from the pool aisle so both open booth mouths, wall-cleated
    # table ends and opposing perpendicular benches can be read at once.
    ("CAM_Audit_Booths_45mm", 45.0, (0.92, 1.22, 1.68),
     (-2.68, 2.48, 0.86), 5.6),
    ("CAM_Audit_Lighting_35mm", 35.0, (1.62, 0.38, 1.42),
     (0.18, 2.08, 2.17), 5.6),
    # Register bay proof: the machine stands 0.590 m from paw feet (0.920) to
    # crown ridge (1.510). A 50 mm from 1.02 m up the aisle only covers 0.412 m
    # vertically, so it cannot show the whole machine at once; 35 mm from
    # 1.574 m obliquely down the bartender aisle covers 0.910 m and leaves
    # 0.160 m of clear air above the crown. Oblique also reads the drum face,
    # the side cheek and the split shelf runs in a single frame.
    ("CAM_Audit_Register_35mm", 35.0,
     (C.DD_BACKBAR_X + 1.15, C.DD_BAR_CENTRE_Y - 1.25, 1.32),
     (C.DD_BACKBAR_X + 0.20, C.DD_BAR_CENTRE_Y, 1.215), 4.5),
    # Deep-patina proof cameras. These are deliberately close enough that a
    # clean procedural surface, floating paper or egg-like fruit cannot hide.
    ("CAM_Audit_BoothPatina_60mm", 60.0, (-0.92, 0.82, 1.22),
     (-2.72, 1.58, 0.72), 5.6),
    ("CAM_Audit_CleanBar_50mm", 50.0, (0.16, -4.45, 1.58),
     (-1.58, -3.24, 1.15), 5.6),
    # Measured pint and faceted rocks glass together, with their stool-aligned
    # offsets, coaster use and service-level asymmetry legible in one frame.
    ("CAM_Audit_PatronBarware_55mm", 55.0, (0.30, -4.88, 1.48),
     (-1.30, -3.63, 1.13), 5.6),
    ("CAM_Audit_StreetNeon_35mm", 35.0, (0.74, -3.26, 1.57),
     (-0.55, -5.72, 1.48), 5.6),
    ("CAM_Audit_WallHistory_45mm", 45.0, (1.28, 0.52, 1.54),
     (-3.02, 1.72, 2.02), 5.6),
    ("CAM_Audit_BathroomDoor_50mm", 50.0, (0.66, 3.12, 1.48),
     (C.DD_BATHROOM_DOOR_X, HL - 0.08, 1.10), 5.6),
    # First step inside the closed entrance: low enough to retain the door-
    # side threshold and street spill, but aimed up the room toward the bar,
    # table and classic fixture rather than into the frosted glazing.
    ("CAM_Cinematic_Threshold_Low_32mm", 32.0,
     (2.08, -HL + 0.42, 1.08),
     (0.30, -0.15, 1.02), 8.0),
    # Ball-height pre-break line: cue ball is the immediate subject and the
    # racked triangle remains the soft destination down-table.
    ("CAM_Cinematic_BreakLine_70mm", 70.0,
     (CX - 0.148, CY + 1.470, C.BED_Z + 0.098),
     (CX, CY + C.FOOT_SPOT_Y, C.BED_Z + C.BALL_R), 11.0),
]

FOCUS_OVERRIDES = {
    "CAM_Cinematic_Threshold_Low_32mm":
        (0.30, -0.15, 1.02),
    "CAM_Cinematic_BreakLine_70mm":
        (CX - 0.093, CY + C.HEAD_STRING_Y + 0.052,
         C.BED_Z + C.BALL_R),
}

def _film_camera_spec():
    """CAM_Film_* cameras, derived from the FROZEN take.

    Section 6.2's settle inserts cannot be authored until the break is
    chosen, because their framings depend on where the balls actually went.
    So they are computed here from assets/data/shots/break_film.json rather
    than hand-placed: pocket drop, cushion death, spin bleed, cue ball
    stopping, last ball stopping. If no take is frozen yet the film cameras
    are simply absent and every other build path is unaffected.

    All the audit cameras stay exactly where they are - validators expect
    them static, so these are additions, never edits.
    """
    import json
    import math
    path = os.path.join(C.ROOT, "assets", "data", "shots", "break_film.json")
    if not os.path.exists(path):
        return []
    with open(path) as handle:
        shot = json.load(handle)

    # coordinate_contract: blender = pool + (-0.385, +0.880, +0.762)
    OX, OY, OZ = -0.385, 0.880, 0.762
    def w(px, py, pz=0.0):
        return (px + OX, py + OY, pz + OZ)

    bed_z = OZ
    ball_r = float(shot["ball_parameters"]["R"])
    events = shot["events"]
    balls = shot["balls"]
    tw, tl = 1.27, 2.54                      # pool bed, metres
    ccx, ccy = tw / 2.0, tl / 2.0

    def final_xy(bid):
        p = balls[bid]["samples"][-1]["p"]
        return float(p[0]), float(p[1])

    spec = []

    # --- shot 8/6: low behind the cue ball, down the head string ---------
    cue0 = balls["cue"]["samples"][0]["p"]
    rack_y = min(float(balls[b]["samples"][0]["p"][1])
                 for b in balls if b != "cue")
    spec.append(("CAM_Film_CueAddress_85mm", 85.0,
                 w(float(cue0[0]) + 0.055, float(cue0[1]) + 0.30,
                   ball_r + 0.030),
                 w(ccx, rack_y + 0.10, ball_r), 2.2))

    # --- shot 7: macro insert, tip a chalk's width off the cue ball ------
    spec.append(("CAM_Film_TipInsert_100mm", 100.0,
                 w(float(cue0[0]) + 0.16, float(cue0[1]) + 0.20,
                   ball_r + 0.020),
                 w(float(cue0[0]), float(cue0[1]), ball_r), 1.8))

    # --- shot 9: locked-off god shot, whole table -------------------------
    # WORLD coordinates, not w(): this camera's height is an absolute height
    # in the room, not a height above the bed, and running it through the
    # pool->world offset once put it at z 3.04 - inside the ceiling, above the
    # light, filming the top of the shades.
    #
    # A true top-down is not physically available. The three shades hang at
    # z 1.778-1.963 across x 0.015-0.485, y 1.415-2.885, directly over the
    # table, so a camera above them sees shades and a camera under them needs
    # roughly a 13 mm fisheye to cover a 2.8 m table from 1 m up. This sits
    # high and off to the cue-side, where the sightline passes beside and
    # below the shades: at the near shade edge the ray is at z 1.54, a
    # quarter-metre under them. Still locked off, still the whole table.
    spec.append(("CAM_Film_BreakOverhead_24mm", 24.0,
                 (-1.35, 0.60, 2.35), (0.25, 2.15, 0.80), 8.0))

    # --- shot 2: the register drum, tighter than the audit reverse -------
    spec.append(("CAM_Film_Register_50mm", 50.0,
                 (C.DD_BACKBAR_X + 0.92, C.DD_BAR_CENTRE_Y - 0.86, 1.30),
                 (C.DD_BACKBAR_X + 0.20, C.DD_BAR_CENTRE_Y, 1.24), 2.8))

    # --- shots 10-14: settle inserts, from the take's own events ---------
    pockets = sorted((e for e in events if e["type"] == "ball_pocket"),
                     key=lambda e: e["time_s"])
    cushions = [e for e in events
                if e["type"] in ("ball_linear_cushion",
                                 "ball_circular_cushion")
                and e["time_s"] > 1.5]

    def speed(e):
        v = e["balls"][0]["initial"]["velocity_mps"]
        return math.hypot(float(v[0]), float(v[1]))
    cushions.sort(key=speed, reverse=True)
    stops = sorted((e for e in events if e["type"] == "rolling_stationary"),
                   key=lambda e: e["time_s"])

    # A - the first ball to drop, shot from outside the pocket looking in
    if pockets:
        pe = pockets[0]
        px, py = (float(v) for v in
                  pe["balls"][0]["final"]["position_m"][:2])
        ox, oy = px - ccx, py - ccy
        n = math.hypot(ox, oy) or 1.0
        ox, oy = ox / n, oy / n
        spec.append(("CAM_Film_Insert_A", 85.0,
                     w(px + ox * 0.55, py + oy * 0.55, 0.25),
                     w(px, py, -0.05), 2.8))

    # B - a ball dying against a cushion nose
    if cushions:
        ce = cushions[0]
        bx, by = (float(v) for v in
                  ce["balls"][0]["initial"]["position_m"][:2])
        # stand off ALONG the rail, toward whichever side has more table
        along = (1.0, 0.0) if abs(by - ccy) > abs(bx - ccx) else (0.0, 1.0)
        sign = 1.0 if (ccx - bx if along[0] else ccy - by) > 0 else -1.0
        spec.append(("CAM_Film_Insert_B", 100.0,
                     w(bx + along[0] * sign * 0.60 + (0.0 if along[0] else 0.16),
                       by + along[1] * sign * 0.60 + (0.16 if along[0] else 0.0),
                       0.18),
                     w(bx, by, ball_r), 2.8))

    # C - sidespin bleeding off a slowing ball, read on the cue ball's dot
    cfx, cfy = final_xy("cue")
    spec.append(("CAM_Film_Insert_C", 100.0,
                 w(cfx + 0.34, cfy + 0.30, 0.15), w(cfx, cfy, ball_r), 2.5))

    # D - the cue ball drifting to its final stop
    cue_samples = balls["cue"]["samples"]
    prev = cue_samples[max(len(cue_samples) - 24, 0)]["p"]
    dx, dy = cfx - float(prev[0]), cfy - float(prev[1])
    n = math.hypot(dx, dy) or 1.0
    spec.append(("CAM_Film_Insert_D", 85.0,
                 w(cfx - dx / n * 0.50, cfy - dy / n * 0.50, 0.20),
                 w(cfx, cfy, ball_r), 2.5))

    # E - the very last ball anywhere to stop moving
    if stops:
        last_id = stops[-1]["balls"][0]["id"]
        lx, ly = final_xy(last_id)
        spec.append(("CAM_Film_Insert_E", 85.0,
                     w(lx + 0.38, ly + 0.34, 0.20), w(lx, ly, ball_r), 2.5))
    return spec


def build(mats=None):
    L.clear_collection(CAMS)
    made = []
    film = _film_camera_spec()
    if film:
        print("  [cameras] %d film cameras derived from the frozen take"
              % len(film))
    for name, lens, loc, aim, fstop in tuple(SPEC) + tuple(film):
        tgt = bpy.data.objects.new(name + "_AIM", None)
        L.link(tgt, CAMS); tgt.location = aim; tgt.empty_display_size = 0.05
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.sensor_width = 36.0                     # full frame
        cd.clip_start, cd.clip_end = 0.02, 60.0
        cd.dof.use_dof = True
        focus = tgt
        if name in FOCUS_OVERRIDES:
            focus = bpy.data.objects.new(name + "_FOCUS", None)
            L.link(focus, CAMS)
            focus.location = FOCUS_OVERRIDES[name]
            focus.empty_display_size = 0.035
        cd.dof.focus_object = focus
        cd.dof.aperture_fstop = fstop
        cam = bpy.data.objects.new(name, cd)
        L.link(cam, CAMS); cam.location = loc
        t = cam.constraints.new("TRACK_TO")
        t.target = tgt; t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"
        made.append(cam)
    bpy.context.scene.camera = bpy.data.objects["CAM_Table_ThreeQuarter_50mm"]
    print("  [cameras] %d built" % len(made))
    return made

if __name__ == "__main__":
    build()
