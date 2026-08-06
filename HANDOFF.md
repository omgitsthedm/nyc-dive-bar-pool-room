# Handoff — NYC Dive-Bar Pool Room

**Updated:** 2026-08-05

**Project root:** `/Users/davidmarsh/Desktop/Pool Table Test/nyc-dive-bar-pool-room`

**Frozen environment master:** `blend/poolroom_master.blend`

**Current derived pool preview:** `blend/poolroom_pool_rebuild_preview.blend`

**Current derived gameplay preview:** `blend/poolroom_gameplay_preview.blend`

**Blender:** 5.2.0 LTS (`/Applications/Blender.app/Contents/MacOS/Blender`)

## Objective

Build a convincing, worn Lower East Side neighborhood dive-bar pool room, then
use that environment for a later demonstration of an actual pool game with
correct physics. The visual direction borrows only broad qualities—warmth,
clutter, diamond glazing, social wear—from a classic animated tavern. All
signage, art, layout, brands, people, and geometry are original or fictional.

## Current state

The detailed environment/realism pass is complete and frozen in the master.
The accepted static pool-system rebuild lives in its derived preview, and the
new deterministic gameplay system lives in a second derived preview. This
keeps both approved source states unchanged while physics and playback are
evaluated independently:

- **68/68 pure geometry-contract checks and 93/93 evaluated Blender
  dimensional/static-construction checks pass.**
- The current environment reports pass **33/33 realism contracts** and **14/14
  physical-staging contracts** across **2,317 render-visible components**
  grouped into **1,064 logical real-world items**.
- **321 high-risk logical items** have explicit support/placement evidence.
- **2,116 environment objects, 80 materials, and eight image assets** match the
  approved environment fingerprint in `reports/environment_lock.json`.
- **355 pool-system objects and 30 materials** match the accepted static
  table/ball/proxy fingerprint in `reports/pool_system_lock.json`
  (`1b4e3397398477e0…`, banked 2026-08-05 after the pocket-mouth revision).
- The source-backed Pooltool suite passes **15/15 deterministic physics
  contracts**, including sliding-to-roll transition, rolling resistance,
  ball/ball and ball/cushion response, draw/stop/follow, pocket acceptance and
  rejection, continuous collision detection, a control break, sample-rate
  invariance and ten-run repeatability.
- The derived Blender gameplay scene passes **216/216 playback contracts** with
  zero Blender rigid bodies, all 16 marked gameplay balls, cue and rack
  assemblies, solver/profile identity, continuous pocket drops and maximum
  solver-to-F-curve parity errors of **0.015 mm position** and **0.069°
  orientation**.
- `blend/poolroom_master.blend` and `reports/environment_lock.json` remain
  unchanged protected artifacts.  `reports/pool_system_lock.json` was
  deliberately re-banked for the reviewed 2026-08-05 pocket revision; the
  derived previews were regenerated from the untouched master.
- The ordered 15-shot opening chapter is rendered at 1600 × 900 and is live as
  a visual-only gallery at `https://pool-table-test.netlify.app/`.

| Area | Current construction |
|---|---|
| Room | swept but heavily worn concrete with located cracks, chips, old patches and dry discoloration; deep-green wainscot; aged plaster; pressed tin; three constructed prewar cross beams; surface services; diamond storefront; front/service/restroom openings |
| Pool table | static construction and current visual proof accepted in the derived static preview: 284 table meshes plus `PT_TableRoot`; six crafted rail caps, 18 flush sights, complete frame/load paths, and six complete pocket drops pass the 68-check geometry and 93-check evaluated-scene gates; the gameplay scene adds its balls, cue and rack without changing this baseline |
| Pool light | classic three-shade enamel fixture on paired chains; shade bottom 40 in above bed / 1.778 m above floor |
| Bar | shallow wall backbar, 703 mm working aisle, scarred paneling, desilvered mirrors, 193 supported back-stock bottles in seven families, eight open well bottles with pourers, ice well, soda gun, garnish station, utility sink, drainboard, waste, cooler, taps, mats, towel, opener/catcher, register, a supported upper display ledge for retained oddments, and a deliberately clean/open guest top with eight physically nested whole fruits in a physically seated old enamel bowl and a hollow repurposed tip jar |
| Register | early mechanical form on the back-bar work surface, facing bartender, with real shelf opening, drawer, key deck, 28 keys, indicators, feet, trim, and connected crank |
| Seating | four different stool acquisitions, two different café tables, four chair types, and two compact wall-adjacent face-to-face booth bays entered from the pool aisle |
| Patron footprint | ten active, seat-reachable drinks: five measured 16 oz pint/mixing glasses with amber beer and restrained foam, five measured faceted 10 oz rocks glasses with cocktail, ice, lime wheel and straw; nine served coasters, one direct fresh-condensation placement, and one dry away-place setting/open tab; every bar base is at least 63 mm inside the guest edge |
| Doors | front exit rail/latch/strike/hinges/threshold/connected closer; distinct service lever and restroom knob; no unsupported vertical pull |
| Art/history | eight original generated raster assets; primary wall art and three large paper-history fields sit flush like old wheat-paste with no frames/pins/raised tape; restroom door carries one dense flat sticker-bomb layer; cues, coats, payphone, CRT, score beads and darts remain physical props |
| Lighting/street | 25/25 Blender lights motivated by a visible practical, neon assembly, or modeled opening; low pool fixture, entry/café/booth pools, bathroom-door cage light, two generic neons, tail-light streak and opposite-shop spill; original nighttime LES street plate behind the diamond glazing |
| Cameras | 28 distinct cameras: 19 cinematic/environment cameras plus nine purpose-built pool-audit cameras |
| Environment freeze | architecture, bar, set dressing, patina, patron service, non-pool lights, their materials/assets, and global color state are fingerprinted in the frozen master; table, pool lights, balls, cameras and pool atmosphere remain editable only in the derived pool/gameplay previews |
| Physics/gameplay | implemented in `blend/poolroom_gameplay_preview.blend`: Pooltool 0.6.0 is the external deterministic event authority; 16 regulation-size, 0.168 kg phenolic-resin balls use generated solid/stripe/number markings and a red cue-ball spin reference; a legal tight 8-ball rack, 58 in cue, 24 mph control break, spin response and pocket capture are solver-tested and baked to exact location/quaternion F-curves; zero Blender rigid bodies remain intentionally |

The floor plan is a fictional but evidence-led interpretation of an adapted
tenement storefront: a working bar confined to the front west side, small
tables and two open-ended booth bays compressed to the perimeter, a clear entrance path, a pool zone
with no set-dressing intrusion into its nominal cue envelope, and service depth
implied behind the rear wall. Research and inference limits are documented in
`docs/ENVIRONMENT_RESEARCH.md`.

## Key realism corrections

### Pocket mouths (2026-08-05 revision)

The reported defect was real: each jaw was upholstered as a flared wedge
whose sharp end pointed at the playfield, so the mouths read as V shapes
coming out of the rails, and a full-width outboard rectangle amputated the
cap wood around every ring.  The revision makes the construction match the
WPA drawing and the photo references: the cloth is now a constant-width band
that turns off the rail and follows the jaw cut into the mouth; twelve exact
walnut cap horns continue the boards along the jaw cuts down to the iron;
the only wood removed around each ring is a circular seat
(welt outer radius + 1.5 mm); and the side irons' mount lugs reach outward
under that wood.  Solver jaw lines, mouths, shelves and the physics contract
are unchanged — the trajectory hash is identical before and after.

### Front door

The former vertical line had no returns, latch, strike, or real-world function.
It was replaced by a horizontal narrow-stile exit rail with two returns, latch
case, fixed jamb strike, three hinges, threshold, and connected two-arm surface
closer. An interior cylinder that sat at the glass edge without a mechanism was
removed. A fixed illuminated EXIT sign and schoolhouse globe make the occupied
path legible without flattening the bar's low-light character.

### Bottles, bar workflow, and register

The old repeated cylinders became seven real bottle silhouettes with varied
height, material, label, orientation, and gaps. Every one of the 193 back-stock
bottle bottoms measures within 2 mm of its recorded shelf support. All eight
working bottle bottoms also meet the mounted speed rail within 2 mm, and every
working bottle has a fitted speed pourer. The rail is part of an ice/well/soda/
garnish cluster opposite the shallow stock wall. A measured 703 mm aisle now
separates that service counter from the backbar; the former overlapping plan
footprints are gone. The sink, drainboard, trash, towel, mats, opener/catcher,
cooler and taps complete the visible shift workflow. The old register is
bartender equipment on a real backbar surface rather than guest-rail décor.

### Furniture and accumulated history

The four bar stools now represent round oak, vinyl tube-back, square wood, and
pedestal swivel-back acquisitions, with different pulls and yaws. The two café
tables and four chairs are different constructions and placements. The two
booths now have benches running perpendicular to the west wall, patrons facing
one another across each table, and open east ends for entry from the pool aisle.
There are no freestanding booth dividers; the nearest booth component remains
240 mm outside the cue envelope. The bays differ in age, upholstery, seams,
fine vinyl cracking, small tears, exposed-foam nicks, hand wear and restrained
repairs. Primary wall graphics are nearly flush wheat-paste rather than framed
decor; cords, braces and fixtures still meet their real supports.

The cleanliness rule is explicit: active service is present, but there are no
apple cores, food waste, loose bar caps, dirty abandoned glassware, sticky
puddles, or grimy customer tabletops. Ten current drinks sit on nine coasters
plus one fresh direct bar placement, while one dry coaster and open tab imply a
patron at the pool table. Patron tables remain wiped beneath the serviceware and
retain pale ring ghosts, fine scratches and softened finish from decades of
older unprotected drinks. Age is embedded across 38 used material families
instead of applied as one uniform dirt layer.

The full per-object/per-assembly method is in `docs/REALISM_AUDIT.md` and its
machine-readable inventories are `reports/object_realism_audit.json` and
`reports/environment_staging_audit.json`. The final staging pass caught and
corrected a 6 mm floating fruit bowl, unsupported upper-backbar oddments, chalk
in front of its shelf, carved initials beyond their tabletop, score rods with
no wall hardware, and two bottle footprints spanning the register-shelf gap.

## Static pool-table status

The pool system now uses one shared cushion/jaw/pocket contract from
`assets/data/table_wpa_geometry.json`, with project dimensions and design
decisions in `scripts/config.py`. Its accepted source SHA-256 is
`afe868b3788218f0ba29dbe9d5caee81157c088b2b7fbbb00ed5f2faf89f04ad`.
Evaluated sharp-line mouths are **115.8875 mm at corners** and **128.5875 mm at
sides**, the midpoints of the WPA permitted ranges. Jaw cuts measure 142.000°
at corners and 103.997691° at sides. The modeled backdraft is 13.5° within the
WPA 12–15° range; facings are 3.175 mm. Shelves are 41.275 mm at corners and
4.7625 mm at sides.

All six pockets have 12 cloth-covered facings, six cloth liners, six leather
throats, six open U-shaped iron/welt assemblies, six leather skirts, six stitch
runs, 12 mount ears, 12 mount bolts, 18 leather straps and rivets, six baskets,
six basket bases and six serviceable rail caps. The visible welt sweeps are
210° at corners and 190° at sides; each recessed iron extends 10° farther for
its two mounting ears. Visible cushion jaws end at their capture-circle
crossings instead of extending into the pocket opening. The validator records
zero hidden-wood/apron collisions and 102 required attachment contacts.

Pooltool 0.6.0 captures a ball when its center crosses the continuous 2D pocket
circle. The six exact `PTX_SolverPocket_*` proxies represent those solver
circles. The six `PTX_ShelfDrop_*` proxies represent the 3D shelf/backdraft
construction only and are not solver triggers. Pocket acceptance, jaw rejection
and continuous animated drops are tested separately by the derived gameplay
solver and playback gates.

## Original generated environment art

Eight raster assets were created with OpenAI image generation in built-in mode:

- `assets/textures/wall_art/payphones_1988.png`
- `assets/textures/wall_art/tuesday_8ball_1993.png`
- `assets/textures/wall_art/sticker_wall_1982_1999.png`
- `assets/textures/wall_art/pool_team_1986.png`
- `assets/textures/wall_art/memory_wall_1978_1998.png`
- `assets/textures/environment/bathroom_sticker_bomb_v2.png`
- `assets/textures/environment/wheatpaste_wall_history_v2.png`
- `assets/textures/environment/les_night_street_v2.png`

The three newest prompts requested a dense but generic 1980s/1990s bathroom
sticker field, an irregular decades-old wheat-paste paper wall, and a wet
Lower East Side nighttime streetscape with blurred traffic and fictional small
businesses. They exclude real logos, celebrities, copyrighted characters and
readable brands. Exact hashes, byte sizes and generation provenance are
recorded in `docs/SOURCE_MANIFEST.md` and `reports/asset_manifest.json`.

## Rebuild and evidence

```bash
# Full environment reconstruction; not a routine pool-iteration command.
/Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/build_all.py

# Scoped pool rebuild. By default this reads the frozen master and writes the
# derived preview; it does not overwrite the master.
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_master.blend -P scripts/23_rebuild_pool_system.py

# Current static candidate checks.
/Users/davidmarsh/Desktop/Pool\ Table\ Test/.venv/bin/python scripts/91_validate_pool_geometry_contract.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/90_validate_scene.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/95_audit_realism.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/96_audit_environment_staging.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/98_validate_environment_lock.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/99_bank_pool_system_lock.py

# Deterministic gameplay profile, trajectory and Blender bake.
/Users/davidmarsh/Desktop/Pool\ Table\ Test/.venv/bin/python scripts/make_game_ball_decals.py
/Users/davidmarsh/Desktop/Pool\ Table\ Test/.venv/bin/python scripts/100_validate_pool_physics.py --repeat 10
/Users/davidmarsh/Desktop/Pool\ Table\ Test/.venv/bin/python scripts/101_export_pool_shot.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/102_bake_pool_playback.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_gameplay_preview.blend -P scripts/103_validate_pool_playback.py

# Six-frame visual proof; this does not modify the saved gameplay blend.
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_gameplay_preview.blend -P scripts/104_render_pool_physics_proof.py -- --engine cycles --samples 48 --width 1280 --height 720
```

The full build checks the existing lock and exits nonzero on drift. The
environment-lock `--write` mode is reserved for an explicitly approved future
environment revision; it is not part of routine pool development. Passing an
explicit `--output` to the scoped pool rebuild changes its destination, so the
default derived-preview path is the safe routine choice.

- `reports/pool_geometry_contract_audit.json`: 68 passed, 0 failed; accepted
  geometry source SHA-256
  `afe868b3788218f0ba29dbe9d5caee81157c088b2b7fbbb00ed5f2faf89f04ad`.
- `reports/dimension_audit.json`: 93 passed, 0 failed.
- Current derived-preview inventory: 2,317 render-visible components and 1,064
  logical items. The realism and staging reports record these current totals;
  all 321 high-risk items pass their support/placement checks.
- `reports/environment_lock.json`: locked baseline; 2,116 objects, 80 materials,
  eight assets; aggregate SHA-256
  `c025578c2a74fd0761fad9c327f201b0b78c75ef4c5ebbcedabfdd98ce292fe5`.
- `reports/pool_system_lock.json`: locked static pool baseline; 355 objects, 30
  materials; aggregate SHA-256
  `1b4e3397398477e0d70855e48329a1b4b30795477b7d07f5ebd14ddbb5bc0930`.
  Fresh read-only checks against `blend/poolroom_gameplay_preview.blend` pass
  both locks: all 2,116 environment objects and all 355 static pool objects are
  unchanged.
- `assets/data/pool_physics_profile.json`: pinned Pooltool 0.6.0 resolver,
  physical profile, cue/rack setup, source links and deterministic control-break
  contract. `assets/data/shots/break_control.json` is the solver-authoritative
  240 Hz playback trajectory.
- `reports/physics_validation.json`: **15/15 PASS**; ten fresh control-break
  systems produce one canonical hash. The control break starts the cue ball at
  10.73 m/s (24.0 mph), disperses 14 object balls by more than 150 mm, sends
  11 object balls to a rail or pocket and pockets the 7 ball.
- `reports/physics_playback_audit.json`: **216/216 PASS**; 16 gameplay balls,
  zero Blender rigid bodies, legal rack, exact cue contact/speed, independently
  hashed marked-ball materials, every 240 Hz/event F-curve key and 24,560
  solver-to-Blender position/orientation comparisons.
  Trajectory SHA-256 is
  `98d46617dfa4e093823314faf185065528d05e38291e370fef0481f44b02272c`;
  saved gameplay blend SHA-256 is
  `ca67536024f1b067f763f9b9ac18ce73cbacaf195ada2c9f464712c7217e341f`.
- `renders/physics_proof/`: six 1280 × 720, 48-spp Cycles gameplay evidence
  frames plus a contact sheet, regenerated after the pocket revision.
  `reports/physics_render_timing.json` records the complete 336.6-second pass;
  the final contact sheet has been visually accepted.
- Table inventory: 109 meshes in `02_TABLE_VISIBLE`; 175 meshes and one
  `PT_TableRoot` empty in `03_TABLE_ENGINEERING`.
- Static frame: two long sills, two end sills, eight cross-sill halves and one
  centre beam; 21 frame/leg manifold solids, six verified load paths and 18
  rail studs.
- Six crafted rail caps, 18 flush sights, six complete pocket drops and 102
  verified pocket attachment contacts.
- `10_PHYSICS_PROXIES`: 42 hidden diagnostic objects: 18 linear contacts, 12
  arc contacts, six exact 2D `SolverPocket` capture circles and six static 3D
  `ShelfDrop` construction volumes; rigid bodies: zero intentionally.
- Set-dressing intrusions into nominal cue envelope: zero.
- Constructed door assemblies: three.
- Back stock: 193 supported bottles in seven families; eight working bottles
  with pourers.
- Motivated Blender lights: 25/25.
- Flush primary art: 4/4; forbidden frames, pins and raised tape: zero.
- Booth wear: both bays; 36 explicit restrained crack/tear/foam/hand-wear components.
- Current service: ten active drinks (five pints/five rocks), all support- and
  reach-checked; ten dry coasters total, one intentional direct placement and
  one dry away-place setting.
- Wiped patron tables: 14 pale historical ring ghosts and 10 fine scratches
  remain beneath current serviceware.
- Guest bar top: zero legacy debris; five lower fruits seated below the bowl
  rim, three upper fruits contacting that cluster, three active drinks inset at
  least 63 mm from the guest edge, and one open tab.
- Paper-history fields: three; constructed cross beams: three; subtle story components: 18.
- Missing external files, rigid bodies, and stray startup objects: zero.
- Camera inventory: 28 distinct cameras (19 cinematic/environment + nine pool
  audit). The pool-audit renderer can also reuse the table three-quarter and
  rack-detail cameras without increasing that distinct-camera count.
- Six final pocket views in `renders/pool_system_audit/` cover corner and side
  mouths from playing-surface, top and underside angles.
- Four refreshed 1600 × 900, 96-spp Cycles environment frames plus the retained
  table/rack checkpoints: `renders/checkpoints/`.
- Six refreshed 1600 × 900, 96-spp close patina/service proof frames plus
  the earlier assembly audits: `renders/realism_audit/`.
- Timing: `reports/render_timing.json` and
  `reports/realism_render_timing.json`.
- Fifteen ordered 1600 × 900, 96-spp Cycles chapter frames:
  `renders/cinematic_stills/`; total measured render time 2,941.5 seconds in
  `reports/cinematic_stills_timing.json`.

## Remaining work and risks

1. **The environment is now a protected baseline.** Pool-phase work must leave
   `reports/environment_lock.json` passing. Deliberate environment revisions
   require an explicit review and `--write`; never regenerate the baseline just
   to silence drift.
2. **The static pool system is now a protected baseline.** Physics-phase work
   must leave `reports/pool_system_lock.json` passing or deliberately replace
   it only after a reviewed table/ball/proxy change.
3. **Gameplay visual proof is accepted.** The gameplay scene, solver suite and
   playback audit pass, and all six 48-spp Cycles frames plus their timing
   report have been visually reviewed as the current foundation evidence.
4. **This is a deterministic control-break foundation, not yet a complete
   rules-driven match.** Shot selection, turn/foul/rules state, multi-shot game
   sequencing and final camera choreography remain later phases.
5. **Final 4K PNG/EXR and 6K hero delivery are not rendered.** Current 1600 ×
   900 evidence is suitable for environment approval, not final delivery.
6. **The existing 288-frame EEVEE sweep is visually stale.** Its hard-coded
   exposure and light boost predate this practical-light network.
7. This is a plausible visualization, not an NYC permit/accessibility/fire/
   health-code certification.
8. The production gallery is deployed. No Git commit or push was made.

## Next action

Extend the accepted deterministic break foundation into a rules-aware
multi-shot game sequence. Add shot selection, turn/foul state and final camera
choreography while keeping both protected source locks green.
Keep the environment and static pool-system locks green unless a reviewed
change is intentional.
