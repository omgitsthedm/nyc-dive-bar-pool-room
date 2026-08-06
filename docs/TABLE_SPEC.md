# Table Specification — as built and measured

All values below are **measured from the derived static pool geometry** in
`blend/poolroom_pool_rebuild_preview.blend` by
`scripts/90_validate_scene.py`, not restated from the config. Full
machine-readable results: `reports/dimension_audit.json` (93/93 PASS). The pure
geometry contract also passes 68/68 checks in
`reports/pool_geometry_contract_audit.json`. Its accepted source SHA-256 is
`afe868b3788218f0ba29dbe9d5caee81157c088b2b7fbbb00ed5f2faf89f04ad`.
The approved environment baseline remains frozen in
`blend/poolroom_master.blend`.

| Property | Target | Measured | Source |
|---|---|---|---|
| Playing surface width | 1.2700 m / 50 in | **1.270000 m** | WPA |
| Playing surface length | 2.5400 m / 100 in | **2.540000 m** | WPA |
| Exterior width | 1.5494 m / 61 in | **1.549400 m** | Olhausen Cavalier |
| Exterior length | 2.8194 m / 111 in | **2.819400 m** | Olhausen Cavalier |
| Floor to playing surface | 0.7620 m / 30 in | **0.762000 m** | Olhausen dim sheet |
| Floor to rail top | 0.8001 m / 31.5 in | **0.800100 m** | Olhausen dim sheet |
| Slate thickness | 0.0254 m / 1 in | **0.025400 m** | Olhausen (3-piece) |
| Slate pieces | 3 | **3** | Olhausen |
| Cushion nose above bed | 35.719–36.862 mm | **36.290 mm** | WPA range, 63.5% of ball dia |
| Ball diameter | 57.15 mm | **16/16 within 0.1 mm** | WPA |
| Ball uniform scale | (1,1,1) | **16/16** | brief sec.11 |
| Rack apex over foot spot | ≤ 0.5 mm | **0.000000 m** | WPA |
| Min rack centre spacing | ≥ 57.05 mm | **57.150 mm** | tangent rows |
| Rigid bodies | 0 | **0** | brief sec.21 |

## Pocket geometry (shared contract, evaluated mesh)

| Property | Target | Measured |
|---|---:|---:|
| Corner mouth | WPA 114.300–117.475 mm; midpoint 115.8875 mm | **115.8875 mm** |
| Side mouth | WPA 127.000–130.175 mm; midpoint 128.5875 mm | **128.5875 mm** |
| Corner jaw cut | 142.000° | **142.000°** |
| Side jaw cut | 104.000° | **103.997691°** |
| Pocket backdraft | WPA 12–15° | **13.5° modeled** |
| Corner shelf | 41.275 mm | **41.275 mm** |
| Side shelf | 4.7625 mm | **4.7625 mm** |
| Facing thickness | 3.175 mm | **3.175 mm** |

The cushion, jaw and pocket plan contract is
`assets/data/table_wpa_geometry.json`; project dimensions and design decisions
remain in `scripts/config.py`. The evaluated mouths, rather than a second set of
documentation-only values, are the acceptance evidence.

Pooltool 0.6.0 uses each pocket's continuous 2D capture circle. The modeled 3D
shelf and backdraft establish static construction only; they are not solver
capture conditions.

## Static construction evidence

- Rail finish: six separately crafted caps and 18 flush inlaid sights.
- Frame: two long sills, two end sills, eight cross-sill halves and one centre
  beam; 21 frame/leg manifold solids, six continuous load paths and 18 rail
  studs.
- Side-pocket apron relief: 220 mm wide × 125 mm deep.
- Six pocket drops: 12 cloth-covered facings, six cloth liners, six leather
  throats, six open U-shaped iron/welt assemblies, six leather skirts, six
  stitch runs, 12 mount ears, 12 mount bolts, 18 leather straps and rivets, six
  baskets, six basket bases and six serviceable rail caps.
- The visible iron/welt assemblies sweep 210° at corners and 190° at sides; the
  recessed iron extends 10° beyond the welt for its two mounting ears.
- Visible cushion jaws terminate at their capture-circle crossings.
- Pocket clearance: zero hidden-wood/apron collisions and 102 verified assembly
  attachment contacts.

## WPA flatness — metadata only

Recorded in the audit JSON, **not simulated**: lengthwise 0.508 mm,
widthwise 0.254 mm, joints coplanar 0.127 mm, centre deflection 0.762 mm.
The static mesh is mathematically flat.

## Component inventory

The static table contains **284 meshes plus one non-rendering `PT_TableRoot`
assembly empty**:

- `02_TABLE_VISIBLE`: 109 meshes.
- `03_TABLE_ENGINEERING`: 175 meshes plus `PT_TableRoot`.

The separate `10_PHYSICS_PROXIES` collection contains **42 hidden diagnostic
objects**: 30 meshes and 12 curves. They split into 18 linear contacts, 12 arc
contacts, six exact 2D `PTX_SolverPocket_*` capture circles and six static 3D
`PTX_ShelfDrop_*` construction volumes. The `SolverPocket` objects match the
Pooltool capture test; the `ShelfDrop` objects are not solver triggers. None is
a renderable table component or rigid body. The hero-prop collection separately
adds 16 balls; there is no rendered triangle rack in the static candidate.
