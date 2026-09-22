# Shared map refinement tooling

Start with [PROCEDURE.md](PROCEDURE.md).

- `blender/`: shared inventory, grouping, review, projection, texture baking,
  publication and HTML gallery implementations.
- `record_approval.py`: records an actual user decision and hashes its evidence.
- `../pipeline/src/refinement/generate-textures.ts`: shared two-image generation
  driver; kept inside the pipeline package for its Node dependencies.

Old `level-editor/blender/*.py` entry points forward to the implementations here
so existing worker recipes and saved commands keep working. Remaining low-level
Blender helpers are loaded from that directory. Map-specific recipes and output
packets stay with their map; moving their coordinates would not make them generic.

```bash
python3 level-editor/refinement/blender/build_review_gallery.py \
  <review-manifest.json> <gallery-dir> --pending-only --map-name <map>
python3 level-editor/refinement/record_approval.py \
  <review-manifest.json> <asset-id> --decision '<actual user approval and scope>'
```

The gallery uses stable asset IDs and content hashes in image filenames, and
stable asset IDs as HTML anchors. It archives prior evidence before rebuilding.
