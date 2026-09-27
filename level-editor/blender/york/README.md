# York grouping pass

This is the first refinement step: freeze source evidence, inspect the whole map,
and assign the reconstructed surfaces to named logical assets. The reviewed
catalog is `../../refinement/catalogs/york.json`; `ownership.txt` is its editable
recipe. It replaces 460 proximity groups with 171 named groups plus background
terrain. All 972 visible source records and nine records without meshes are
accounted for. The cathedral is one asset; castle buildings, walls, towers,
houses, stalls, bridges and raised terrain have distinct owners.

Outputs are local under `../../work/york-refinement/`:

- `baseline/`: immutable scene, native obstacle data, artwork, masks and hashes.
- `inventory/inventory.json`: complete imported mesh and patch inventory.
- `grouped/york-grouped.blend`: named asset parents and retained source identities.
- `grouped/validation.json` and `partition-verification.json`: preservation checks.
- `review/index.html`: searchable source crops and two geometry views per asset.
- `grouping-review.json`: exact reviewed catalog/inventory hashes and scope.
- `state-ownership.json`: native patch associations and sprite-only asset inventory.
- `stage/york.rhlos-map.json`: staged map with individual reusable assets in
  `stage/map-assets/3d-assets/`; the live library is not modified.

## Scope and uncertainties

Grouping preserves the reconstruction's existing geometry and textures. Missing
walls, floating sections, depth inaccuracies and unseen textures need the next
refinement step. Painted vegetation and decorative details remain part of the
background or building textures, not newly created individual models. Static
coverage does not imply complete animated state or scenery geometry.

Five market-front houses share source 650. Its surface is partitioned into five
component selectors following visible frontage divisions. Continuations through
hidden foundations are inferred; no caps are added. The complete original is
retained hidden. Surface area and UV interpolation are checked against it.

Some native volumes have displaced depth. In particular, source 67 belongs to
the main keep's visible stone ledge even though the proxy is disconnected in 3D.
The north precinct boundary includes clipped low boundary proxies 870–871.
These decisions assign ownership without pretending to repair their shape.

Base patches and Fog mission doors are inventoried separately. Door receiver
ownership and interior/exterior projection receivers still require authored
review before layered projection. No geometry or texture approval is implied by
the static grouping review.

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
