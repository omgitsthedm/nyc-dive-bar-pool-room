# Open verified Blender checkpoints

Use `poolroom_cinematic_portable_2026-08-08.blend` to inspect or render the
cinematic scene from the moved workspace. The protected
`../poolroom_cinematic.blend` remains byte-identical to its August 7 source.

The portable checkpoint changes only 73 external image paths. All paths are
project-relative, all images load, and no old-root or absolute image references
remain. Its structural fingerprint matches the source, and
`scripts/116_validate_cinematic_take.py` passes 16/16.

A temporary 640 × 360, four-sample Cycles render of frame 480 matched the
published frame composition and materials. Structural Similarity Index Measure
(SSIM) was `0.931954` against the grained and compressed delivery frame.

SHA-256:
`d267631b11208f2185be31a342bd2b02a4cde18de2b69f3013418c11856872b7`

`02_table_geometry.blend` remains the named table-geometry checkpoint. The
older Finder-numbered saves were preserved under
`../../blend-backups/legacy-numbered/2026-08-08/`.
