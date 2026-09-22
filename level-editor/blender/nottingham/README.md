# Nottingham refinement

These recipes implement the review workflow in
`../../work/derby-refinement/REFINEMENT_PROCEDURE.md`. Run commands from the
repository root. Generated evidence lives in `level-editor/work/nottingham-refinement/`.

The reviewed grouping is `grouping/catalog-v5.json`: 118 selectable groups own
555 canonical source parts exactly once. Terrain has its own additional review
workspace. The market houses form one market terrace with selectable children.

`setup_scene.py` records the source inventory and recovers the omitted thin slab.
`group_scene.py` groups the recovered source without changing world geometry.
`source_states.py` preserves native masks, patches, and animation frames.
`source_review_masks.py` builds explicit receiver constraints. The canonical
V11 baseline contains only existing source nodes; component sidecars are applied
to the owning workspace after its geometry recipe creates those components.
Unknown ownership is represented by a rejection mask and neutral shading.

`freeze_tooling.py` snapshots the shared Blender helpers. Recipes select the
snapshot referenced by `tooling/current.json`; changing live shared helpers does
not alter an existing worker's implementation. `render_slots.py` limits expensive
Blender work to three concurrent processes. Use background Blender with
`--threads 2 --python-exit-code 1` and acquire a render slot before loading and
rendering large scenes.

`prepare_assets.py --help` describes frozen workspace preparation. Each asset
keeps immutable `baseline.blend`, `input/`, and source evidence. Run its geometry
recipe on `model.blend`, then regenerate and validate `modified/`. A wider camera
fit requires a new workspace revision with matching input and modified views.
Do not replace frozen input images. `workspace-overrides.json` selects revisions
explicitly; the gallery never guesses the newest directory.

Rebuild and check the pending review gallery:

```sh
python3 level-editor/blender/nottingham/build_gallery.py
node level-editor/blender/nottingham/verify_gallery.mjs
```

The builder checks catalog membership, immutable files, mask authority, fixed
cameras, projection partitions, and worker reports bound to model and packet
hashes. `candidate.json` requires an explicit eight-view visual audit and a
description of changes or a justified unchanged-geometry decision. Validation
alone does not establish that refinement is complete. Limitations remain visible.

Candidates can name `revealed_solid`, `revealed_textured`, `revealed_context`,
and `revealed_input` using workspace-relative paths. Animated endpoints use
`animation_states: [{"id": "portcullis-initial", "directory": "..."}]`.
These are complete fixed-camera packets, checked and included in the state
bundle hash. Endpoint cards refer to their parent asset's decision.
Optional `covered_solid`, `covered_textured`, and `covered_context` display the
validated covered state as the primary card while retaining the complete
`modified/` geometry comparison in the evidence.

`gallery-progress.json` lists every group, including missing or invalid packets.
`gallery-packet-evidence/` holds current validation and ownership records; the
gallery retains older review revisions in its history. Worker audit directories
record measured anchors, inferred hidden geometry, source constraints, and
reproducible commands.

Geometry approval is a separate explicit user decision, bound to the model,
modified views, and any state bundle hashes. Pass those records with
`build_gallery.py --approvals <file>`. Source grouping preferences are not geometry
approval. Texture synthesis and editor publication follow the procedure's
approval gate; an unapproved review packet must not be published.
