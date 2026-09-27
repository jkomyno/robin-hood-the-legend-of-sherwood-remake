# Sherwood grouping revision

The first migration kept too many historical obstacle boundaries. The September
2026 grouping audit instead follows complete huts, furniture sets, platform and
ladder assemblies, trees with their branches and roots, and contiguous outcrops.
The candidate has 82 selectable assets, down from 107. Thirty groups have changed
membership or names; 52 retain their existing membership and names.

`grouping-candidate.json` is a review candidate, not the published catalog. The
live library and `refinement/catalogs/sherwood.json` remain the initial publication
until the revised grouping is reviewed and handed off through normal publication.
The candidate worker is `work/sherwood-refinement/grouping-review/grouped-source-only.blend`.
Its geometry, UVs, material assignments, transforms and mesh names match the
corrected source-only worker exactly; only ownership metadata changes.

The central oak contains sources 32, 33, 48, 49 and 52. Its house and platform
remain separate. Source 24 explicitly splits tree meshes from attached ladder
meshes; source 102 explicitly splits house walls from platform rails, braces and
ladders. Version 2 component selectors retain canonical source/gameplay ownership.
Source 48 was already merged into the native trunk mesh and remains a canonical
part rather than a duplicated visible mesh.

The audit inspected world geometry against the original Day art and the composite
with original animated-tree first frames. It corrected misleading east/west and
central-treehouse names, including the southwest shelter and north woodland
shelter. Independent props and separated rocks remain independent. Existing
geometry defects, including the northeast woodland oak feedback, remain separate
refinement work; grouping approval does not approve geometry or generated textures.

To reproduce from the valid source-only worker, run from `level-editor`:

```sh
/usr/bin/blender --background --threads 2 --python blender/sherwood/inspect_grouping.py -- --worker work/sherwood-refinement/textures/reproject-v2/source-only.blend --output work/sherwood-refinement/grouping-review/geometry.json
python3 blender/sherwood/regroup_models.py --geometry work/sherwood-refinement/grouping-review/geometry.json --output work/sherwood-refinement/grouping-review
/usr/bin/blender --background --threads 2 --python blender/sherwood/stage_grouping_review.py -- --root work/sherwood-refinement/grouping-review
/usr/bin/blender --background --threads 2 --python blender/sherwood/verify_grouping_worker.py -- work/sherwood-refinement/grouping-review
```

Inspect all four solid and source-textured views for each changed group. Record
its `packet.json` SHA-256 in `grouping-review/inspections.json`, keyed by asset ID,
only after that visual check. This enables grouping approval without fabricating
user approval. Rebuild the parent gallery before the grouping gallery:

```sh
python3 blender/sherwood/build_model_review.py --packets work/sherwood-refinement/textures/sunburst --output work/sherwood-refinement/model-review
python3 blender/sherwood/build_grouping_review.py --root work/sherwood-refinement/grouping-review
node blender/sherwood/verify_grouping_gallery.mjs
python3 -m unittest discover -s blender/sherwood -p 'test_regroup_models.py'
```

The existing server on port 5190 serves the grouping gallery at `/grouping/`.
Every sheet starts with the original camera, then west, east and back. Each card
includes raw original-art context. Model decisions remain in `model-decisions.json`;
superseded component cards are omitted from the pending model gallery. A grouping
review is a separate revision and does not overwrite previous component decisions.
