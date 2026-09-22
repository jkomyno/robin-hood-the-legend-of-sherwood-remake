# 3D map refinement procedure

This is the reusable workflow for refining another game map. The goal is to
produce geometry that matches the source artwork from the playable camera,
preserve the game’s reveal and occlusion behavior, and export named editor
assets that can be selected independently.

## 1. Freeze the source and inventory the map

1. Copy the original scene into a frozen worker baseline. Never edit the
   baseline in place.
2. Record the source artwork, source dimensions, camera/projection settings,
   patch/state files, object IDs, materials, UVs, and transforms.
3. Build a scene inventory containing every mesh, parent, source node, mask or
   patch association, animation/state association, and current editor name.
4. Preserve hashes for the source scene, source artwork, masks, and every
   exported asset.

The source artwork is authoritative for visible pixels. The 3D model is an
editable hypothesis for hidden depth and surfaces. Do not infer a surface from
texture alone when the source mask or a revealed state contradicts it.

## 2. Create logical asset groups before refining geometry

An asset group is the smallest logical object a level designer should select:
usually one building, tower, wall section, stair, bridge, cottage, prop, or
interior component. A roof, wall, and foundation that belong to one building
remain one group unless separate selection is useful in the editor.

For each group:

- assign a stable machine ID and a descriptive human name;
- list all source nodes and meshes;
- preserve parent/child relationships and world transforms;
- record state-specific parts such as raised/lowered bridges or revealed
  interiors;
- ensure no mesh is silently assigned to two groups;
- split long walls at structural breaks, bends, towers, landings, or other
  natural boundaries;
- retain a canonical source ownership record even when one source mesh is
  split into multiple projection components.

Run a catalog reconciliation after every split. It must report missing parts,
duplicates, changed transforms, and source-node/component ownership.

## 3. Create one workspace per asset group

Each worker receives an isolated directory:

```text
round-2/assets/<asset-id>/
  model.blend                 # worker copy
  baseline.blend              # untouched group baseline
  input/
    context.png               # original source crop with background
    views.json
    views/view-0..7-solid.png
    views/view-0..7-known.png # source-visible pixels only
    views/view-0..7-textured.png
  modified/
    context.png
    views.json
    views/view-0..7-solid.png
    views/view-0..7-known.png
    views/view-0..7-textured.png
  inspection/
  validation.json
  review.md
```

The eight views are four columns by two rows with identical cameras in input
and modified output. Use the same framing and resolution. The context image is
the original map crop, not a synthesized texture. Back or unseen surfaces are
shown as neutral gray so the worker can distinguish source evidence from
inferred geometry.

Workers may create extra close-ups, reverse views, or alternative camera
angles when needed. These supplements must not replace the frozen eight-view
packet.

## 4. Use masks and patches as ownership authority

For every rendered pixel, determine which source layer, patch, state, and mesh
component owns it. Keep separate records for:

- covered/exterior state;
- revealed/interior state;
- character or foreground occlusion;
- removable covers and bridge leaves;
- source-visible pixels and genuinely unknown pixels.

Never treat a large union mask as proof that every pixel belongs to one object.
Use native masks, layer metadata, receiver components, and state-specific
occluders. A source pixel from a neighboring tower, roof, or foreground object
must not be projected onto the reviewed asset.

Validation must report accepted pixels, rejected pixels, foreign ownership,
duplicate ownership, outside-object preservation, source RGB preservation, and
geometry/UV/transform changes.

## 5. Refine geometry from source evidence

For each asset, compare the source crop against all eight solid and source-only
textured views. Correct:

- silhouette, footprint, wall thickness, roof profile, overhangs, and contacts;
- stairs, landings, arches, windows, doors, battlements, merlon count and
  zigzag phase;
- interiors revealed by patches, including floors, walls, tables, fireplaces,
  bridges, and occlusion shells;
- disconnected, nonmanifold, degenerate, duplicated, or intersecting faces.

Count repeated architectural elements directly from the source. A projected
texture that appears offset or has fewer wall up/down repeats is evidence of a
geometry/projection mismatch and requires a count/phase correction.

Keep source-supported geometry separate from artistic inference. Document every
inferred hidden surface and every unresolved limitation.

### Numbered source artwork corners: why and how

Use this whenever repeated architecture, especially battlements, disagrees with
the projected texture. Counting merlons alone failed on Derby: uniform spacing
and guessed wall bends could give the correct count while leaving each notch
offset. A texture can also conceal missing faces. Explicit corner observations
make the worker's evidence inspectable and constrain phase, width and height.

1. Inspect the original, unsynthesized artwork and its native ownership masks.
   Save an unmarked bounding-box crop with enough surrounding context. Enlarge
   with nearest-neighbor for pixel inspection; do not paint or resize the source
   used for projection.
2. Pick every visible cap endpoint, vertical notch shoulder, and notch-floor
   corner in order along each wall run. Store original full-image `(x,y)` pixels
   in JSON, plus source hash, crop origin, source node, run, corner role,
   confidence and visibility. Crop/display coordinates must be converted back.
   Mark roof/chimney-obscured corners as inferred; do not score them as measured.
3. Draw numbered dots and connecting lines on a separate annotated crop. Put
   the untouched crop beside it. Identify which near/far cap edge was traced;
   mixing the two edges creates false height/thickness corrections. Typical
   manual uncertainty is 1–3 native pixels, not subpixel certainty.
4. Use the frozen original projection to solve the corresponding world-space
   corners. One pixel leaves depth ambiguous: constrain height/depth using
   wall footprints, vertical faces, continuity, adjoining geometry and revealed
   artwork. Keep the 35-degree source camera separate from Derby's selected
   48-degree sun. Correct actual visible Working meshes in world coordinates,
   not hidden baseline copies or object-local coordinates mistaken for world.
5. Rebuild or cut the complete wall, retaining its body, cap thickness, returns
   and ground contacts. Do not replace it with detached merlon boxes. Check
   zero-area faces, open edges, overlapping seams, signed volume and preservation
   of unrelated geometry. Source-fit accuracy does not imply sound topology.
6. Reopen the saved result and project its actual edges/vertices onto the source.
   Show before/after edges, numbered targets and displacement vectors. Prefer
   explicit corner-to-corner correspondence. Nearest-vertex RMS can match the
   wrong overlapping face and must be labelled diagnostic. Tiny residuals from
   fitting those same targets are construction checks, not independent proof
   that the chosen artwork pixels were correct.
7. Reapply source projection and render all eight views at the frozen cameras.
   Independently inspect silhouette, geometry and source texture; include the
   unmarked source, numbered trace and actual-mesh overlay in the review gallery.

Working examples (map-specific recipes, not generic CLIs):
`level-editor/blender/derby_keep_north_pixel_trace.py`,
`derby_keep_north_trace_report.py`, `derby_round4_keep_central_trace.py`, and
`derby_upper_gate_corner_fit.py`. Preserve their evidence format when adapting
coordinates and node IDs to another map; do not reuse Derby's coordinates.

## 6. Reapply projection after every geometry change

Projection is never considered current after a mesh edit. Re-run the reusable
projection/export script to generate the complete `modified/` packet:

1. evaluate the modified mesh;
2. render the fixed eight cameras and the context crop;
3. apply native source masks and state-specific ownership;
4. preserve known source pixels exactly;
5. leave unsupported or unknown regions neutral gray;
6. write hashes, ownership evidence, and validation reports.

Inspect every modified view. A clean solid silhouette does not prove that the
projected texture is aligned.

## 7. Review and approval gate

Build a review gallery from the candidate manifest. It must show:

- solid and source-textured eight-view sheets;
- original context crop;
- covered and revealed sheets when applicable;
- validation and ownership evidence;
- known limitations and state assumptions;
- explicit status: refinement in progress, ready for approval, approved, or
  rejected.

Hide approved items from the pending gallery, but retain their archived review
evidence. Do not infer approval from a positive comment such as “pretty good”;
record explicit approval before starting an AI texture fill.

### Review-gallery approval process

The review gallery is the primary handoff between workers and the map owner.
Each card contains the stable asset ID and name, solid and source-textured
views, original context, covered/revealed views when applicable, validation,
ownership evidence, and limitations.

1. Finish geometry and the complete `modified/` packet.
2. Validate masks, hashes, transforms, outside objects, and all fixed cameras.
3. Rebuild the gallery with `--pending-only`, archiving the previous index.
4. The map owner reviews the actual images and explicitly approves, rejects, or
   requests a revision for each named asset.
5. Record the exact approval text and revision/hash, then hide approved cards
   from the pending gallery while retaining their evidence archive.
6. Only explicitly approved geometry may proceed to texture synthesis or
   publication.

Geometry approval and texture approval are separate decisions. Raw generated
   textures remain archived even when a protected/source-preserved alternative
   is selected.

## 8. Texture generation

After geometry approval, prepare two fixed-camera inputs for texture synthesis:

1. source-preserved textured views, with unknown areas neutral gray;
2. pure gray solid views with the desired fixed-world lighting.

Use the approved image model and high quality with no API mask when that is the
map workflow. Preserve the raw response, protected/source-preserved composite,
prompt, settings, input hashes, and API response. Never replace known source
pixels with a generated result without explicit approval.

If a generated material is wrong, retain the failed raw output and run a
separate retry directory with a more specific material prompt.

### Concrete two-image Sunburst workflow

Commands below run from the repository root. The implemented driver is
`level-editor/pipeline/src/refinement/generate-textures.ts`; it reads the key
from `level-editor/.env` through `env.ts`. Never print or copy the key into reports.

Prepare a new immutable experiment directory with the approved camera manifest
`views.json`, per-view input PNGs and editable masks. The manifest must include
the camera matrices, tile/crop layout, asset objects, source blend, reviewed
packet hash and projection/ownership evidence required by the bake helper.
Use the existing reviewed packet preparation code as the schema authority;
merely placing an eight-view PNG beside an invented manifest is insufficient.
The driver requests the exact canvas dimensions from the approved manifest;
verify both input sheets and the local mask match it. Sunburst custom dimensions
must be multiples of 16, have neither edge above 3840, an aspect ratio between
1:3 and 3:1, and 655,360–8,294,400 total pixels. Do not resize an approved packet without
updating camera/crop metadata and reviewing its actual new input.

```bash
node level-editor/pipeline/src/refinement/generate-textures.ts <experiment-dir> --prepare
```

This assembles `input.png` and `mask.png`. The first API image is source-textured
+ shaded gray unknown surfaces. The second is the pure-gray `solid.png` rendered
with exactly the same cameras, tile order, framing and fixed-world lighting.
The local mask is still required: alpha zero means editable; nonzero protects
known artwork/background. `--no-mask` omits it from the API request, not from
local source-preservation or baking.

Record actual user approval in `approval.json`: `status: "approved"`,
`approved_by: "user"`, SHA256 `input_sha256`, and a nonempty `geometry_revision`.
Also bind the asset ID, reviewed geometry, solid-sheet hash and ownership
evidence required by `project_reviewed_texture.py`. Hashes bind evidence; they
do not create approval. A material geometry/input change needs renewed review.

```bash
node level-editor/pipeline/src/refinement/generate-textures.ts <experiment-dir> \
  --generate --prompt-variant short --no-mask \
  --lighting-reference <approved-pure-gray-solid.png>
```

The current request is multipart POST `/v1/images/edits`, model
`gpt-image-2.5-sunburst`, quality `high`, exact approved canvas size, one lossless PNG.
It sends two `image[]` fields and no API `mask`. The short prompt requests
consistent missing textures while preserving existing pixels, and explicitly
says to follow gray-surface shading and use image two for lighting, shadows
and shape, returning only the completed first sheet. Optional
`--prompt-suffix` adds asset-specific material instructions. Do not use the old
gatehouse-specific detailed prompt for unrelated assets.

Inspect `generation-short-no-mask-with-lighting/generated-raw.png` and
`generated-preserved.png`. The latter restores protected pixels locally even
if the API modified them. Keep both, `generation.json`, and `api-cache/` request,
response, input, mask and lighting files. Check dimensions, silhouette, texture
scale, all eight viewpoints and tile-to-tile consistency. Never silently rescale
generated output. The raw alternative is retained for an explicit later choice.

### Bake, validate and publish (generation alone is not completion)

After reviewing the fill, bake the selected image back onto the exact approved
geometry using all eight camera transforms and visibility/ownership checks:

```bash
/usr/bin/blender --background <approved-asset.blend> --threads 2 \
  --python level-editor/refinement/blender/bake_reviewed_asset.py -- \
  <experiment-dir>/views.json <selected-generated-preserved.png> <new-bake-dir> 2
```

`project_reviewed_texture.py` reconciles the generated views with the reviewed
packet and projects onto visible eligible surfaces; it is not a single front
decal or a UV unwrap of the contact sheet. `bake_reviewed_asset.py` guards geometry,
outside materials/UVs and input evidence; it saves `worker.blend`, validation and
`actual/textured.png`. Inspect this actual eight-view mesh render, not just the
AI output. Audit seams and alternate views. Keep covered/revealed layers and
receiver ownership separate. The optional batch wrapper `bake_approved_packets.py`
takes a positional jobs JSON with `manifest`, `generated_image`, `output` and
optional `source_blend`; it does not publish anything.

Create a publication plan using the existing `stage_reviewed_publication.py`
schema, binding baseline, catalog, scene/collection, map/source paths, imports,
review manifests and a new output directory. Do not copy Derby's node IDs into
another map's plan.

```bash
/usr/bin/blender --background --threads 2 \
  --python level-editor/refinement/blender/stage_reviewed_publication.py -- <publication-plan.json>
```

This stages geometry/material imports and exports a map plus standalone assets.
Staging is not live integration: validate canonical membership, grouping,
transforms, materials, states and the generated library, then promote the staged
files to the editor paths with rollback evidence. Check the map and asset picker
in the running editor. Track separately: geometry approved, texture generated,
texture baked, publication staged, and live editor integration verified.

## 9. Lighting review

Keep the shared azimuth/elevation configurable and record it in every packet.
Review solid lighting before texture synthesis. If artwork shadows are used to
calibrate lighting, select exact caster-edge and receiver-shadow pixel pairs;
broad regions and arbitrary points are invalid. Annotate each pair directly on
the source image and record confidence and exclusions for foliage, ambient
occlusion, rock, smoke, and painted shading.

Compare directional-sun and finite-point-light hypotheses only after the
landmarks are visually verified. Do not change production lighting from an
unverified fit.

## 10. Animated and revealed assets

Represent stateful objects explicitly. A drawbridge may be one animated mesh
with validated hinge states or separate raised/lowered state components; choose
the representation supported by the runtime and export format. Validate both
states, their masks, occluders, collision geometry, and texture projection.

For buildings with interiors, validate covered and revealed states separately.
The revealed render must match the interior source artwork on the actual
interior receivers, not merely pass a pixel-ownership check.

## 11. Export and editor integration

Export both:

- the complete refined map scene with logical group names;
- standalone named assets for every selectable group.

The export is a reusable script and must write deterministic metadata:
asset ID, display name, source nodes, projection components, masks, states,
materials, geometry hash, UV hash, and validation results.

Integrate only validated candidates into the editor library. Keep a backup of
the last verified publication. Verify:

- map loading;
- group selection selects the complete logical object;
- optional second-click part selection works;
- standalone assets appear in the creation palette;
- covered/revealed and animated states load correctly;
- geometry and textures match the reviewed packet.

Run browser/editor smoke tests and retain the publication manifest, hashes,
screenshots, and rollback path.

## 12. Required worker handoff

Every worker must return:

- final `model.blend` and recipe/script;
- input and modified packets;
- source/mask/state ownership evidence;
- geometry, UV, transform, and outside-object validation;
- before/after renders and any close-ups;
- explicit limitations and unresolved assumptions;
- approval state and texture-generation state.

The coordinator merges only after the packet is reproducible, the review state
is clear, and the editor export validates against the named asset catalog.

## 13. Reusable scripts

### Blender MCP

Use Blender MCP as the normal interactive inspection and review path whenever a
Blender session is available. Through MCP, inspect collections, objects,
materials, cameras, custom ownership properties, parenting, transforms, and
state visibility; run small diagnostic Python snippets; and render screenshots
or close-ups. Keep the frozen baseline untouched.

Use the deterministic background scripts below for packet generation, projection
bakes, exports, and publication staging. MCP is the interactive review path;
the scripts are the reproducible handoff path. Record the `.blend` file, script,
arguments, and output hashes for every accepted change.

The following scripts form the reusable core. They should accept a map config,
asset ID, source image, collection, camera set, and output directory rather
than embedding Derby names or paths.

| Script | Role |
|---|---|
| `blender/refinement_inventory.py` | Inventory meshes, parents, source nodes, masks, states, materials, UVs, and transforms. |
| `blender/group_assets.py` | Reconcile logical groups, stable names, source ownership, and standalone catalog entries. |
| `blender/refinement_workspace.py` | Create frozen input packets and deterministic modified packets. |
| `blender/refinement_review.py` | Render solid, source-known, textured, and context review views. |
| `blender/render_multiview_asset.py` | Render the fixed 4×2 camera sheet and per-view PNGs. |
| `blender/source_projection_bake.py` | Apply source projection with masks, ownership, and protected-pixel checks. |
| `blender/project_reviewed_texture.py` | Reproject an approved texture packet onto reviewed geometry. |
| `blender/occlusion_constraints.py` | Apply covered/revealed and foreground occlusion constraints. |
| `blender/interior_layers.py` | Resolve state-specific interior receivers and patch layers. |
| `blender/review_sunlight.py` | Render deterministic neutral solid lighting with configurable world-space light. |
| `blender/build_review_gallery.py` | Build the pending-only approval gallery and archive prior evidence. |
| `blender/export_editor.py` | Export the complete map and standalone named assets with metadata. |
| `blender/integrate_refinement.py` | Import validated geometry/material packets into a publication stage. |
| `blender/stage_reviewed_publication.py` | Stage guarded publication changes and rollback evidence. |
| `blender/bake_approved_packets.py` | Bake approved texture packets while retaining raw/protected outputs. |
| `blender/verify_publication_assets.py` | Verify hashes, group counts, materials, meshes, and standalone assets. |

The previous generic `--config` examples were illustrative, not implemented
interfaces, and have been removed. Use the actual command parsers and Python
entry points; several core files are libraries rather than standalone CLIs.
For an existing frozen workspace, the implemented modified-packet command is:

```bash
/usr/bin/blender --background <asset.blend> --threads 2 \
  --python level-editor/refinement/blender/refinement_workspace.py -- modified <asset-dir>
python3 level-editor/refinement/blender/build_review_gallery.py \
  <review-candidates.json> <gallery-dir> --pending-only
```

Use `refinement_workspace.py --help` and its `prepare --help` subcommand for
required inventory/grouping/source arguments when creating a workspace.
Section 8 gives the implemented generation, baking and publication commands.
The gallery uses stable asset anchors and asset-plus-content-hash image URLs,
so hiding approved cards cannot show cached images of another asset.
Add `source_trace`, `projection_errors`, and `source_comparison` image fields
to the manifest when appropriate. Keep report image paths local to its directory
or child directories, never relying on `..` in the user's Markdown viewer.

Scripts must fail loudly when required source nodes, masks, receivers, states
or assets are missing; they must not silently fall back to empty/unowned output.

## 14. Map-specific recipes and how to generalize them

Files named `derby_asset_*.py`, `derby_round2_*.py`, `derby_round3_*.py`, and
similar are useful geometry recipes, but they are map-specific worker
implementations. For another map, copy the recipe pattern and parameterize:

- source node IDs and logical asset ID;
- source-image crop and camera set;
- masks, patch layers, and state names;
- measured wall/roof/stair anchors;
- repeated-element counts and phase;
- output and validation paths.

Keep geometry recipes idempotent: running one twice must not add duplicate
meshes, repeated battlements, or extra caps. Each recipe should emit a compact
JSON report containing changed objects, vertex/face counts, source nodes,
repeated-element counts, world-transform drift, and validation results.

Map-specific scripts should call the reusable workspace, projection, review,
and export helpers instead of duplicating their own mask, camera, naming, or
hash logic. This keeps the same review contract across all maps.
