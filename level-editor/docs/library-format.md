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
Asset files contain no source-map placement origins, hinge positions in map
coordinates, or mission-state records. Source obstacle/profile identifiers may
remain as provenance. A reusable appearance switch has an asset-local ID.

The map's `assetSources` pins the catalog descriptor, model, selected scene, and
resources. Objects name their source with `asset:<asset-id>:<part-name>`. Their
local footprints and part/group transforms use the same representation as manual
palette insertion. Group and object IDs, hidden state, collision flags, and
native source obstacle IDs survive conversion.

Mission-specific reveal triggers, drawbridge bindings and initial-state evidence
belong in per-object `missionBindings` and map `sceneMetadata`. Bindings are applied
to the placed clone, so inserting the same library asset elsewhere does not attach
it to the original mission. `sceneMetadata.assetOrigins` is map-only refinement
provenance: it lets publication compensate for an exporter choosing a different
local origin while retaining the author's edits. It is not needed to render an
asset or insert it manually. Terrain is a pinned background catalog asset in
`sceneAssets`.

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
