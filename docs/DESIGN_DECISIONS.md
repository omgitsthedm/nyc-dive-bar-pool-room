# Design Decisions

Values below are **not** published by any source in the hierarchy. They are
engineering choices made for a credible 9-foot, ~900–1,000 lb slate table.
None of them may be quoted as an Olhausen, Brunswick, or WPA specification.

Project dimensions and most explicit design decisions live in
`scripts/config.py`; the shared cushion/jaw/pocket plan contract lives in
`assets/data/table_wpa_geometry.json`. Most design-decision constants use the
`DD_` prefix. `CLOTH_T` is also a documented design decision even though its
older name predates that convention.

## Internal frame members

| Constant | Value | Rationale |
|---|---|---|
| `DD_SILL_W` / `DD_SILL_H` | 3.5 × 5.5 in | Perimeter sill sized to carry ~600 lb of slate plus a seated player on the rail. Proportioned off the patent's plywood beam (US3263996, Fig. 4). |
| `DD_CROSS_SILL_W/H` | 3.5 × 4.5 in | Four transverse sill assemblies, modeled as eight halves. Two assemblies sit directly under the slate seams per the Metro manual's support logic; two are intermediate. |
| `DD_BEAM_W/H` | 5.5 × 7.25 in | Central bolt-through beam. The patent shows a central longitudinal member carrying load between end frames; this is its modern hardwood equivalent. |
| `DD_APRON_T` / `DD_APRON_H` | 1.0 × 7.5 in | Flat panel apron with restrained routed reveal, per the Olhausen component breakdown. Thickness is cosmetic-plus-stiffening, not structural. |
| `DD_SIDE_POCKET_APRON_RELIEF_W/D` | 220 × 125 mm | Removes the side-pocket obstruction while preserving a split upper apron return. |
| `DD_LEG_HEAD_H` | 115 mm | Square load block beneath each sill. |
| `DD_LEVELER_PAD_H` / `DD_LEVELER_STEM_H` | 6 / 28 mm | Exposed pad and threaded stem used by the built leveler assembly. |
| `DD_RAIL_CAP_T` | 10 mm | Separate continuous finished walnut cap above the structural rail. |
| `DD_SIGHT_T` | 2.2 mm | Flush inlay thickness; the validator checks all 18 sights. |

`DD_LEVELER_H` and `DD_RAIL_BODY_H` remain legacy declarations in
`scripts/config.py` but do not drive the current built geometry.
`DD_POCKET_BASKET_D` is not a current constant; the active basket decision is
`DD_BASKET_DEPTH` below.

## Turned leg profile

`DD_LEG_TOP` 5.0 in square block, `DD_LEG_MIN` 3.25 in narrowest turning.
No source publishes the Remington's turning profile. The lathe profile in
`turned_leg_profile()` is original — a square head block, a cove, a slim
waist, and a foot ring. It is deliberately more restrained than the benchmark
mesh's turning, per the brief's instruction to let proportion and finish carry
the premium impression rather than ornament.

## Cushion envelope and seating

The current `k66_profile()` is a K-66-class cloth-covered envelope, not a claim
to reproduce a proprietary extrusion drawing. Its evaluated constraints are:

- 30.1625 mm published-class rubber height;
- 36.29025 mm nose above the bed (63.5% of a 57.15 mm ball);
- 38.100 mm rail-top height above the bed;
- 7.9375 mm cushion-envelope base above the bed;
- 50.800 mm covered width and 66° upper/lower faces.

The separate 10 mm walnut rail cap now fixes the rail top, so the earlier
percentage-based seating narrative is no longer the built profile. The
validator measures the evaluated cushion and cap geometry directly and confirms
all six cushions are outward manifold, meet the shared jaw/pocket contract and
do not rise above the rail top.

## Room

`WALL_T` 0.20 m for prewar masonry plus plaster. The 6.55 × 11.58 × 3.15 m
clear interior is taken from the brief and is not independently sourced.

## Environment character

The scene uses a fictional, original neighborhood-bar vocabulary: deep-green
wainscot, scarred dark wood, framed aged mirrors, dense generic bottle stock,
mismatched stools and chairs, diamond storefront glazing, field-built booths,
wall-mounted cues, payphone, CRT, darts, and layered old paper. It evokes the
warmth and clutter of a long-lived animated tavern without copying its floor
plan, characters, signage, brands, or protected art.

The 6.55 m clear width is treated as the interior of a roughly 25 ft masonry
lot. The rendered room is only the public front portion: a framed street door
and transom open beside the storefront, while separate service and restroom
doors imply additional depth behind the rear wall. This is a spatial inference
from the research in `ENVIRONMENT_RESEARCH.md`, not a survey or code claim.

The former clean floor is treated as a later concrete retrofit: broad wear is
procedural, but major cracks, aggregate failures, patched chips, sealed-in dry
discoloration, chair scuffs and traffic polishing are authored individually so
damage has location and history. It is swept and serviceable, not littered or
filthy. Two compact
booth bays and two small cafe tables stay at the perimeter, outside the cue
envelope. Booth benches run along X, perpendicular to the west wall; opposing
seats face one another across Y and both bays remain open on the east/pool side.
The backs themselves separate the bays, so no freestanding divider walls are
needed. The nearest booth component is 240 mm outside the cue rectangle.

The bar uses two rows on three shelves for 193 supported back-stock bottles in
seven profile families. The reduced count is more credible than the former 280
cloned cylinders: varied shoulders/necks, labels, shelf gaps, and a real opening
for the register now carry the density. Eight open working bottles have speed
pourers in a rail mounted to the ice/well station. The register faces the
bartender from the back-bar work surface rather than occupying the guest rail
as decoration.

The 3.80 m guest bar is confined to the front zone and stops 57 mm before the
nominal cue rectangle in Y. That allows its top and 360 mm underbar service
counter to move east without entering the playing clearance. A 220 mm shallow
wall cabinet and 240 mm back shelves remain against the west wall. Their front
edge and the service counter leave a measured 703 mm bartender aisle; the prior
version incorrectly overlapped the two work surfaces in plan. Ice, garnish,
soda gun, utility sink, drainboard, waste, cooler and glass handling follow the
aisle as connected work modules. These dimensions are scene design decisions,
not a hospitality code, accessibility, or permit claim.

The wall graphics are purpose-made fictional 1978–1999 artifacts rather than
modern clean posters. Printed wear is baked into the raster images, including
an analog memory collage and a separate irregular wheat-paste history field.
Primary art sits within millimetres of the wall and records a wheat-pasted
mounting method; frames, pins and raised tape are deliberately absent. A dense
flat sticker-bomb layer covers the restroom door. The west-wall spectator
vignette remains outside the nominal cue envelope; the validator checks this
relationship.

The hospitality-surface rule separates neglect from filth. The bar top is open
and wiped, with an old enamel bowl holding eight whole fruits, three actively
served drinks, one open tab, a dry away-place setting and a hollow tip jar;
there are no apple cores, food scraps, loose caps, dirty abandoned glasses or
sticky puddles. Patron tabletops are also wiped. Ten current dry coasters sit
over pale historical ring ghosts, fine scratches, softened edges and finish
loss from decades of earlier wet glasses. One current pint is intentionally
direct on the bar with fresh wipeable condensation, not a baked-in stain.

Pint and rocks-glass exterior envelopes are the manufacturer dimensions
recorded in `ENVIRONMENT_RESEARCH.md`. Their placements are design decisions:
each active glass stores a real seat anchor, support height, fill fraction and
0.244–0.656 m horizontal reach. Bar bases additionally remain at least 63 mm
inside the guest edge; reach alone is not allowed to justify overhang. This is
a staging/ergonomics contract, not a claim that the fictional bar uses a
particular commercial glassware brand.

The storefront exterior is an original nighttime Lower East Side street plate
set behind the diamond glazing, augmented by modeled car-color and opposite-
shop spill. A generic OPEN sign faces the street and therefore reads reversed
from inside. A separate generic 8-ball neon marks the front-room wall. These
elements create urban depth without copying a real storefront, logo or brand.

## Door and egress hardware

The storefront leaf uses a horizontal narrow-stile exit rail because the
interior must communicate one-action egress, not a decorative pull. The rail
has two returns, a latch case, a fixed jamb strike, hinges, threshold, and an
articulated surface closer whose two arms meet the body and frame shoe. No
interior key cylinder remains at the glass edge. This follows real hardware
operating logic but is a visualization choice, not an occupant-load or NYC
code-compliance determination.

The entry schoolhouse globe and fixed EXIT sign keep the front path readable.
Localized café and booth fixtures were added only after close renders proved
that physically present furniture was disappearing into black. The scene does
not use invisible cinematic fill; every light records its visible fixture or
modeled opening in `reports/object_realism_audit.json`.

## Classic billiard fixture

The three shades are original revolved profiles: 235 mm outer radius, 185 mm
height, 10 mm modeled shell thickness, and 500 mm center spacing. Green enamel
exteriors, cream reflectors, a brass spine, and paired chains were chosen to
read immediately as traditional pool-table lighting. The chain-hung assembly
is declared movable, allowing the requested WPA 40-inch condition above the
bed; its shade bottom is 1.778 m above this floor. The fixed-fixture 65-inch
condition is intentionally not used.

## Pocket iron geometry

The accepted geometry contract SHA-256 is
`afe868b3788218f0ba29dbe9d5caee81157c088b2b7fbbb00ed5f2faf89f04ad`.
Its evaluated sharp-line mouths use the WPA range midpoints: 115.8875 mm at
corners and 128.5875 mm at sides. The cut angles are 142° and 103.997691°;
shelves are 41.275 mm and 4.7625 mm. A modeled 13.5° backdraft sits within the
WPA 12–15° range.

`DD_POCKET_IRON_W`, `DD_POCKET_IRON_H`, and the welt dimensions describe an
open U-shaped rail-top iron/welt assembly rather than a near-circular collar.
The visible leather welt sweep is 210° at corners and 190° at sides. Its
recessed iron extends 10° farther to carry two mounting ears beneath the rail-cap
ends. Black steel does not span the mouth, and a capped primitive remains
forbidden because it would occlude the opening. Each visible cushion jaw ends at
its capture-circle crossing, with its back edge tucked under the welt instead of
forming an unsupported green fin inside the opening. The audit verifies all six
centers are open and each iron remains outside the capture circle.

## Gameplay physics architecture

### One deterministic authority

Pooltool 0.6.0, not Blender Bullet, is the shot authority. The solver uses an
explicit resolver profile, float64 state and continuous event times for
ball/ball, cushion, state-transition and pocket events. A 240 Hz export samples
that solved trajectory for presentation; changing the export frame rate does
not change the underlying events. `scripts/102_bake_pool_playback.py` writes
the samples as linear location and quaternion F-curves in the derived
`blend/poolroom_gameplay_preview.blend`.

The trajectory SHA covers every authoritative payload field, including the
profile and geometry identities, cue/rack setup, events and all ball samples.
Only volatile output metadata is excluded. Quaternion integration is split at
exact collision times so post-contact angular velocity is never smeared into
the interval before contact.

Zero Blender rigid bodies are therefore intentional. Bullet would introduce a
second, frame-stepped solution and does not directly encode billiards-specific
sliding-to-natural-roll, separate rolling and sidespin decay, or the same
pocket event model. The static proxy collection contains 42 diagnostic objects:
18 linear contacts, 12 arc contacts, six exact 2D `PTX_SolverPocket_*` capture
circles and six static 3D `PTX_ShelfDrop_*` construction volumes. It is neither
rendered nor promoted into Bullet collision bodies.

### Ball and contact profile

The machine-readable authority is `assets/data/pool_physics_profile.json`.
WPA-published size/material constraints and project-selected dynamics remain
explicitly separated:

| Property | Gameplay value | Status |
|---|---:|---|
| Ball diameter | 57.15 mm | WPA equipment dimension |
| Ball mass | 0.168 kg | Project choice within the WPA 0.156–0.170 kg range |
| Material metadata | cast phenolic resin, unwaxed polished surface | WPA-aligned resin family; visual/project finish description |
| Sliding friction coefficient | 0.20 | Project profile/calibration choice |
| Rolling deceleration | 0.125 m/s² (`u_r = 0.01274645`) | Project profile/calibration choice |
| Initial sidespin deceleration | 22 rad/s² | Project profile/calibration choice |
| Ball/ball friction | 0.07 | Project profile/calibration choice |
| Ball/ball normal restitution | 0.97 | Project profile/calibration choice |
| Cushion friction | 0.14 | Project profile/calibration choice |
| Stronge cushion restitution parameter | 0.88 | Calibrated solver parameter; produces a 0.8185 effective normal rebound ratio in the acceptance fixture |

The cushion parameter is not interchangeable with an energetic restitution
coefficient from another model. The tests report the effective normal rebound
ratio so future tuning can compare observed behavior rather than similarly
named inputs.

### Markings, cue and rack

The derived gameplay scene owns 16 new game balls rather than altering the
static hero-prop balls. Locally generated 2048 × 1024 equirectangular maps give
the object balls regulation solid/stripe color classes, two opposed white
number circles, an inverted duplicate numeral and underlines on 6 and 9. A
single red circle on the cue ball makes spin and orientation readable without
changing its collision sphere.

The playable cue is 1.4732 m / 58 in long including its bumper, 0.567 kg, with
a 13 mm tip, modeled as eight joined visual components and animated through
pullback, contact, follow-through and withdrawal. Its saved transform uses the
solver's `a`, `b`, `theta` and `phi` contact frame and reaches the authored cue
speed on the terminal approach segment. The hollow three-rail wooden triangle stages a
tight 8-ball rack with zero nominal contact gap: the 8 is centered in row
three, and the two rear corners are one solid and one stripe. Rack and cue
animation are presentation layers around the solver state, not hidden forces.

### Control break and pocket presentation

The canonical control break targets a 10.73 m/s / 24.0 mph cue-ball launch and
uses a fixed seed, rack order, cue position, direction and tip offset. Ten
fresh systems produce one canonical hash. At the accepted profile the shot
disperses 14 object balls by more than 150 mm, sends 11 object balls to a rail
or pocket, pockets the 7 ball and settles without overlap.

Pocket acceptance uses the same cushion/jaw/pocket plan contract as the static
table. Pooltool 0.6.0 captures against the continuous 2D pocket circle represented
exactly by each `PTX_SolverPocket_*` proxy. The separate `PTX_ShelfDrop_*`
volumes document the modeled 3D shelf and backdraft only; Pooltool does not use
them as capture triggers. Dedicated tests accept centered corner and side
approaches, reject jaw grazes, and preserve a continuous 0.48 s visual drop for
captured balls. This phase establishes deterministic shot mechanics and a
control-break fixture; a complete turn/foul/rules engine and multi-shot match
remain separate future work.

The capture decision is the solver's continuous 2D jaw/pocket event; the
post-capture fall is a deterministic monotonic presentation path. Gravity,
shelf hangers and speed-dependent pocket spit-outs are not claimed in this
foundation and remain a later pocket-model hardening step.

---

# Amendment 01 decisions

## Slate sections (Patch 8)

**Choice: three equal modeled slate objects**, each 37.0 in / 0.9398 m along
the table's 111 in exterior span. Each object covers a 33.33 in share of the
100 in playfield.

Real 9-foot slates are commonly unequal with a larger centre piece (roughly
30 / 40 / 30 in). Equal thirds are kept here because the transverse sills are
placed parametrically from the same exterior division, so one relation drives
both the slate seams and the sills that support them. The apparent discrepancy
between 37.0 in objects and 33.33 in playfield shares is the rail overhang, not
a seam gap. Dedicated support sills cross both seams.

## Pocket baskets (Patch 2)

| Constant | Value | Note |
|---|---|---|
| `DD_BASKET_DEPTH` | 118 mm | Inside the permitted 100–120 mm band, measured below the slate bed plane; selected to preserve the current six-ball capacity and catch-pad clearance. |
| `DD_BASKET_TAPER` | 0.78 | Base radius as a fraction of the mouth radius — baskets narrow toward the base without producing an implausibly pinched silhouette. |
| `DD_BASKET_STRAIGHT_MAX` | 60 mm | Deepest parallel-wall section permitted; the profile turns inward beyond it. |
| `DD_LEATHER_T` | 3.2 mm | Modelled wall thickness via Solidify, inside the 2.5–4 mm band. |

Baskets hang from the pocket iron on three visible blackened-steel straps per
pocket, so no leather floats unsupported. Depth and six-ball capacity are both
asserted in `reports/dimension_audit.json`.

## Ball numbers and stripes (Patch 4)

Numbers and stripe bands are **equirectangular decal maps** consumed inside the
shared ball material node graph. An earlier iteration built the stripe as a
second sphere shell trimmed to the equator; that is geometry, which the
amendment forbids, and it was removed.

Number circles are 22 mm (Aramith proportion), two per ball on opposite
hemispheres, with 6 and 9 underscored. Glyphs are drawn from a geometric
stroke description in `make_ball_decals.py`, so **no font file is required**
and Patch 6 has nothing to license.

Maps are 2048 × 1024 over a 57.15 mm sphere = **11,407 px per metre** of UV
space, against a 1024 px/m hero floor.
