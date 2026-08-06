# NYC Dive-Bar Pool Room

Photoreal Blender 5.2 environment: a fictional prewar Lower East Side
neighborhood bar with a custom, unbranded, 9-foot six-leg slate pool table as
the hero. The frozen environment and accepted static table now support a
derived deterministic gameplay scene with marked balls, cue/rack setup, a
control break, spin, pocket capture and solver-to-Blender playback validation.

## Scoped pool rebuild and gate

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_master.blend -P scripts/23_rebuild_pool_system.py
```

The scoped rebuild reads the frozen environment master and writes
`blend/poolroom_pool_rebuild_preview.blend` by default. It is the routine pool
iteration path. `scripts/build_all.py` remains the deterministic full-environment
reconstruction and should not be used merely to update the derived pool preview.
The gates exit nonzero if geometry, realism, or the approved environment
fingerprint fails:

- `reports/pool_geometry_contract_audit.json`: **68/68 pure geometry-contract
  checks pass**; source SHA-256
  `afe868b3788218f0ba29dbe9d5caee81157c088b2b7fbbb00ed5f2faf89f04ad`.
- `reports/dimension_audit.json`: **93/93 static dimension and construction
  checks pass**.
- `reports/object_realism_audit.json`: **33/33 realism contracts pass** across
  **2,317 render-visible components** grouped into **1,064 logical real-world
  items**.
- `reports/environment_staging_audit.json`: **14/14 staging contracts pass**;
  all **333 high-risk logical items** have explicit support/placement evidence.
- `reports/environment_lock.json`: **PASS** — 2,223 frozen environment objects,
  82 materials, and eight image assets match the approved baseline.
- `reports/pool_system_lock.json`: **PASS** — 355 pool-system objects and 30
  materials match the accepted static table/ball/proxy baseline (re-banked
  2026-08-06 with the R1 register-bay revision).

The approved environment and the current pool candidate have distinct roles:

- `blend/poolroom_master.blend` is the frozen environment baseline.
- `blend/poolroom_pool_rebuild_preview.blend` is the derived static pool
  candidate; routine pool work must not overwrite the master.
- `blend/poolroom_gameplay_preview.blend` is derived from that accepted static
  candidate and contains the new balls, cue, rack and baked transforms in
  `11_GAMEPLAY`, plus gameplay cameras and the `GAMEPLAY` view layer.

Scoped pool rebuild and saved-candidate checks:

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/90_validate_scene.py
/Users/davidmarsh/Desktop/Pool\ Table\ Test/.venv/bin/python scripts/91_validate_pool_geometry_contract.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/95_audit_realism.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/96_audit_environment_staging.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/98_validate_environment_lock.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/99_bank_pool_system_lock.py
```

## Current state

| Area | Status |
|---|---|
| Room shell | done — swept but heavily worn concrete, aged plaster, pressed tin, green wainscot, conduit, three constructed cross beams, diamond storefront, three constructed door assemblies |
| Pool table | static construction and current visual proof pass — 296 table meshes plus one root, six crafted rail caps, twelve cap horns, 18 flush sights, complete frame/load paths, and six complete pocket drops; the separate gameplay layer leaves this accepted baseline unchanged |
| Pool light | done — low movable three-shade green-enamel fixture, 40 in above bed / 1.778 m above floor |
| Working bar | done — physical shallow-backbar/service-counter section, 703 mm aisle, 193 supported back-stock bottles, eight poured well bottles, ice/soda/garnish, sink, drainboard, waste, cooler, taps, mats, opener/catcher, bartender-facing register, supported display oddments, and a clean open guest top with eight physically nested whole fruits and barware bases at least 63 mm inside the guest edge |
| Seating | done — four distinct stools, two different café tables, four chair types, two wall-adjacent face-to-face booth bays with open pool-side entry |
| Patron service | done — ten seat-reachable active drinks: five measured pint beers and five measured faceted rocks cocktails with ice/lime/straw; nine served coasters, one direct fresh-condensation placement, one dry away setting/open tab; no dirty abandoned glassware or food waste |
| Set dressing/patina | done — flat wheat-paste art, three layered paper-history fields, flat bathroom sticker bomb, restrained booth cracks/tears, current coasters over old tabletop ring ghosts, cues, score beads, darts, payphone, CRT, coats, notes and 18 small story details |
| Lighting/street | done — 25/25 sources motivated by visible fixtures, neon assemblies or modeled openings; original wet-night LES street plate behind diamond glazing |
| Environment freeze | done — core room collections are unselectable and machine-fingerprinted; non-pool lighting/materials/assets/global color state are guarded; pool systems remain editable |
| Evidence | 28 distinct cameras — 19 cinematic/environment cameras plus nine purpose-built pool-audit cameras; six final corner/side pocket views cover playing-surface, top and underside angles |
| Opening chapter | done — 15 ordered 1600 × 900 Cycles stills in `renders/cinematic_stills/`; visual-only gallery live at `https://pool-table-test.netlify.app/` |
| Physics/gameplay | foundation passes — Pooltool 0.6.0 deterministic event solver, 16 marked 57.15 mm / 0.168 kg balls, explicit slide/roll/spin and collision profile, legal tight 8-ball rack, 58 in cue, 24 mph control break, pocket capture and baked quaternion/location playback; zero Blender rigid bodies intentionally |
| Physics validation | `reports/physics_validation.json` 15/15 PASS; `reports/physics_playback_audit.json` 216/216 PASS across 24,560 saved-scene sample comparisons, with 0.015 mm maximum position error and 0.069° maximum orientation error |
| Physics visual proof | accepted — six regenerated 1280 × 720, 48-spp Cycles frames and contact sheet in `renders/physics_proof/`; `reports/physics_render_timing.json` records 336.6 s |
| Final 4K/EXR delivery | not started |
| Sweep film | existing EEVEE render is stale after the environment relight |

## Project structure

`scripts/config.py` owns project dimensions and documented design decisions.
`assets/data/table_wpa_geometry.json` owns the shared solver/render cushion,
jaw and pocket geometry contract. Its accepted SHA-256 is
`afe868b3788218f0ba29dbe9d5caee81157c088b2b7fbbb00ed5f2faf89f04ad`.
Evaluated mouths are 115.8875 mm at corners and 128.5875 mm at sides, the WPA
range midpoints; cuts are 142° and 103.997691°, shelves are 41.275 mm and
4.7625 mm, and the modeled 13.5° backdraft is within the WPA 12–15° range.
Visible jaws stop at the capture-circle crossings. Open U-shaped iron/welt
assemblies use 210° corner and 190° side visible sweeps. Values prefixed `DD_`,
plus the explicitly documented `CLOTH_T` choice, are project decisions rather
than manufacturer or WPA specifications; see `docs/DESIGN_DECISIONS.md`.

The hidden `10_PHYSICS_PROXIES` collection contains 42 diagnostic objects. Six
`PTX_SolverPocket_*` objects are the exact 2D capture circles used by Pooltool;
six `PTX_ShelfDrop_*` objects describe the 3D shelf/backdraft construction only.
The remaining 30 objects represent 18 linear and 12 arc contacts. None is a
Blender rigid body.

`scripts/98_validate_environment_lock.py` protects the approved room while the
pool phase proceeds. Do not use its `--write` mode unless an environment change
has been explicitly reviewed and approved; routine builds only verify.

The benchmark GLB remains in `99_REFERENCE_LOCKED`, hidden, unselectable, and
excluded from every view layer. Attribution is in `docs/ATTRIBUTION.md`.

## Deterministic gameplay workflow

The physics source of truth is `assets/data/pool_physics_profile.json` and the
shared static collision geometry remains
`assets/data/table_wpa_geometry.json`. Pooltool solves events in float64; the
authoritative 240 Hz trajectory export is then baked into Blender location and
quaternion F-curves. Its current trajectory SHA-256 is
`98d46617dfa4e093823314faf185065528d05e38291e370fef0481f44b02272c`.
Pooltool's capture test is a continuous 2D pocket-circle crossing; the modeled
3D shelf and backdraft are construction geometry, not solver triggers. Blender
Bullet is deliberately not involved, so zero rigid bodies remain intentional.

```bash
/Users/davidmarsh/Desktop/Pool\ Table\ Test/.venv/bin/python scripts/make_game_ball_decals.py
/Users/davidmarsh/Desktop/Pool\ Table\ Test/.venv/bin/python scripts/100_validate_pool_physics.py --repeat 10
/Users/davidmarsh/Desktop/Pool\ Table\ Test/.venv/bin/python scripts/101_export_pool_shot.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_pool_rebuild_preview.blend -P scripts/102_bake_pool_playback.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_gameplay_preview.blend -P scripts/103_validate_pool_playback.py
/Applications/Blender.app/Contents/MacOS/Blender -b blend/poolroom_gameplay_preview.blend -P scripts/104_render_pool_physics_proof.py -- --engine cycles --samples 48 --width 1280 --height 720
```

Scripts `100`–`104` respectively validate the event model, export the control
break, build the derived gameplay blend, audit solver/playback parity and
render six proof frames. The ball textures and their manifest live in
`assets/textures/balls_game/` and `assets/data/game_ball_markings.json`.

Start with:

- `HANDOFF.md` — current state, evidence, open work, and next action.
- `docs/REALISM_AUDIT.md` — per-object/per-assembly audit method and findings.
- `docs/ENVIRONMENT_RESEARCH.md` — Lower East Side construction and dive-bar
  research, with inference boundaries.
- `docs/QA_REPORT.md` — automated and rendered acceptance results.
- `docs/DESIGN_DECISIONS.md` — separation between published dimensions,
  calibrated gameplay coefficients and presentation-only choices.
- `docs/ATTRIBUTION.md` — model, document, solver and physics-study provenance.
