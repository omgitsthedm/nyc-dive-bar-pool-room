# QA Report — Frozen Environment, Static Pool System and Gameplay Physics

## Automated gates

### Pure geometry-contract audit — 68/68 PASS

`reports/pool_geometry_contract_audit.json` validates the shared cushion, jaw
and pocket source independently of Blender. Its accepted source SHA-256 is
`afe868b3788218f0ba29dbe9d5caee81157c088b2b7fbbb00ed5f2faf89f04ad`.
The audit confirms 115.8875 mm corner and 128.5875 mm side evaluated mouths at
the WPA range midpoints, 142°/103.997691° cuts, 41.275/4.7625 mm shelves and
the capture-circle crossings used to terminate the visible jaws.

### Dimensional/static-construction audit — 93/93 PASS

`reports/dimension_audit.json` is generated from evaluated Blender geometry,
not by restating source constants.

- Playfield: 1.270000 × 2.540000 m; exterior: 1.549400 × 2.819400 m.
- Bed: 0.762000 m; rail top: 0.800100 m.
- Cushion nose: 36.290 mm, inside the WPA range.
- Slate: 25.400 mm, three pieces.
- Balls: 16; diameter tolerance and uniform scale pass.
- Pocket baskets: 6/6; depth and six-ball capacity pass.
- Pocket irons: 6/6 measured with open centers.
- Pocket construction: 12 cloth-covered facings, six cloth liners, six leather
  throats, six open U-shaped iron/welt assemblies, six leather skirts, six
  stitch runs, 12 mount ears, 12 mount bolts, 18 leather straps and rivets, six
  baskets, six basket bases and six serviceable rail caps.
- Pocket shelves measured from evaluated cloth: 41.275 mm at corners and
  4.7625 mm at sides; hidden-wood/apron collisions: 0; verified attachment
  contacts: 102.
- Table frame: two long sills, two end sills, eight cross-sill halves and one
  centre beam; 21 frame/leg manifold solids, six load paths and 18 rail studs.
- Rail finish: six crafted caps and 18 flush sights.
- Set-dressing objects inside the nominal cue envelope: 0.
- Movable pool-light clearance: 1.016 m above bed / 1.778 m above floor.
- Constructed door assemblies: 3/3.
- Supported back-bar stock: 193 complete bottles; minimum gate 120.
- Floor hero material: `MAT_Env_Floor_NeglectedConcrete`.
- Rigid bodies, missing external files, unassigned material slots, unapplied
  production-mesh scale, and stray startup objects: 0.
- Hidden diagnostic proxies: 42 (30 mesh and 12 curve): 18 linear, 12 arc, six
  exact 2D `SolverPocket` capture circles and six static 3D `ShelfDrop`
  construction volumes. These are not rigid bodies.
- Reference and guide collections remain excluded from render view layers.

### Realism audit — 33/33 PASS

`reports/object_realism_audit.json` records the current derived preview: 2,317
render-visible component objects grouped into 1,064 logical real-world items,
with 33/33 required realism contracts passing.

- Complete front exit hardware: 13/13 required operating components.
- Unsupported vertical door pull: absent.
- Bottle profiles: seven families, requirement at least five.
- Supported bottle bodies: 201/201 bottoms meet their shelf or speed rail within 2 mm (193 back stock + 8 well bottles).
- Bar stools: four distinct acquisition types and four yaw values.
- Seating/patron-table assemblies within 2 mm of floor contact: 12/12.
- Booth layout: two wall-adjacent face-to-face bays, four perpendicular bench
  backs, zero divider walls, pool-side entries 240 mm clear of the cue envelope.
- Register: back-bar work surface, facing bartender.
- Bar workflow: all required ice/well/soda/garnish/sink/drain/waste/mat/opener/
  beer roles present; speed pourers 8/8; bartender aisle 703 mm; bar-to-cue
  clearance 57 mm.
- Motivated light objects: 25/25.
- Mounted primary art planes: 4/4.
- Flush primary art planes: 4/4; forbidden frames, pins and raised tape: 0.
- Explicit restrained booth-wear components: 36 across both booth bays.
- Flat restroom-door sticker layers represented: 180; flush paper-history zones: 3/3.
- Patron service: 10 active drinks split five pint beers/five faceted rocks
  cocktails and bar 3/booths 4/café 3; all 10 meet their support and declared
  0.244–0.656 m seat reach; every bar glass/coaster base remains at least 63 mm
  inside the guest edge and 216 mm inside the nearest bar end.
- Complete drinks: pints 5/5 with beer/foam; rocks 5/5 with cocktail, three ice
  cubes, lime wheel and straw.
- Coaster logic: nine served coasters, one direct fresh-condensation placement,
  and one dry away-place setting; 14 historical finish-ring ghosts and 10 fine
  scratches remain beneath current service.
- Guest bar top: zero legacy debris; five lower fruits below the bowl rim,
  three upper fruits touching the lower cluster, three inset active drinks and
  one open tab.
- Storefront street/neon sources: 5/5; constructed aged cross beams: 3/3.
- Used aged material families: 38; authored subtle story components: 18.

The inventory method and category counts are documented in
`docs/REALISM_AUDIT.md`.

### Physical-staging audit — 14/14 PASS

`reports/environment_staging_audit.json` routes every visible component to a
real-world owner/support contract and evaluates 321 high-risk logical items.
Its current inventory matches the derived preview at 2,317 visible components
and 1,064 logical items.

- Current derived-preview inventory: 2,317 visible components / 1,064 logical
  items.
- High-risk support/placement evidence: 321/321; failures 0.
- Bottle roots: 201/201 supported and contained by a shelf or speed rail;
  minimum root clearance 10.86 mm; interpenetrations 0.
- Patron footprints: supported/contained with no interpenetrating placements.
- Loose furniture: no exact duplicate transforms.
- Upper backbar radio, trophy, coffee tin and pickle jar: 4/4 seated on a real
  display ledge.
- Fruit bowl meets the bar top; five lower fruits meet the basin and three upper
  fruits contact the lower cluster.
- Wall cues engage rack clips; score rods have wall plates and spacers; chalk
  and carved tabletop initials meet their intended surfaces.
- Blender rigid bodies: 0 in the static candidate and still intentionally 0 in
  the derived gameplay scene. The 42 hidden proxies are diagnostic geometry;
  Pooltool supplies the deterministic dynamic solution.

### Environment lock — PASS

`reports/environment_lock.json` fingerprints the approved static room at
2,143 objects, 82 used materials and eight image assets. Standalone verification
matches aggregate SHA-256
`de99efd0b2f5caef661e66d542918f06942a20ea7330f925a615d77b778bd0be`.
Architecture, bar, set dressing, patina and patron-service collections are
unselectable in the frozen `blend/poolroom_master.blend`. Non-pool lights and
global color state are also fingerprinted. Pool-table collections, pool fixture
objects, balls, cameras and pool atmosphere remain outside this freeze and are
developed in `blend/poolroom_pool_rebuild_preview.blend`.

### Static pool-system inventory — PASS

The derived preview contains 296 table meshes plus one `PT_TableRoot` empty:
121 meshes in `02_TABLE_VISIBLE` (including the twelve walnut cap horns added
by the 2026-08-05 pocket-mouth revision); 175 meshes and the root in
`03_TABLE_ENGINEERING`. The separate `10_PHYSICS_PROXIES` collection contains
42 hidden diagnostic objects (30 mesh and 12 curve).

`reports/pool_system_lock.json` fingerprints this accepted static pool state at
355 objects and 30 materials. Standalone verification matches aggregate
SHA-256 `0d7d3949f39661715cb5edb41d1e044b6461a0ed28fe96857fa16ce826a47273`.

Shared geometry measures 115.8875 mm corner and 128.5875 mm side evaluated
mouths at the WPA permitted-range midpoints. Corner/side jaw cuts are
142.000°/103.997691°; the modeled 13.5° backdraft is inside the WPA 12–15°
range; facing thickness is 3.175 mm. The visible U-shaped welt sweeps are 210°
at corners and 190° at sides, with visible jaws ending at their capture-circle
crossings. These are static construction results. Pooltool capture uses the 2D
circle, not the modeled 3D shelf/backdraft.

### Deterministic physics suite — 15/15 PASS

`reports/physics_validation.json` is generated by
`scripts/100_validate_pool_physics.py` under Python 3.12.13 with pinned
Pooltool 0.6.0, NumPy 2.3.5, Numba 0.62.1, resolver version 9 and float64
state. Its 15 required contracts all pass:

- pinned profile/source identity and 57.15 mm / 0.168 kg ball contract;
- analytic sliding-to-natural-roll transition and rolling stop;
- head-on and cut-angle ball/ball transfer with momentum/no-overlap checks;
- calibrated cushion restitution with mirrored positive/negative English;
- draw, stop and follow from vertical tip offsets;
- centered corner/side pocket capture and jaw-graze rejection;
- 20 m/s continuous ball and cushion collision detection without tunneling;
- legal tight-rack 24 mph control break;
- four-table-length cushion-travel fixture;
- identical event solution when sampled at 24, 30, 60 and 240 Hz;
- a full authoritative-payload trajectory identity that detects field
  mutation while excluding only volatile output metadata;
- collision-split quaternion integration matching a 16× reference at the
  contact probes; and
- ten fresh control-break systems with one canonical hash.

The control break lasts 5.850 s across 197 events. It disperses 14 of 15 object
balls by more than 150 mm, sends 11 object balls to a rail or pocket, pockets
the 7 ball, and finishes with 67.907 mm minimum ball separation. The solver
fixture hash is
`3886177ecb2f271e4b55d5c086609532f9cd44a36313723b129dc4f2f9fa3619`.

### Solver-to-Blender playback audit — 216/216 PASS

`reports/physics_playback_audit.json`, generated by
`scripts/103_validate_pool_playback.py`, verifies the further-derived
`blend/poolroom_gameplay_preview.blend` without changing either protected
source blend.

The gameplay bake is additive: `blend/poolroom_master.blend` and
`reports/environment_lock.json` remain unchanged protected artifacts, and
`reports/pool_system_lock.json` carries the deliberately re-banked 2026-08-05
pocket-revision baseline. Fresh read-only checks against the saved gameplay
candidate pass both protected locks: 2,143 environment objects and 355 static
pool objects are unchanged.

All 216 checks pass:

- independently recomputed trajectory, profile and geometry hashes match the
  baked scene;
- `11_GAMEPLAY` and the `GAMEPLAY` view layer exist, with static hero balls
  excluded from that view;
- all 16 gameplay balls have their correct hashed marking map, connected
  material, real dimensions, mass and complete physical-profile metadata;
- the eight-part playable cue measures 1.4732 m, reaches the exact `a/b/theta`
  contact and evaluates at 6.98811 m/s versus the 6.98816 m/s solver input;
- the three-rail triangle contains the legal order, 8-ball center, rear-corner
  classes and 30 tangent rack neighbors without overlap;
- Blender rigid bodies remain at zero and the scene records that choice as
  intentional;
- solver/world coordinate roundtrip error is effectively zero;
- all 1,535 exported timeline samples are checked for every ball: 24,560
  solver-to-saved-scene comparisons;
- maximum baked position error is **0.000015182 m / 0.015 mm**;
- maximum baked orientation error is **0.068528°**;
- the maximum 240 Hz sample step is 44.691 mm; and
- captured-ball drops remain continuous.

The accepted trajectory SHA-256 is
`98d46617dfa4e093823314faf185065528d05e38291e370fef0481f44b02272c`.
Zero Bullet bodies is a tested architecture condition, not an omission.

## Camera and render evidence

The saved candidate defines 28 distinct cameras: 19 cinematic/environment
cameras and nine purpose-built pool-audit cameras. Six final pocket views in
`renders/pool_system_audit/` cover corner and side mouths from playing-surface,
top and underside angles. The pool-audit renderer can also reuse
`CAM_Table_ThreeQuarter_50mm` and `CAM_Rack_Detail_85mm` without increasing the
distinct-camera count.

The finished opening chapter contains 15 ordered 1600 × 900, 96-spp Cycles
frames in `renders/cinematic_stills/`. All 15 render from the same derived
candidate; the measured total is 2,941.5 seconds. The visual-only sequence is
live at `https://pool-table-test.netlify.app/`.

### Gameplay physics proof

`scripts/104_render_pool_physics_proof.py` defines six regenerated views in
`renders/physics_proof/`: rack setup, rack lift, cue contact, first rack impact,
opening spread and settled table. The render script uses the isolated
`GAMEPLAY` view layer so legacy static balls cannot appear with the gameplay
set. All six 1280 × 720, 48-spp Cycles frames and a contact sheet are present.
`reports/physics_render_timing.json` records a complete 336.6-second pass. The
six-frame contact sheet was inspected after the final orientation/camera/cue
rebake and is accepted as the current gameplay foundation evidence.

### Final environment close-audit review

All frames are Cycles, Metal GPU, 1600 × 900, 96 spp, AgX Medium High
Contrast, exposure -1.0.

| Camera | Acceptance |
|---|---|
| `CAM_Audit_Entrance_35mm` | pass — EXIT reads correctly; closer arms terminate at body/shoe; push rail connects to returns/latch; strike, hinges, threshold and lit egress path read |
| `CAM_Audit_BarWorkflow_45mm` | pass — shallow stock wall, register, open aisle, drainboard/glasses, sink, ice, garnish, soda gun, well rail and guest die read as separate connected systems |
| `CAM_Audit_FrontSeating_40mm` | pass — round/square tables and four mismatched chair constructions read in a localized practical pool |
| `CAM_Audit_Booths_45mm` | pass — both open pool-side mouths, face-to-face perpendicular benches, wall-cleated tables, distinct upholstery, seams and repair tape read without divider walls |
| `CAM_Audit_Lighting_35mm` | pass — low three-shade pool fixture and visible surrounding practicals explain the illumination hierarchy |
| `CAM_Audit_BoothPatina_60mm` | pass — close wear is restrained to fine cracking, small tears, narrow foam nicks, softened edges and repairs; seats remain usable and wiped |
| `CAM_Audit_CleanBar_50mm` | pass — guest top remains open and clean; eight whole fruits sit in one worn enamel bowl; current served glassware is distinct from caps, scraps or dirty abandoned empties |
| `CAM_Audit_PatronBarware_55mm` | pass — measured amber pint, faceted rocks glass, ice/lime/straw, dry coaster, fresh direct placement, hollow tip jar, 63 mm minimum guest-edge inset and physically seated fruit read as active tidy service |
| `CAM_Audit_StreetNeon_35mm` | pass — original wet-night street plate sits beyond the diamond glazing; car/shop color spill and street-facing OPEN neon create depth |
| `CAM_Audit_WallHistory_45mm` | pass — irregular paper history reads nearly flush to the wall without frame, pin or raised-tape shadows |
| `CAM_Audit_BathroomDoor_50mm` | pass — one dense flat sticker-bomb field, old hardware and a visible caged practical read as a functioning rear-door assembly |

Exact timings are in `reports/realism_render_timing.json`.

## Broad room/table review

Four refreshed environment frames and the retained table/rack checkpoints are
in `renders/checkpoints/`, all 1600 × 900 at 96 spp.

| Camera | Acceptance |
|---|---|
| `CAM_Hero_Entry_30mm` | pass — current 30 mm frame renders from the accepted candidate and closes the room sequence before the table views |
| `CAM_Table_ThreeQuarter_50mm` | pass — current candidate frame resolves the table construction, six pockets, low fixture and room context |
| `CAM_Rack_Detail_85mm` | conditional — render succeeds, but ball-number legibility remains below acceptance |
| `CAM_Bar_Reverse_35mm` | pass — bar depth, varied stools, supported bottle density, register workflow and diamond glazing read |
| `CAM_Environment_Wide_35mm` | pass — low pool fixture, booth strip, rear doors, pool clearance and perimeter furniture read |
| `CAM_FrontRoom_22mm` | pass — entrance hardware, EXIT/practicals, café seating, bottle wall and concrete traffic wear read |

Checkpoint timings are in `reports/render_timing.json`; current chapter timings
are in `reports/cinematic_stills_timing.json`.

## Purpose-built pool-audit views

The candidate adds `CAM_PoolAudit_Top_24mm`,
`CAM_PoolAudit_Corner_85mm`, `CAM_PoolAudit_Side_85mm`,
`CAM_PoolAudit_CornerTop_70mm`, `CAM_PoolAudit_SideTop_70mm`,
`CAM_PoolAudit_CornerUnderside_55mm`,
`CAM_PoolAudit_SideUnderside_55mm`,
`CAM_PoolAudit_Fixture_SideElevation` and
`CAM_PoolAudit_Fixture_ThreeQuarter_24mm`. They are the visual evidence surfaces
for the rebuilt table and fixture. The current corner and side views accept
static pocket construction only; they make no claim about later ball motion.
Geometry remains accepted independently by the 68-check pure-contract audit
and the 93-check evaluated-scene audit.

## Resolved findings

### Static pocket construction and visual proof accepted

Root cause was geometric: capped cylinders spanned the mouths. They are now
open U-shaped rail-top iron/welt assemblies with cloth-lined drops, dark leather
throats/baskets, mount ears, bolts, stitch runs and attached leather straps.
The visible sweeps are 210° at corners and 190° at sides; cushion jaws stop at
their capture-circle crossings. Evaluated facings, mouths, shelves, backdraft,
cap cuts, clear drops and 102 assembly contacts all pass. The six final corner,
side, top and underside views show smooth drafted cloth liners without the
former capped or ribbed/grille artifact. Dynamic capture and jaw rejection use
the exact 2D `SolverPocket` circles; the 3D `ShelfDrop` shelf/backdraft volumes
are construction only.

### Door hardware had no real operating logic

The unsupported vertical line is gone. The front leaf now has a horizontal
exit rail, returns, latch case, jamb strike, three hinges, threshold, closer
body, two connected arms, and shoe. An unmotivated interior key cylinder at the
glass edge was removed. The EXIT legend was reviewed from the actual interior
camera and corrected for reading direction.

### Stock, register, and furniture looked cloned

Back stock now uses seven silhouettes and support metadata rather than repeated
cylinders. The register moved from guest decoration to bartender workflow.
Four stools, four chair types, and two café tables now carry different
construction histories and non-surveyed loose placements. The booths are two
compact perpendicular wall bays entered from the pool aisle, not a parallel
banquette divided by false interior walls.

The final support pass reserved each bottle's full base radius around the
register-shelf opening. Two unsupported placements were removed, leaving 193
back-stock and eight working bottles; all 201 roots now fit their supports and
do not interpenetrate. A shallow upper display ledge was added beneath the old
radio, trophy, coffee tin and pickle jar.

### Bar had décor but no buildable bartender section

The former service counter and backbar shelf occupied almost the same plan
footprint. The guest rail was moved forward only inside the front zone and the
bar shortened before the cue rectangle. A shallow wall backbar now faces a
360 mm service counter across a measured 703 mm aisle. The visible service
sequence adds ice, well bottles/pourers, soda gun, garnish, sink, drainboard,
waste, mats, towel, opener/catcher, cooler and scoured metal wear.

### Small staging details lacked real supports

The fruit bowl profile now closes at its rotation axis and the bowl meets the
guest top. Five lower fruits meet the measured basin profile and three upper
fruits contact that cluster. Chalk cubes sit on their ledge, the first booth's
carved initials engage its tabletop finish, and each score rod now has two wall
plates and two brass spacers. Wall cues are checked for rack engagement rather
than incorrectly treated as wall-fastened objects.

### Added detail disappeared into black

The room remains dim, but entry, café, and booth practicals now expose the
construction and wear. No invisible film fill was added; every Blender light
has a visible fixture or modeled opening.

### Surface age started to read as filth

The final material and set-dressing pass separates housekeeping from fabric
age. Bar and patron tops are wiped and free of loose debris; current drinks are
actively served on dry coasters or one fresh direct placement, while older ring
evidence is pale finish loss rather than wet residue. Booth damage is fine and
localized. Floor and wall history is carried by cracks, chips, dry
discoloration, patched areas and traffic polish, with no litter or rotting food.

### Glassware had no human footprint

The two generic booth cylinders were removed. Ten seat-anchored assemblies now
use recorded pint and eight-sided rocks-glass envelopes, varied fill levels,
complete beverage/garnish components, support contact, coaster logic and
plausible reach. The solid-looking tip-jar cylinder was also rebuilt as an open
hollow jar with folded tips.

### Gameplay markings and shot dynamics were missing

The legacy static rack-detail checkpoint exposed the missing number treatment
but was never a gameplay scene. The new derived gameplay balls use unique
locally generated solid/stripe/number maps, opposed numerals, 6/9 underlines
and a cue-ball spin marker. A sourced deterministic event solver now carries
the physical profile, spin, ball/ball and cushion response, pocket capture and
control break. Exact transform F-curves provide Blender playback while keeping
the accepted static table and environment unchanged.

## Open findings

1. **Environment drift is now a hard failure.** Routine pool builds must keep
   `scripts/98_validate_environment_lock.py` green; do not rewrite the baseline
   to hide an accidental room change.
2. **The old static 85 mm rack checkpoint remains conditional.** Its legacy
   balls are intentionally untouched by the gameplay phase. The replacement
   gameplay maps pass asset/metadata checks, and the regenerated six-frame
   physics proof is the accepted gameplay evidence.
3. **A complete rules-driven match remains future work.** This phase accepts
   deterministic motion, spin, capture and one control-break fixture; it does
   not yet implement turns, fouls, shot selection or multi-shot game state.
4. **4K PNG/EXR and 6K hero finals remain unrendered.**
5. **The EEVEE sweep needs a new parity test** after the practical-light pass.
