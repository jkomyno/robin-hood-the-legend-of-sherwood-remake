# Shared map refinement tooling

Start with [PROCEDURE.md](PROCEDURE.md).

- `blender/`: shared inventory, grouping, review, projection, texture baking,
  publication and HTML gallery implementations.
- `record_approval.py`: records an actual user decision and hashes its evidence.
- `prepare_texture_packet.py`: copies an eligible, explicitly approved packet
  without resizing its cameras or images; builds local source-protection masks.
- `build_texture_gallery.py`: collects separately baked texture candidates whose
  eight actual views have been inspected, using the shared gallery generator.

Collectors that produce a gallery ownership report can call
`record_gallery_decision(gallery_path, records_path, asset_id, decision, exact_text)`
from `record_approval.py`. It keeps decisions separate from regenerated candidate
manifests, binds the displayed model and render packet, archives approved files,
and retains previous decisions when a user requests another revision. Approved
items hidden from the pending page remain addressable through gallery history.
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

For a batch of approved geometry/texture handoffs, use
`blender/stage_approved_batch.py` with a JSON plan (see
`plans/derby-approved-buildings-20260923.json` for the schema). Paths are resolved
against the repository root, source blends are hashed, and imports are restricted
to each catalog group's canonical parts. `source_asset_id` explicitly handles a
worker retaining an older parent group; it never imports the entire old group.
The script stages the map and standalone assets without updating the live library.

Run `blender/verify_staged_handoffs.py` in Blender against the resulting resolved
`.plan.json` before promotion. It compares untouched meshes exactly and checks
each imported handoff's world geometry, UVs, material graphs and packed image
bytes. World-coordinate drift below 0.001 units is allowed for float32 parenting
roundoff and is reported per asset; topology and appearance must match exactly.
