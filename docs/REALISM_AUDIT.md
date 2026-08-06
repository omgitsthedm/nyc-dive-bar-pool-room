# Realism Audit — Object and Assembly Pass

**Date:** 2026-08-05

## Outcome

The room now passes three scene-quality layers plus an environment freeze:

- **90/90 dimensional and static-construction checks** for table geometry,
  pockets, frame/load paths, balls, clearance,
  room construction, asset integrity, and render hygiene.
- **33/33 realism contracts** for door operation, bottle support/profile
  variety, stool acquisition/placement variety, booth orientation/access,
  bartender workflow/aisle construction, register placement, light motivation,
  flush paper history, restrained upholstery damage, measured current barware,
  seat reach/support/coaster logic, clean/worn hospitality surfaces, aged
  structural fabric, street/neon context and small story detail.
- **14/14 physical-staging contracts** covering finite geometry, materials,
  scene bounds, support/contact, containment, furniture uniqueness, bottle
  footprint/clearance and the absence of premature rigid bodies.
- `reports/environment_lock.json` freezes 2,116 environment objects, 80 used
  materials, eight image assets, non-pool lights and global color state.

`reports/object_realism_audit.json` inventories **2,317 render-visible component
objects** and groups them into **1,064 logical real-world items**. This prevents a
three-part bottle, a 28-key register, or a multi-part door closer from being
misreported as either one anonymous object or dozens of unrelated props.

## Review method

This was not a single beauty-render judgment. The pass combined four checks:

1. **Per-object inventory.** Every render-visible object in the ten production
   collections records its collection, world transform, dimensions, materials,
   logical owner, category, and expected support relationship.
2. **Per-assembly grouping.** Components are grouped under the object that would
   own them in reality: a bottle, stool, chair, booth, cash register, door,
   practical fixture, pool-table system, or mounted prop.
3. **Required contracts.** Thirty-three realism rules and fourteen physical-
   staging rules fail the deterministic build if violated. The staging layer
   provides explicit evidence for all 321 high-risk logical items.
4. **Zone renders.** Eleven close cameras test entrance hardware, bartender
   workflow, front seating, booths, lighting, upholstery patina, the clean bar
   top, measured barware, street/neon depth, flush wall history and the restroom
   door at readable scale. Six wider room/table checkpoints test whether the
   corrections still work as a scene rather than isolated models.

This means every component is classified and contract-checked, while every
high-risk assembly and room zone receives direct visual review. It does **not**
claim that all 2,317 components were each rendered as a separate turntable.

## Inventory by category

| Category | Component objects |
|---|---:|
| Building fabric | 400 |
| Door hardware | 66 |
| Pool-table system | 174 |
| Bottle stock | 668 |
| Bar fixtures/stock | 287 |
| Bar workflow equipment | 46 |
| Movable seating | 75 |
| Fixed seating | 79 |
| Patron tables | 20 |
| Patron service | 153 |
| Wall/table props | 206 |
| Motivated lighting | 142 |
| Atmosphere | 1 |
| **Total** | **2,317** |

The bottle count above includes bodies, shoulders, necks, caps, and labels. The
actual supported back-bar stock count is **193 complete bottles**, plus eight
working well bottles in the speed rail.

## Required realism contracts

| Contract | Result |
|---|---|
| Front door has exit rail/returns, latch/strike, threshold, closer body/arms/shoe, and three hinges | pass — 13/13 |
| Unsupported vertical door pull is absent | pass |
| Back stock uses at least five bottle profiles | pass — seven families |
| Every bottle bottom meets its shelf/speed-rail support within 2 mm | pass — 201/201 |
| Four bar stools represent four acquisition types | pass |
| Loose stools are not parade-aligned | pass — four distinct yaw values |
| All seating and patron-table assemblies meet the floor within 2 mm | pass — 12/12 |
| Booths are exactly two wall-adjacent face-to-face bays with east/pool entry | pass — two tables, four X-axis backs |
| Booth entries contain no freestanding partition walls | pass — zero dividers |
| Booth pool-side edges remain outside the cue envelope | pass — 240 mm clear |
| Register sits on the back-bar work surface facing the bartender | pass |
| Visible bar service workflow includes ice, well bottles, soda, garnish, sink, drainboard, waste, wet surface, opener, and beer service | pass — all roles present |
| Every working well bottle has a speed pourer | pass — 8/8 |
| Backbar and service counter leave a working bartender aisle | pass — 703 mm |
| Front-zone guest bar stops before the cue envelope | pass — 57 mm clear |
| Every Blender light has a visible fixture or documented opening | pass — 25/25 |
| Every primary wall-art plane records a mounting method | pass — 4/4 |
| Primary wall art is flush wheat-paste with no frame, pins, or raised tape | pass — 4/4; forbidden hardware zero |
| Both booth bays have explicit restrained vinyl damage | pass — 36 crack, tear, foam, or hand-wear components across both bays |
| Bathroom door carries dense flat sticker history | pass — 180 visually represented sticker layers |
| Three wall zones carry flush decades of paper history | pass — 3/3 |
| Patron tables are wiped with current coasters over older finish wear | pass — 10 dry coasters; 14 pale ring ghosts; 10 fine scratches |
| Active drinks create a balanced room footprint | pass — 10 drinks: 5 pints/5 rocks; bar 3, booths 4, café 3 |
| Served glassware uses recorded manufacturer envelopes | pass — 5 dimensioned pints; 5 dimensioned faceted rocks glasses |
| Every pint contains amber beer and restrained foam | pass — 5/5 |
| Every rocks drink contains cocktail, three ice cubes, lime wheel and straw | pass — 5/5 |
| Coaster logic represents tidy current service | pass — 9 served coasters, 1 direct fresh placement, 1 dry away setting |
| Every drink meets its support, plausible human reach and bar-edge inset | pass — 10/10 support, 10/10 reach at 0.244–0.656 m; bar bases at least 63 mm inside guest edge and 216 mm inside bar ends |
| Guest bar top is clean/open and supports tidy current service | pass — zero legacy debris; 5 lower fruit below bowl rim, 3 upper fruit contacting lower cluster, 3 inset drinks, 1 open tab |
| Storefront contains busy street depth and multiple neon/light sources | pass — 5/5 |
| Prewar shell includes three constructed aged cross beams | pass — 3/3 |
| Age is embedded across major material families | pass — 38 used aged materials |
| Close views contain subtle authored story details | pass — 18 components |

## Corrections made

### Entrance and construction hardware

- Replaced the unsupported vertical pull with a horizontal narrow-stile exit
  rail, returns, latch case, fixed jamb strike, three hinges, threshold, and a
  connected two-arm surface closer.
- Removed an interior key cylinder that had no mechanism behind it at the
  glass edge.
- Added a correctly reading illuminated EXIT sign and an old schoolhouse
  egress globe so the occupied exit path is dim, not black.
- Service and restroom leaves now have hardware, hinges, bottom gaps, and
  distinct functions. Service light appears only through the modeled gap.

### Bar workflow and stock

- Rebuilt the register as an early mechanical unit with drawer, key deck,
  28 keys, amount windows, feet, trim, and connected crank. It now faces the
  bartender from a real opening in the lowest back-bar shelf.
- Replaced cloned cylinders with seven bottle families: round whiskey,
  longneck, wine, squat liqueur, bell decanter, square whiskey, and flat flask.
  Labels face the room, heights/yaws vary, shelves have gaps, and every bottle
  meets a recorded support surface.
- Corrected the bar section itself. The former backbar and service counter
  occupied almost the same plan footprint; the rebuilt shallow wall backbar
  and 360 mm service counter leave a measured 703 mm bartender aisle.
- Added an open utility sink and drain, connected faucet, glass drainboard,
  ice well and scoop, soda gun/holster/hose, garnish bins, mounted speed rail,
  eight pour-spout bottles, dry waste, scoured metal, towel, wet mats,
  opener/cap catcher, cooler and connected tap hardware.

### Seating and lived-in placement

- Replaced four matching stools with round oak, vinyl tube-back, square wood,
  and pedestal swivel-back acquisitions. Their positions, heights, yaws,
  stretchers, foot supports, repairs, and wear differ.
- The two café tables are now different constructions: round pedestal and
  square four-leg. Their ladderback, vinyl-tube, painted-wood, and steel-folding
  chairs are individually rotated and pulled from the tables.
- Rebuilt the two fixed booths as compact wall bays. Opposing benches run
  perpendicular to the west wall, tables are cleated at their short wall edge,
  and patrons slide in from the open east/pool end to face one another. No tall
  divider walls remain. The red and bottle-green bays differ in age, back
  height, seams, feet, fine cracking, small tears, narrow exposed-foam nicks,
  end-cap hand wear and restrained repairs. The damage reads at close range but
  does not turn the seating into an unusable ruin.

### Clean surfaces, accumulated history, and lighting

- Primary wall graphics were flattened against the plaster and record a
  wheat-pasted mounting method. Frames, pins and raised tape were removed, and
  three irregular paper-history fields break up the wall without picture-frame
  shadows. The restroom door receives one dense flat sticker-bomb texture.
- Patron tables and the guest bar top follow a clean-versus-worn rule. Ten
  active drinks use measured hollow glass profiles: five pint beers and five
  faceted rocks cocktails with ice, lime and straws. Nine served drinks use dry
  coasters, one has fresh direct bar condensation, and one empty dry coaster/open
  tab implies a patron at the table. There are no apple cores, dirty abandoned
  glasses, loose caps, food scraps or sticky puddles. Wiped tabletops retain pale
  historical finish ghosts and fine scratches; the open bar top still holds an
  enamel bowl with eight physically nested whole fruits.
- All ten drinks meet their declared support within 2 mm and remain within
  0.244–0.656 m of an explicit stool, bench or chair anchor. Bar glass/coaster
  bases remain at least 63 mm inside the guest edge and 216 mm inside the bar
  ends. Fill levels, straw directions and offsets vary instead of forming a
  showroom row. The former booth cylinders and solid-looking tip jar were
  replaced by manufactured glass profiles with real wall/base thickness.
- The fruit bowl uses five lower fruit whose lowest points sit below the rim and
  three upper fruit whose geometry contacts the lower cluster. The previous
  four-plus-four staging placed every fruit bottom above the rim and was removed.
- Cue rack clips meet their cues; cues lean individually; score beads cluster;
  useful bar tools stay in bartender reach zones. Payphone and CRT wiring are
  connected curves, not floating lines.
- The exterior is a modeled light world behind the diamond glazing: one original
  wet-night LES street plate, blurred traffic, fictional small-business signs,
  a generic window-facing OPEN neon, an interior 8-ball neon and colored spill.
- Three boxed, strapped and bolted aged cross beams, plaster finish-loss zones,
  fine cracks and localized chair scuffs make the shell feel inherited. Age is
  carried by 38 used materials rather than one global dirt overlay.
- Added a caged restroom practical while preserving the localized entry, café,
  booth, back-bar, wall-sconce, neon, street-opening and service-gap sources.
  The pool table remains the brightest plane.

## Visual evidence

Final 1600 × 900, 96-spp Cycles frames are in `renders/realism_audit/`:

- `CAM_Audit_Entrance_35mm.png`
- `CAM_Audit_BarWorkflow_45mm.png`
- `CAM_Audit_FrontSeating_40mm.png`
- `CAM_Audit_Booths_45mm.png`
- `CAM_Audit_Lighting_35mm.png`
- `CAM_Audit_BoothPatina_60mm.png`
- `CAM_Audit_CleanBar_50mm.png`
- `CAM_Audit_PatronBarware_55mm.png`
- `CAM_Audit_StreetNeon_35mm.png`
- `CAM_Audit_WallHistory_45mm.png`
- `CAM_Audit_BathroomDoor_50mm.png`

The broader six-camera room/table set is in `renders/checkpoints/`.

## Research boundary

The hardware choice follows the operating logic documented for
[Adams Rite narrow-stile exit devices](https://www.adamsrite.com/en/products/exit-devices/8400-series-life-safety-narrow-stile-mortise-exit-device).
The fixture over the entrance also reflects NYC's requirement that occupied
exit access receive illumination, documented in
[2022 Building Code Chapter 10](https://www.nyc.gov/assets/buildings/apps/pdf_viewer/viewer.html?file=2022BC_Chapter10_EgressWBwm.pdf&section=conscode_2022).
These are plausibility references, not a code-compliance certification.

Back-bar placement and working density were checked against historical bar
imagery and current manufacturer workflow references. A historic bar postcard
in the [Smithsonian collection](https://nmaahc.si.edu/object/nmaahc_2014.37.36.5)
shows varied stock and a register integrated with the back bar. The compact
ice/drain/sink/speed-rail/waste sequence follows the component relationships in
Glastender's [ALL-66C specification](https://www.glastender.com/bar-fabrication/signature/all-in-one-stations/all-66c),
Krowne's [underbar overview](https://krowne.com/product-showcase/underbar), and
Perlick's [underbar design guide](https://www.perlick.com/pub/media//akeneo_connector/media_files/T/o/Top_Shelf_Stainless_Steel_Underbar_Design_Guide_lo_res_433b.pdf).

The two-booth decision was checked against the compact perimeter seating shown
by the [Old Town Bar](https://oldtownbarnyc.com/) and published interior
photography of [Rudy's](https://www.blind-magazine.com/news/a-toast-to-new-yorks-legendary-watering-holes/).
Those references informed orientation and density only; the modeled bays are
original.

The accumulated-wall and mismatched-furniture direction is supported by the
long, narrow, layered character described in this
[Milano's Bar field review](https://scoundrelsfieldguide.com/new-york/new-york-city/milanos-bar/)
and the neighborhood construction sources in `ENVIRONMENT_RESEARCH.md`.
