# Map and asset library format

A published map is `library/scenes/<map>.rhlos-map.json` plus references to the
same local assets offered by the editor palette. There is no separate map model,
map-coordinate asset scene, or automatic whole-map GLB fallback.

## Files

```
library/
  scenes/<map>.rhlos-map.json
  scenes/backups/...
  3d-assets/index.json
  3d-assets/<source-map>/<asset-id>/asset.json
  3d-assets/<source-map>/<asset-id>/model.glb
  3d-assets/blobs/<sha256>.bin
  3d-assets/blobs/<sha256>.png
  3d-assets/blobs/<sha256>.jpg
```

The index identifies assets and their descriptors, including their relative paths.
Source-map directories use lowercase names (for example `derby/`); asset IDs remain
stable. Consumers resolve the index paths instead of constructing paths from IDs.
A descriptor records local
collision footprints, stable part names, the model, and its pinned resources.
`model_scene` selects a named reusable appearance in a multi-scene model.
`state_variants` and `standalone_variants` retain their existing initial/applied
semantics. Different appearances share geometry and image payloads where their
bytes match.

Each asset uses one GLB, including its named appearances. Private payloads and
small shared payloads are embedded. A payload stays external only when sharing
between distinct assets saves at least 256 KiB: `bytes × (asset count − 1)`.
Sharing between appearances of a single asset happens inside its GLB and never
requires an external file. Models with `resources: []` are self-contained.

`blobs/` holds only the worthwhile shared buffers and textures, such as the large
reconstruction atlases. GLBs that use these files reference ordinary relative
`../../blobs/...` URIs; descriptors and saved references pin library-relative paths
and SHA-256 hashes. Packaging preserves texture encoding and accessor bytes.
Optional preview models are derived browser thumbnails, never map geometry.
`refinement/blender/lossy_assets.py` builds `preview.glb` from the lossy model (or the
model when there is none): simplified, meshopt-compressed geometry and an AVIF texture of
about 1 texel per 8 map pixels. `preview.glb.receipt.json` binds its `source_model` bytes.
An optional `lossy_model` (for example `<source-map>/<asset-id>/lossy.glb`) is a
derived lossy display copy of `model`: same nodes, extras, scenes and materials, one
re-baked texture atlas (EXT_texture_avif), quantized vertices (KHR_mesh_quantization)
and no normals on unlit primitives (nothing is lit yet).
`<lossy_model>.receipt.json` records the SHA-256 of the `model` bytes it was built
from (`source`) and of itself (`output`). Saved maps keep pinning `model`; the editor
displays the lossy model only while `source` equals that pin and falls back to `model`
otherwise.

## Local assets and placed instances

Mesh children use a local Z-up frame; the glTF `map` wrapper converts to Y-up.
Each asset descriptor records its export pivot as `source_origin_scene` so a
revised asset can be rebased without adding export provenance to the map. Asset
files contain no hinge positions in map coordinates or mission-state records.
Source obstacle/profile identifiers may remain as provenance. A reusable
appearance switch has an asset-local ID.

The map's `assetSources` pins the catalog descriptor, model, selected scene, and
resources. A version 2 map stores one entry in `placements` for each placed asset
group. Its `assets` array names the catalog assets that make up that placement;
the placement retains its ID, name, and transform. The pinned descriptors supply
the default parts, local transforms, collision footprints, names, and visibility.
The editor expands placements into its normal group and object model when loading.

A descriptor part is an obstacle part (`source_obstacle` plus
`obstacle_local_game`), a mission part (`mission_profile` plus editor-only
`obstacle_local_game`), or authored scenery. Authored scenery is a `foliage-*` or
`scenery-*` node with `scenery: true` and no obstacle, footprint or mission
profile, for example `{"node": "foliage-oak", "name": "Painted tree",
"scenery": true}`. Its GLB part node carries `scenery: true` in its extras. A
placed scenery part has `kind: "scenery"`, `source: {map}` and no `obstacle`. It
rotates about its asset-local origin, and its group pivot ignores it. The index
entry is an ordinary asset entry. Game baking rejects scenery until the compiler
can place its geometry.

Only changed parts appear in a placement's `parts` object, keyed by descriptor
part node. Each entry stores fields that differ from the descriptor defaults,
including mission bindings or an edited transform or collision shape. `removed`
lists deleted descriptor parts; `copies` describes extra instances of a part.
Mixed-asset placements use full `asset:<asset-id>:<part-node>` keys. `idMode`
selects the existing object ID convention, and an exceptional object ID appears
as a part override. An optional top-level `order` preserves object order when it
differs from descriptor order. Old version 1 maps remain readable and expand into
the same editor model. Run `node pipeline/src/migrate-map-v2.ts library` to check
an existing library, then add `--apply` to save version 2 files with backups.

Mission-specific reveal triggers and drawbridge bindings belong in per-object
`missionBindings`. Bindings are applied to the placed clone, so inserting the same
library asset elsewhere does not attach it to the original mission. The map keeps
only reveal patch IDs and names in `sceneMetadata.reveal.patches` for editor labels;
game patch states and review frames stay in their source manifests. The map
does not need export origins for editing or rendering; publication reads those
from the old and new pinned asset descriptors when an asset revision changes
its local origin. Terrain is a pinned background catalog asset in `sceneAssets`.

Coordinates use ordinary floating-point values. The migration verifies collision
footprints and flags and compares rendered views, allowing small rasterization
differences from local-coordinate roundoff. No residual-coordinate extension or
special precision data is stored in assets.

## Authoring and compilation

**New map** creates an unbounded canvas (`size: null`); choosing dimensions is not
a prerequisite. `exportBounds: [x, y, width, height]` is an optional output crop,
not an editing boundary. Content may intentionally extend beyond it. Without an
explicit crop, an authored-map compiler should derive output bounds from content.
The current reconstruction baker cannot compile placed catalog geometry or custom
crops; saving/publishing the editor document is separate from game-file baking.

## Export, verification, and cleanup

The refinement map exporter writes this format directly. Selected reviewed assets
and map instances share one canonical model; unselected map groups are also
exported as reusable local catalog assets. Intermediate standalone GLBs and their
placement evidence are retained only in the staging backup/evidence area.

Publication verifies the complete referenced resource graph, installs asset files
before the map/index, and uses hash guards, a library lock, backups, and rollback.
A changed pin is an error; the loader does not silently substitute a newer asset.
See [the refinement procedure](../refinement/PROCEDURE.md#map-publication-format).

Retired whole-map scenes, redundant embedded models, and unreferenced payloads
belong under `library/scenes/backups/`. Cleanup must retain every file referenced
by any active map, catalog appearance, or preview. Ongoing Blender workers and
review evidence are independent of this library cleanup.

For an existing split-scene library, stage conversion with
`python3 refinement/unify_map_assets.py library work/canonical/staged`, then run
`node pipeline/src/place-canonical-assets.ts work/canonical/plan.json` from
`level-editor/`. Review the placement proof and rendered comparisons before
running `python3 refinement/apply_canonical_library.py work/canonical/plan.json
--apply`. Without `--apply`, this command validates source guards and the complete
active graph and reports the proposed cleanup. It archives superseded files and
restores previous files if installation fails.

To repack an existing local catalog using the hybrid policy, run
`python3 refinement/hybrid_library.py library work/hybrid/staged`, review its
report and rendered comparisons, then run
`python3 refinement/apply_canonical_library.py work/hybrid/plan.json --apply`.
The packer also accepts an existing hybrid catalog and rediscovers sharing from
embedded payloads, placing every asset under its source-map directory and updating
map pins. `--min-savings` sets the byte threshold. The refinement map
exporter runs this packing step automatically across its staged catalog;
library-wide repacking can additionally find sharing across separate publications.

The editor reads published files over HTTP, using `3d-assets/index.json` for the
palette. Its static serving preparation generates `scenes/index.json` (an array
of map JSON filenames) and excludes backups. Browser saves are OPFS copies, never
writes to this library; **Download** exports the current map JSON for external use.
