# Default terrain art

Seamless 256 × 256 tiles synthesized from clean Day map surface samples with
`texture-synthesis 0.8.3 --tiling`. Grass, dirt and water use Leicester; paving
uses Nottingham courtyard flagstones. The donor crops are stretched vertically
to undo the ground's 35° projection before synthesis. No color tint is applied.

Regenerate from `level-editor/` with Pillow and `texture-synthesis` on PATH:

```sh
python3 scripts/synthesize-terrain.py /path/to/Data/Levels/Day
```

The script records crop rectangles, seeds and CLI settings. Its working donors
and full-color outputs go to ignored `work/terrain-textures/`. Use `--threads 1`
for deterministic regeneration; parallel synthesis varies in small details.

The PNGs are reviewable swatches. `tiles.json` holds the same 256-color palettes
and indexed pixels for synchronous browser/offline decoding. This avoids an
image-loading race when baking immediately after adding terrain. Each tile
covers 256 game units, so moving or resizing ground preserves its texture scale.
Roads and rivers use the dirt/water swatches with feathered edges.
