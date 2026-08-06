# Source Manifest

Machine-readable hashes for every consulted file: `reports/asset_manifest.json`.

## Toolchain (Amendment Patch 9)

```text
Executable: /Applications/Blender.app/Contents/MacOS/Blender
Version:    Blender 5.2.0 LTS 	build date: 2026-07-14 
```

`blender` on PATH: (no 'blender' on PATH)
Blender app bundles present: /Applications/Blender.app 

Scripts pin this API version. No version-agnostic fallback shims are used.

## Project-internal reference copies

| File | SHA-256 | Origin | Purpose |
|---|---|---|---|
| `docs/references/olhausen_component_breakdown.txt` | `ea4f384c69f9e7b582a4d6e91397b538e0e47818501c4aa57ad0f2ccddd15fce` | `/Users/davidmarsh/.codex/attachments/4288f30b-497f-4352-b3d4-35b7e82aa844/pasted-text.txt` (volatile) | Material stack and Remington product-family construction. Relocated per Amendment Patch 1; the `.codex/attachments` path is treated as unavailable for the remainder of production. |

## External references (read-only, never modified)

| File | Purpose | Survives into output? |
|---|---|---|
| `Metro2005.pdf` | Assembly relationships, hardware logic, cloth/featherstrip treatment | No — reference only |
| `US3263996.pdf` | Hidden frame and load-path logic (expired patent, public domain) | No — reference only |
| `pool_table_traditional-2.glb` | Proportion/style benchmark, CC-BY-4.0 | No — locked in `99_REFERENCE_LOCKED`, excluded from all view layers |
| `pool_table_traditional/license.txt` | License of record | Attribution retained in `docs/ATTRIBUTION.md` |
| [Libbey 1639HT mixing glass](https://libbeyfoodservice.com/product/libbey/restaurant-basics-heat-treated-mixing-glass/1639ht) | Manufacturer dimensions for generic 16 oz pint/mixing-glass envelope | No — dimensional reference only; no logo or source model |
| [Libbey 15232 Gibraltar rocks glass](https://libbeyfoodservice.com/product/libbey/gibraltar-rocks/15232) | Manufacturer dimensions and eight-sided form for generic 10 oz rocks-glass envelope | No — dimensional reference only; no logo or source model |

## Fonts (Amendment Patch 6)

`assets/fonts/` is currently **empty**. No font is used in any render yet.
Ball numbers (Patch 4) are drawn procedurally in the material node graph and
require no font file. Any font added later must carry a row here with name,
foundry, license type, license path/URL, and permitted-use confirmation for
rendered stills before it may appear in a final render.

## Original generated environment art

These eight project-owned raster assets were created on 2026-08-04 with OpenAI
image generation in built-in mode. The prompt direction requested fictional
1978–1999 neighborhood-bar ephemera, analog snapshots, faded ink, compressed
paper history, a dense restroom sticker field and a wet nighttime Lower East
Side street. No real brands, celebrities, copyrighted characters or external
logos were requested. Printed age is distinct from current housekeeping: the
scene's bar and patron surfaces remain clean. All eight assets survive into the
rendered environment.

| File | SHA-256 | Bytes |
|---|---|---:|
| `assets/textures/wall_art/memory_wall_1978_1998.png` | `176d76a1b3c8ca5d92019e4f080664aa7b53700ef5abfa519cfecf2f93f3a758` | 3,022,145 |
| `assets/textures/wall_art/payphones_1988.png` | `f36041024c93eb80f70430ba13cc682e5223eb8cff7b9c903a44f8d08370d353` | 3,324,202 |
| `assets/textures/wall_art/pool_team_1986.png` | `da91126d3f9d46f4354d983ec9f47ad895917ac871767be8d264f6509fb68f42` | 2,560,797 |
| `assets/textures/wall_art/sticker_wall_1982_1999.png` | `62411c5dc6d3f2d88bade82247187ef61525cc7ca7a3e2353fca5b865374cc7b` | 3,904,191 |
| `assets/textures/wall_art/tuesday_8ball_1993.png` | `e24416bc005969f009c7557ade3d743d2933466980f9550394214d3e1d120b64` | 3,892,826 |
| `assets/textures/environment/bathroom_sticker_bomb_v2.png` | `679b48ddc9f7f493bc38e2fb39b0b620040b7fe79db3d5e45540127989a7d5ac` | 3,718,724 |
| `assets/textures/environment/les_night_street_v2.png` | `63b10cb784c64bcd00497ecf42ce7331577fec4ee4557de09c013d17b0d5a084` | 2,290,364 |
| `assets/textures/environment/wheatpaste_wall_history_v2.png` | `f8ed2eb787c213fc4a479e741090a01c712a85343e5ffe8dabba0c660151801a` | 3,588,198 |

The five earlier prompts cover fictional neighborhood flyers and an analog
1978–1998 memory collage. The three environment-pass prompts cover: hundreds of
overlapping illegible 1980s/1990s stickers compressed to a restroom door; an
irregular, many-layered wheat-paste paper field with faded fictional ephemera;
and a rain-wet LES night street with blurred cars, fire escapes and glowing
fictional small-business fronts. All prompts excluded real logos, celebrities,
copyrighted characters and readable brands. Generated source files were copied
from built-in image-tool output into the project paths above; Blender references
only these project copies.

## Film audio (2026-08-06)

PATH B — synthesized offline, no downloaded assets. The provenance invariant
requires any downloaded audio to be CC0/public-domain with a verifiable URL,
licence, hash and byte size; no sample could be licence-verified without
fetching from the network, so none was used. Synthesized assets need no
manifest entry, but the generator is recorded here:

| Generator | Sounds |
|---|---|
| `scripts/111_build_film_audio.py` | cue strike, ball-ball clack, cushion thump, pocket capture, room tone |

All four one-shots are numpy: band-passed noise bursts with exponential
decays, plus a damped sine partial on the clack and a 90 Hz thud under the
pocket. The room tone is brown noise low-passed at 300 Hz, -34 dBFS.

The mix is deterministic. The RNG is seeded from the trajectory's own
SHA-256, so the same take always produces a bit-identical WAV; the hash of
each render is recorded in `reports/film_audio_manifest.json`.
