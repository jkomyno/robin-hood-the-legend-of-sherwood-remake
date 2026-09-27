# York grouping pass

This is the first refinement step: freeze source evidence, inspect the whole map,
and assign the reconstructed surfaces to named logical assets. The reviewed
catalog is `../../refinement/catalogs/york.json`; `ownership.txt` is its editable
recipe. It replaces 460 proximity groups with 250 named groups plus background
terrain. All 972 visible source records and nine records without meshes are
accounted for. Distinct adjoining buildings are separate assets, including attached towers
and gatehouses. Cathedral towers and the north precinct hall are separate from
the nave. `building-review.json` records the subdivisions of the first pass.

Outputs are local under `../../work/york-refinement/`:

- `baseline/`: immutable scene, native obstacle data, artwork, masks and hashes.
- `inventory/inventory.json`: complete imported mesh and patch inventory.
- `grouped/york-grouped.blend`: named asset parents and retained source identities.
- `grouped/validation.json` and `partition-verification.json`: preservation checks.
- `grounding/york-grounded.blend`: subsequent terrain-trimmed asset scene.
- `grounding/report.json`, `verification.json` and `coverage-audit.json`: cut
  inventory, retained-surface/UV checks and complete-scene burial audit.
- `review/index.html`: searchable source crops and two geometry views per asset.
- `grouping-review.json`: exact reviewed catalog/inventory hashes and scope.
- `state-ownership.json`: native patch associations and sprite-only asset inventory.
- `stage/york.rhlos-map.json`: staged map with individual reusable assets in
  `stage/map-assets/3d-assets/`; the live library is not modified.

## Scope and uncertainties

Grouping preserves the reconstruction's existing geometry and textures. The
subsequent grounding pass removes buried surfaces as described below. Missing
walls, floating sections, depth inaccuracies and unseen textures need the next
refinement step. Painted vegetation and decorative details remain part of the
background or building textures, not newly created individual models. Static
coverage does not imply complete animated state or scenery geometry.

Five market-front houses share source 650. Its surface is partitioned into five
component selectors following visible frontage divisions. Continuations through
hidden foundations are inferred; no caps are added. The complete original is
retained hidden. The castle hall and east round tower also share two surfaces
(sources 769 and 795), split along their visible junction. The continuation
through their hidden intersection is inferred. Surface area and UV interpolation
are checked against all three retained originals.

Some native volumes have displaced depth. Source artwork locates source 67 on
the northeast square watchtower ledge; it is owned by that tower.
The north precinct boundary includes clipped low boundary proxies 870–871.
These decisions assign ownership without pretending to repair their shape.

Base patches and Fog mission doors are inventoried separately. Door receiver
ownership and interior/exterior projection receivers still require authored
review before layered projection. No geometry or texture approval is implied by
the static grouping review.

## Terrain grounding

`ground_assets.py` reads the frozen grouped scene and subtracts the volumes below
the reviewed terrain, ramp and raised-lane surfaces from each asset. It trims
447 component meshes across 171 assets. All 250 named assets and terrain remain.
Cuts follow both the support footprint and its sloping height, preserving exposed
lower walls at terrace edges. Bridge decks and roofs are not solid-ground cutters.
The eleven support sources are listed explicitly in the recipe and its report.

Clipping interpolates every UV channel and retains material assignments. No caps
or replacement textures are added. Untrimmed meshes remain in a hidden reference
collection, and the grouped input file is unchanged. Asset origins move to the
lowest retained contact point; visible world geometry stays in place. The export
localizes mesh positions and obstacle heights together and verifies map placement.

The gallery and staged export now use this grounded scene. The previous delivered
gallery and library are preserved in `review-v4/` and `stage-v4/`. Verification
checks retained surfaces/UVs, accounts for removed area, tests every removed
polygon against its terrain support, and audits the full scene for buried surface
samples. Boundary comparisons allow 0.003 scene units for float32 rounding; the
ground base includes 0.1 units of reconstruction quantization tolerance.

## Reproduction

Run from the repository root, using the shared render-slot pool for Blender.
`setup_scene.py` requires the archived reconstruction in the path it records and
refuses an existing baseline. `group_scene.py` refuses an existing grouped blend.
Preserve earlier output revisions before rerunning either.

```sh
node level-editor/pipeline/src/export-interior-layers.ts york level-editor/work/york-refinement/source-states-complete
blender --background --python level-editor/blender/york/setup_scene.py
python3 level-editor/blender/york/survey.py
python3 level-editor/blender/york/build_catalog.py
blender --background --python level-editor/blender/york/group_scene.py
blender --background --python level-editor/blender/york/verify_partition.py
blender --background --python level-editor/blender/york/review_geometry.py
python3 level-editor/blender/york/build_gallery.py
blender --background --python level-editor/blender/york/export_grouped.py
```

Review all source and geometry cards before writing `grouping-review.json`.
Changing the catalog invalidates that review. Geometry workers and texture
synthesis are separate subsequent steps in the shared refinement procedure.

For the subsequent grounding pass, preserve the existing `review/` and `stage/`
outputs first (`audit_grounding.py` uses the delivered `review-v4/` as its baseline):

```sh
blender --background --python-exit-code 1 --python level-editor/blender/york/ground_assets.py
blender --background --python-exit-code 1 --python level-editor/blender/york/verify_grounding.py
blender --background --python-exit-code 1 --python level-editor/blender/york/review_geometry.py -- --grounded
python3 level-editor/blender/york/audit_grounding.py
python3 level-editor/blender/york/build_gallery.py
blender --background --python-exit-code 1 --python level-editor/blender/york/export_grouped.py -- --grounded
python3 level-editor/blender/york/verify_grounded_export.py
```

`ground_assets.py` refuses to overwrite an existing grounded blend. Preserve the
previous grounding directory before rerunning it.
