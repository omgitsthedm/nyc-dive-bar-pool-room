"""
config.py — every locked dimension for the NYC dive-bar pool room.

One source of truth. No magic numbers anywhere else in the build.

Source-of-truth order (per the production brief):
  1. WPA equipment specifications
  2. Olhausen outside-dimension sheet (Remington / Cavalier rails)
  3. Brunswick Metro installation manual (assembly relationships)
  4. US3263996 (Braun, 1966) — hidden frame and load path
  5. Supplied Olhausen component breakdown (material stack)
  6. Downloaded benchmark mesh (visual proportion only)

Anything not published by a source above is marked DESIGN_DECISION and is
documented in docs/DESIGN_DECISIONS.md. Such values are never presented as
official specifications.
"""

import os

IN = 0.0254                       # metres per inch

# ---------------------------------------------------------------- project ---
PROJECT = "nyc-dive-bar-pool-room"
# Resolved from this file's own location, so the project can be relocated
# without editing a hardcoded path. (It previously pointed at Playground.)
ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
# The asset library now lives beside the project. Fall back to the original
# Downloads location so an older checkout still resolves.
_LOCAL_GLB = os.path.join(os.path.dirname(ROOT), "Pool Table Assets",
                          "pool_table_traditional-2.glb")
_DL_GLB = ("/Users/davidmarsh/Downloads/Pool Table Assets/"
           "pool_table_traditional-2.glb")
REFERENCE_GLB = _LOCAL_GLB if os.path.exists(_LOCAL_GLB) else _DL_GLB

COLLECTIONS = [
    "00_GUIDES", "01_ARCHITECTURE", "02_TABLE_VISIBLE", "03_TABLE_ENGINEERING",
    "04_BAR", "05_HERO_PROPS", "06_SET_DRESSING", "06_PATINA",
    "06_PATRON_FOOTPRINTS", "07_LIGHTS", "08_CAMERAS",
    "09_ATMOSPHERE", "10_PHYSICS_PROXIES", "99_REFERENCE_LOCKED",
]

# ------------------------------------------------------------ hero table ----
# WPA playfield, measured cushion-nose to cushion-nose.
PLAY_W = 50.0 * IN                # 1.2700 m
PLAY_L = 100.0 * IN               # 2.5400 m

# Olhausen outside dimensions, Cavalier rails, 9 foot.
OUT_W = 61.0 * IN                 # 1.5494 m
OUT_L = 111.0 * IN                # 2.8194 m

BED_Z = 30.0 * IN                 # 0.7620 m floor -> playing surface
RAIL_TOP_Z = 31.5 * IN            # 0.8001 m floor -> top of rail

RAIL_PLAN_W = 5.5 * IN            # 0.1397 m nominal rail plan width
SLATE_T = 1.0 * IN                # 0.0254 m, three-piece
LINER_T = 0.75 * IN               # 0.01905 m under-slate wood liner
CLOTH_T = 0.0010                  # DESIGN_DECISION: modelled worsted-cloth skin

BALL_D = 0.05715                  # 2.25 in exactly
BALL_NUMBER_CIRCLE_D = 0.022      # Aramith proportion (Amendment Patch 4)
BALL_R = BALL_D / 2.0             # 0.028575 m

# Cushion: K-66-class manufactured envelope. The exact nose height is WPA;
# the 50.8 mm cloth-covered featherstrip-to-nose width is the shared local
# pooltool/render contract. The rubber envelope fits entirely below the rail
# cap rather than protruding through it as the previous guessed profile did.
CUSHION_NOSE_MIN = 0.035719
CUSHION_NOSE_MAX = 0.036862
CUSHION_NOSE = BALL_D * 0.635     # 0.0362903 m — 63.5% of ball diameter
K66_HEIGHT = 1.1875 * IN          # 1 3/16 in overall rubber height
K66_FACE = 1.125 * IN             # 1 1/8 in top/face width
K66_ANGLE = 66.0                  # degrees, cross-section
CUSHION_COVERED_W = 2.0 * IN      # 50.8 mm, physics/render contract

# Sights (WPA 9-foot spacing).
SIGHT_SPACING = 12.5 * IN         # 0.3175 m
SIGHT_OFFSET_FROM_NOSE = 3.6875 * IN   # 0.0936625 m to sight centre
SIGHT_COUNT = 18
DD_SIGHT_T = 0.0022               # flush inlay thickness

# Pockets — centre of the permitted range, full range kept as metadata.
CORNER_MOUTH_MIN, CORNER_MOUTH_MAX = 4.5 * IN, 4.625 * IN
SIDE_MOUTH_MIN, SIDE_MOUTH_MAX = 5.0 * IN, 5.125 * IN
CORNER_MOUTH = 4.5625 * IN        # 0.11589 m
SIDE_MOUTH = 5.0625 * IN          # 0.12859 m
CORNER_CUT_ANGLE = 142.0          # degrees +/- 1
SIDE_CUT_ANGLE = 104.0            # degrees +/- 1
BACK_DRAFT = 13.5                 # degrees, permitted 12-15
CORNER_SHELF = 1.625 * IN         # within 1 to 2.25 in
SIDE_SHELF = 0.1875 * IN          # within 0 to 0.375 in
POCKET_FACING_T = 0.125 * IN      # 3.175 mm, permitted 1.588-6.35 mm

# WPA flatness tolerances — validation metadata only, never simulated.
FLATNESS_LENGTHWISE = 0.000508
FLATNESS_WIDTHWISE = 0.000254
JOINT_COPLANAR = 0.000127
CENTRE_DEFLECTION = 0.000762

# ------------------------------------------------- DESIGN_DECISION sizes ----
# Not published by any source. Chosen for a credible 900-1,000 lb 9-foot table.
DD_SILL_W = 3.5 * IN              # perimeter sill frame member width
DD_SILL_H = 5.5 * IN              # ... and depth
DD_CROSS_SILL_W = 3.5 * IN        # four transverse support sills
DD_CROSS_SILL_H = 4.5 * IN
DD_BEAM_W = 5.5 * IN              # central bolt-through beam
DD_BEAM_H = 7.25 * IN
DD_LEG_TOP = 5.0 * IN             # square head-block width/depth
DD_LEG_MIN = 3.25 * IN            # narrowest turned diameter
DD_LEG_HEAD_H = 0.115             # square load block beneath the sill
DD_LEVELER_PAD_H = 0.006          # exposed steel pad above finished floor
DD_LEVELER_STEM_H = 0.028         # threaded stem, incl. 2 mm pad overlap
DD_APRON_T = 1.0 * IN             # flat apron panel thickness
DD_APRON_H = 7.5 * IN             # apron panel height
DD_SIDE_POCKET_APRON_RELIEF_W = 0.220
DD_SIDE_POCKET_APRON_RELIEF_D = 0.125
DD_LEVELER_H = 1.25 * IN          # blackened steel leveler travel + plate
DD_RAIL_BODY_H = 2.0 * IN         # hardwood rail body above the slate
DD_RAIL_CAP_T = 0.010             # finished continuous walnut top cap
DD_CUSHION_TERMINAL_EDGE_RADIUS = 0.0015  # cloth-wrapped pocket-facing edge
# Pocket baskets (Amendment Patch 2). Depth is measured below the slate bed
# plane. Baskets taper toward the base; no parallel vertical wall deeper than
# 60 mm. Interior must admit six tangent 57.15 mm balls.
DD_BASKET_DEPTH = 0.118           # permitted 0.100-0.120
DD_BASKET_DEPTH_MIN = 0.100
DD_BASKET_DEPTH_MAX = 0.120
DD_BASKET_TAPER = 0.78            # base radius as a fraction of mouth radius
DD_BASKET_STRAIGHT_MAX = 0.060    # deepest parallel-wall section permitted
DD_LEATHER_T = 0.0032             # 2.5-4 mm modelled leather wall

# -------------------------------------------------------------- the rack ----
FOOT_SPOT_Y = -PLAY_L / 4.0       # 0.635 m from centre toward the foot rail
HEAD_STRING_Y = PLAY_L / 4.0
ROW_PITCH = (3.0 ** 0.5) / 2.0 * BALL_D   # 0.0494952 m tangent row spacing

# ------------------------------------------------------------------ room ----
ROOM_W = 6.55                     # 21 ft 6 in clear interior
ROOM_L = 11.58                    # 38 ft 0 in
ROOM_H = 3.15                     # 10 ft 4 in
WALL_T = 0.20                     # DESIGN_DECISION: prewar masonry + plaster

TABLE_CENTRE = (0.25, 2.15, 0.0)  # brief sec.9; table long axis along Y

CUE_LEN = 58.0 * IN               # 1.4732 m
CUE_ENVELOPE_W = 4.216            # nominal clearance for a 9-foot table
CUE_ENVELOPE_L = 5.486
WPA_OBSTACLE_CLEARANCE = 1.83     # 6 ft rail-to-obstacle, preferred

# --------------------------------------------------------------- lighting ---
FIXTURE_LEN = 1.48                # classic three-shade billiard light
# Venue-specific chain-hung/movable fixture. WPA permits 40 in above the bed
# for a fixture a referee can move aside; 65 in applies to non-movable rigs.
FIXTURE_MIN_ABOVE_BED = 40.0 * IN # 1.016 m; shade bottom ~1.78 m above floor
FIXTURE_CONFIGURATION = "movable_chain_hung"
LUX_TABLE_MIN = 520.0
LUX_VENUE_MIN = 50.0

BAR_LEN = 3.80
BAR_DEPTH_GUEST = 0.75
BAR_HEIGHT = 1.067                # 42 in finished

# -------------------------------------- environment art direction (DD) -----
# Original, project-specific dimensions for the historic dive-bar pass.
DD_WAINSCOT_H = 1.04
DD_WAINSCOT_T = 0.028
DD_CHAIR_RAIL_H = 0.075
DD_CHAIR_RAIL_D = 0.055
DD_WAINSCOT_PANEL_PITCH = 0.62

DD_WINDOW_MULLION_W = 0.030
DD_WINDOW_MULLION_D = 0.026
DD_WINDOW_DIAMOND_BAR_L = 0.84
DD_WINDOW_DIAMOND_X = (-2.42, -1.86, -1.30, -0.74, -0.18, 0.38, 0.94, 1.50)
DD_WINDOW_DIAMOND_Z = (0.93, 1.52, 2.11)

DD_FRONT_DOOR_X = 2.36
DD_FRONT_DOOR_W = 0.91
DD_FRONT_DOOR_H = 2.10
DD_FRONT_EXIT_BAR_W = 0.66
DD_FRONT_EXIT_BAR_Z = 1.02
DD_DOOR_FRAME_W = 0.085
DD_DOOR_FRAME_D = 0.060
DD_REAR_DOOR_W = 0.84
DD_REAR_DOOR_H = 2.03
DD_SERVICE_DOOR_X = -1.86
DD_BATHROOM_DOOR_X = 1.86

DD_BAR_FRONT_PANEL_COUNT = 8
DD_BAR_PANEL_FRAME_W = 0.038
DD_BAR_PANEL_INSET_T = 0.018
DD_BAR_STOOL_SEAT_H = 0.755
DD_BAR_STOOL_SEAT_R = 0.185
DD_BAR_STOOL_BACK_H = 0.305
DD_BAR_STOOL_FOOT_Z = 0.265
DD_BAR_STOOL_OFFSETS = (-1.55, -0.56, 0.50, 1.58)
# y offset, pull away from bar, yaw degrees, acquisition type. Installed bar
# fixtures may align; loose stools should not look surveyed into position.
DD_BAR_STOOL_LAYOUT = (
    (-1.57, 0.060, -7.0, "round_oak"),
    (-0.60, -0.015, 4.5, "vinyl_tube_back"),
    (0.52, 0.115, -11.0, "square_wood"),
    (1.55, -0.040, 13.0, "pedestal_swivel_back"),
)
DD_BAR_BOTTLE_ROWS = 2
DD_BAR_BOTTLE_SHELVES = 3
# The front-zone bar section is kept south of the pool cue rectangle. A shallow
# wall backbar, 700 mm working aisle and 360 mm service counter fit inside the
# 1.42 m perimeter strip without pretending two counters occupy the same space.
DD_BAR_TOP_X = -1.53
DD_BAR_CENTRE_Y = -2.55
DD_BAR_SERVICE_X = -1.985
DD_BACKBAR_X = -3.155
DD_BACKBAR_DEPTH = 0.22
DD_BACKBAR_SHELF_DEPTH = 0.24
DD_BARTENDER_AISLE_MIN = 0.70

# A1 whole-room haze density (Principled Volume, ATM_RoomHaze_Volume).
# Cycles stills only - the EEVEE film path hides the volume entirely.
#
# MEASURED, not guessed. Rendering CAM_Hero_Entry_30mm across the range and
# reading the image back:
#   density   far-wall stops lost   shadow lift   lit/shadow contrast
#     0.000         0.000              +0.0%          1.43
#     0.004         0.016              +0.4%          -
#     0.012         0.017              +0.4%          -
#     0.110         0.009              +1.4%          -
#     0.200         0.004              +4.4%          1.38
#     0.400         0.012              +9.6%          1.32
#     0.700         0.019             +11.5%          1.31
#     1.200         0.005             +12.8%          1.30
# The far wall never approaches the 1-stop budget at any density, because in a
# lit room haze ADDS in-scattered light rather than subtracting it; the effect
# shows up as lifted shadows and reduced contrast. Anything at or below ~0.1 is
# indistinguishable from no haze at all - the originally specified 0.004-0.012
# band is roughly 100x too low for a Principled Volume at this room scale.
#
# Far-wall stops turned out to be the WRONG gauge. The cost of haze lands on
# near-camera surface texture, not on distant brightness. Measured on
# CAM_Cinematic_Threshold_Low_32mm at final quality, comparing the floor's
# local contrast against the same frame with no haze:
#   density   floor detail   shadow lift
#     0.00        +0.0%          +0.0%
#     0.45        -2.2%          +2.2%
#     0.70        -4.2%          +2.7%
#     1.20        -8.9%          +2.9%
# Lift saturates by 0.70 while the detail cost still doubles on the way to
# 1.20. At 1.20 the concrete slab cracks wash out of the near floor entirely,
# which is exactly the "lived-in reads through detail" the room depends on.
# 0.70 buys 93% of the atmosphere for less than half the texture.
DD_ROOM_HAZE_DENSITY = 0.70

# In-scattering needs volume bounces; the scene ships with 0, which alone cost
# about a quarter of the effect (shadow lift +10.2% vs +12.8% at density 1.20).
# Applied in memory by the Cycles stills path only, never saved.
DD_ROOM_HAZE_VOLUME_BOUNCES = 2

# Two compact wall bays only. Each tuple is
# (centre_y, bench_run_from_wall_x, total_bay_width_y). The benches run along
# X, perpendicular to the west wall, so patrons enter from the east/pool aisle
# and face one another across Y. These are intentionally not a continuous
# banquette and never become a second wall inside the room.
DD_BOOTH_LAYOUT = ((1.52, 1.04, 1.30), (3.25, 0.98, 1.36))
DD_BOOTH_TABLE_X = -2.71
DD_CAFE_TABLE_LAYOUT = ((2.54, -3.55, 0.31), (2.50, -2.15, 0.28))

# Current-shift serviceware. These are manufacturer dimensions, converted to
# metres, rather than generic scene-scale cylinders. Libbey 1639HT mixing
# glass: 16 oz, 3.5 in diameter, 5.88 in tall. Libbey 15232 Gibraltar rocks:
# 10 oz, 3.5 in diameter, 3.88 in tall. See docs/ENVIRONMENT_RESEARCH.md.
DD_PINT_GLASS_D = 3.50 * IN
DD_PINT_GLASS_H = 5.88 * IN
DD_ROCKS_GLASS_D = 3.50 * IN
DD_ROCKS_GLASS_H = 3.88 * IN
DD_SERVICE_COASTER_D = 0.104
DD_SERVICE_COASTER_T = 0.003

DD_POOL_SHADE_R = 0.235
DD_POOL_SHADE_H = 0.185
DD_POOL_SHADE_SPACING = 0.50
DD_POOL_SHADE_SHELL_T = 0.010
DD_POOL_FIXTURE_BAR_W = 0.060
DD_POOL_FIXTURE_CHAIN_R = 0.006

DD_POCKET_IRON_W = 0.010
DD_POCKET_IRON_H = 0.006
# Local to the bed plane. The casting sits under the padded rail-top welt,
# outside the clear throat, as a real leather-wrapped pocket iron does.
DD_POCKET_IRON_CENTRE_Z = RAIL_TOP_Z - BED_Z - 0.0085
DD_POCKET_WELT_MAJOR_OFFSET = 0.0075
DD_POCKET_WELT_R = 0.0058
DD_POCKET_CORNER_SWEEP_DEG = 210.0
DD_POCKET_SIDE_SWEEP_DEG = 190.0
DD_POCKET_IRON_SWEEP_EXTRA_DEG = 10.0
DD_POCKET_MOUNT_EAR_L = 0.045
DD_POCKET_MOUNT_EAR_W = 0.016
DD_POCKET_MOUNT_EAR_H = 0.004
DD_POCKET_MOUNT_EAR_OVERLAP = 0.004
DD_POCKET_RIVET_R = 0.0028
DD_POCKET_RIVET_H = 0.0030
DD_POCKET_SKIRT_T = 0.0032
DD_POCKET_STITCH_W = 0.0008
DD_POCKET_STITCH_H = 0.00055
DD_POCKET_STRAP_W = 0.012
DD_POCKET_STRAP_T = 0.0032
DD_POCKET_STRAP_OVERLAP = 0.002
# The analytic transition fillets are too tight to carry the full 50.8 mm
# upholstered rail envelope. The visible jaw terminates at the capture-circle
# crossing and its back edge tucks under the leather welt; narrowing happens
# only beside the hidden fillet, never at the mouth.
DD_CUSHION_JAW_WELT_OVERLAP = 0.0010
DD_CUSHION_JAW_TAPER_L = 0.012

# name, wall, horizontal centre, vertical centre, width, height, tilt degrees
DD_WALL_ART_LAYOUT = (
    ("payphones", "east", 0.62, 1.78, 0.58, 0.87, -2.0),
    ("tuesday_8ball", "east", 2.78, 1.76, 0.62, 0.93, 1.5),
    ("sticker_wall", "east", -0.58, 1.70, 1.30, 0.78, 0.7),
    ("pool_team", "rear", 0.32, 2.34, 1.08, 0.72, -1.0),
)


# A3 peeling paper corners: (art_name, corner, tip_lift_m, roll_deg).
# Corner letters are vertical then horizontal: S/N = lower/upper, W/E = the
# negative/positive in-plane horizontal direction of that wall. Wheat paste
# fails at corners first, so these are corners, never edges or centres. Lifts
# stay in the 5-20 mm band and the flap stays small: worn, not trashed.
# Two on the sticker-wall history field, one on the art nearest the dartboard
# (east wall, y 4.20), one on the payphones sheet.
DD_PAPER_CURLS = (
    ("sticker_wall", "NE", 0.016, 55.0),
    ("sticker_wall", "SW", 0.009, 80.0),
    ("tuesday_8ball", "NE", 0.013, 45.0),
    ("payphones", "SE", 0.011, 65.0),
)


def playfield_to_world(x, y, z=0.0):
    """table-local playfield coords -> world (table centred per TABLE_CENTRE)"""
    return (TABLE_CENTRE[0] + x, TABLE_CENTRE[1] + y, BED_Z + z)


# ------------------------------------------------- cloth (Patch 3 lock) -----
CLOTH_CLASS = "worsted wool, Simonis 860 class"
CLOTH_WEIGHT_GSM = 700.0          # ~21 oz per square yard
CLOTH_THREAD_MAX_W = 0.0005       # no apparent thread wider than 0.5 mm

# ----------------------------------------------- texel density (Patch 7) ----
TEXEL_HERO = 1024.0               # px per metre of UV space
TEXEL_MID = 512.0
TEXEL_BACKGROUND = 256.0
