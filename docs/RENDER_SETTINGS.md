# Render Settings

## Saved-scene roles and cameras

`blend/poolroom_master.blend` is the frozen environment baseline.
`blend/poolroom_pool_rebuild_preview.blend` is the derived static pool
candidate and the correct source for current table proof renders.

The candidate defines **24 distinct cameras**: 19 cinematic/environment
cameras (six broad checkpoints, eleven close realism views and two additional
cinematic views) plus five purpose-built pool-audit cameras. The pool-audit
renderer also reuses `CAM_Table_ThreeQuarter_50mm` and
`CAM_Rack_Detail_85mm`; those reused views do not increase the distinct-camera
count.

## Engine

Cycles, Metal GPU backend (confirmed active; CPU fallback coded and logged if
Metal is unavailable). AgX, Medium High Contrast. Adaptive sampling on,
threshold 0.01. OpenImageDenoise with albedo+normal passes.

Final: 512 samples, 3840 x 2160, 16-bit PNG.
Preview/checkpoint: 96 samples, 1600 x 900. Scene exposure is **-1.0 stops**;
this preserves the white ball patches and keeps the cloth bottle-green instead
of mint. Gamma is 1.0.

## Measured frame times (final environment checkpoints)

Preview pass, 1600 x 900 @ 96 spp, Metal GPU. Checkpoint timings come from
`reports/render_timing.json`; the current 30 mm hero timing comes from
`reports/cinematic_stills_timing.json`:

| Camera | Seconds |
|---|---|
| CAM_Hero_Entry_30mm | 179.3 |
| CAM_Table_ThreeQuarter_50mm | 155.1 |
| CAM_Rack_Detail_85mm | 203.6 |
| CAM_Bar_Reverse_35mm | 233.6 |
| CAM_Environment_Wide_35mm | 255.5 |
| CAM_FrontRoom_22mm | 182.6 |

Close realism pass, 1600 x 900 @ 96 spp, Metal GPU — from
`reports/realism_render_timing.json`:

| Camera | Seconds |
|---|---:|
| CAM_Audit_Entrance_35mm | 93.0 |
| CAM_Audit_BarWorkflow_45mm | 168.7 |
| CAM_Audit_FrontSeating_40mm | 145.3 |
| CAM_Audit_Booths_45mm | 228.9 |
| CAM_Audit_Lighting_35mm | 261.9 |
| CAM_Audit_BoothPatina_60mm | 118.6 |
| CAM_Audit_CleanBar_50mm | 207.1 |
| CAM_Audit_PatronBarware_55mm | 112.7 |
| CAM_Audit_StreetNeon_35mm | 198.0 |
| CAM_Audit_WallHistory_45mm | 306.1 |
| CAM_Audit_BathroomDoor_50mm | 354.5 |

The complete 15-shot opening chapter took 2,941.5 seconds at this preview
setting, a mean of 196.1 seconds per frame. Exact per-camera timings and shot
order are in `reports/cinematic_stills_timing.json`.

## Pool-system audit settings

`scripts/83_render_pool_audit.py` uses Cycles and writes to
`renders/pool_system_audit/` without updating production reports. Its `audit`
preset is 32 spp at 1280 × 720, with a 1200 × 1200 diagnostic top view. Its
`final` preset is 512 spp at 3840 × 2160, with a 3840 × 3840 top view.

The five purpose-built views are:

- `CAM_PoolAudit_Top_24mm`;
- `CAM_PoolAudit_Corner_85mm`;
- `CAM_PoolAudit_Side_85mm`;
- `CAM_PoolAudit_Fixture_SideElevation`;
- `CAM_PoolAudit_Fixture_ThreeQuarter_24mm`.

The script's default seven-view set adds the existing table three-quarter and
rack-detail cameras. Static table acceptance comes from the 90-check geometry
audit. Current audit renders provide static visual proof and are not a gameplay
test.

## Legacy four-frame delivery budget projection

Scaling from the measured preview pass: 4K is 5.76x the pixels of 1600x900,
and 512 spp is 5.33x the samples. Cycles does not scale perfectly linearly,
but a conservative estimate is **~30x the preview time per camera**:

```
checkpoint mean       217.3 s
4K @ 512 spp          ~217.3 x 30.72 = ~111 min per camera
4 required cameras    ~7.4 machine-hours
6K hero               ~4.1 machine-hours
Total                  ~11.5 machine-hours
```

This historical four-frame projection is **inside the 24 machine-hour gate**;
it is not a cost estimate for rendering all 24 cameras. If the measured 4K time
comes in above projection when the delivery pass runs, the documented order of
remedies applies: reduce to 384 spp first, then border-crop the 6K, then drop
the 6K. Hero-area quality, denoising, and black levels are not to be traded.

## Lighting

The chain-hung fixture is recorded as movable; its bottom is 40 in (1.016 m)
above the bed under the corresponding WPA condition, placing it 1.778 m above
this floor. Three 16 W disc emitters sit inside the shades, plus one 4 W wide
fill for rail and corner evenness.

All **25 Blender light objects** record a visible fixture, neon assembly or
modeled opening:

- three 28 W bar pendants; 18 W back-bar tube glow; 7.5 W back-bar neon;
- 15 W street-facing OPEN neon and 8 W generic 8-ball neon;
- 29/31 W rear sconces, 24/26 W east-wall sconces and a 72 W caged
  restroom-door practical;
- 92 W entry schoolhouse globe and 72 W caged café bulb;
- 58/54 W mismatched booth pendants and a 2.5 W illuminated EXIT sign;
- 62 W broad storefront spill, 18 W tail-light spill, 20 W opposite-shop-sign
  spill and 5 W service-gap spill.

These values are Blender emitter energies, not measured fixture wattage or a
code photometric calculation. Volume scatter density remains 0.0032 and is
confined to a box above table-camera height.

## Sweep parity warning

`scripts/85_render_sweep.py` still uses `EXPOSURE = 2.35` and
`LIGHT_BOOST = 2.6` for EEVEE. Those values were calibrated before this
environment relight. The existing 288 frames are retained as historical output
but must not be described as matching the current Cycles stills until a short
frame-range test is re-tuned and approved.
