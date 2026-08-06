# Attribution

## Third-party benchmark model

This project used a downloaded 3D model as a **proportion and style benchmark only**.
It is imported into a hidden, locked `99_REFERENCE_LOCKED` collection, excluded from
every render view layer, and no source mesh, texture, UV set, or recognizable
derivative is present in the final geometry — all hero assets are rebuilt
parametrically from published specifications.

The attribution is preserved regardless, so provenance stays unambiguous:

> This work is based on "Pool Table Traditional"
> (https://sketchfab.com/3d-models/pool-table-traditional-e0b938c0c2e74eb794a49ebde2543977)
> by fizyman (https://sketchfab.com/fizyman), licensed under CC-BY-4.0
> (http://creativecommons.org/licenses/by/4.0/).

License of record: `../Pool Table Assets/pool_table_traditional/license.txt`
SHA-256 of every consulted source file: `reports/asset_manifest.json`

## Physics software

Deterministic shot resolution uses
[Pooltool 0.6.0](https://github.com/ekiefl/pooltool), installed as the pinned
`pooltool-billiards` package in the project-adjacent Python 3.12 environment.
Pooltool is licensed under the
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
Its methods and software citation are described in the
[Pooltool JOSS paper](https://doi.org/10.21105/joss.07301). Blender receives
solver-authored transforms only; Blender Bullet is not used as a second
physics authority. Pooltool 0.6.0 performs pocket capture against a continuous
2D circle. The Blender model's 3D shelf and backdraft are static construction
geometry and are not attributed to Pooltool's capture model.

## Reference documents

| Document | Status | Use |
|---|---|---|
| `../Pool Table Assets/Metro2005.pdf` — Brunswick installation manual | Third-party copyright, consulted not reproduced | Static assembly relationships, hardware logic, cloth/featherstrip treatment. It does not supply gameplay coefficients. No Brunswick branding or exterior styling is copied. |
| `../Pool Table Assets/US3263996.pdf` — Braun, 1966 | **Expired patent, public domain** | Hidden static frame geometry and load-path logic only. The dated fibreglass exterior is deliberately not reproduced, and the patent is not a physics source. |
| Olhausen Remington component breakdown (user-supplied) | Third-party product information | Material stack and product-family construction character. The table is unbranded and is **not** a replica; no Olhausen logo, nameplate, or proprietary ornament appears. |
| `../assets/wpa/WPA-Recommended-Equipment-Specifications.pdf` | Publicly published WPA standard | Playfield, pocket, cushion, ball, marking and lighting requirements. The standard supplies ball size and a mass range, but not this project's gameplay friction coefficients. |
| Libbey Foodservice 1639HT and 15232 product pages | Manufacturer product information, consulted not reproduced | Exterior height/diameter/capacity envelopes for unbranded generic pint and eight-sided rocks glassware. No logo, catalog image or source model is reproduced. |

## User-supplied pocket references

The four user-supplied pocket images were used as visual comparison material,
not as dimensional authority. Photo 2 is the 1933 expired patent
[US1894989A, *Carom plug for tables*](https://patents.google.com/patent/US1894989A/en).
It depicts a removable plug that closes a pocket for carom play, not a pocket
iron. No plug body, geometry or hardware was copied into the table. The 40°
plan-view annotation in Photo 1 is not treated as vertical backdraft; the model
uses 13.5° within the WPA 12–15° backdraft range. Photos 3 and 4 inform only the
general appearance of an open leather-welt pocket and relative mouth scale.

## Physics research references

The gameplay profile cites primary literature for model choice and calibration
context. Values not fixed by the WPA are explicit project profile choices and
are not presented as measurements from a particular cloth, ball set or table.

| Reference | Role in this project |
|---|---|
| [Ball collision dynamics](https://doi.org/10.1016/j.ijmecsci.2007.11.006) | Frictional, inelastic equal-ball contact model context. |
| [Ball motion on cloth](https://doi.org/10.1119/1.3157159) | Sliding-to-rolling transition and rolling-resistance model context. |
| [Cushion impact dynamics](https://doi.org/10.1243/09544062JMES1964) | Compliant cushion response and spin-coupled rebound context. |
| [Sidespin decay](https://doi.org/10.1109/TMECH.2015.2461547) | Angular deceleration model context. |
| [Cue impact mechanics](https://doi.org/10.1119/1.2825392) | Instantaneous cue-tip/ball impulse and tip-offset context. |
| [Event-driven billiards simulation precedent](https://doi.org/10.1007/11922155_19) | Event-based continuous contact resolution precedent. |

## Originality statement

The table is a custom, unbranded, 9-foot six-leg design. Where a dimension is not
published by any source it is recorded as a `DESIGN_DECISION` in
`docs/DESIGN_DECISIONS.md` and is never presented as an official specification.

All signage, posters, flyers, labels, and lettering in the scene are fictional and
original. No real-world beer, liquor, sports-team, or music logos appear.

Eight environment raster assets were created with OpenAI image generation in
built-in mode for this project: five period wall-art plates, one restroom
sticker field, one wheat-paste wall-history field and one fictional Lower East
Side night-street plate. Their prompts excluded real brands, celebrities,
copyrighted characters and logos. Exact file hashes, byte sizes and prompt
direction are recorded in
`docs/SOURCE_MANIFEST.md` and `reports/asset_manifest.json`.

The 16 gameplay-ball equirectangular maps were generated locally by
`scripts/make_game_ball_decals.py`; they are not downloaded ball textures.
They use solid/stripe color fields, opposed number circles, inverted duplicate
numerals, underlined 6/9 markings and one red cue-ball reference circle. The
script renders the installed macOS Arial Bold face into the raster numerals;
the font file itself is neither copied nor redistributed by this project.
