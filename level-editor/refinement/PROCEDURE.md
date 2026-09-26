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

### Check source coverage, not just sampled colors

Exact RGB checks prove that accepted texture pixels retain their colors; they
do not prove that all visible artwork was accepted. Before marking an asset
ready, compare its complete source-visible domain against the native masks,
receiver geometry, and foreground occlusion. Inspect rejected pixels as well as
accepted pixels. Explain each substantial neutral area using the original
artwork: hidden surface, outside the image, foreign ownership, or a defect to
correct. A nonzero texture count is not a completeness check.

Reopen the saved model and inspect its actual materials in all eight views and
every applicable state. Diagnostic source sheets alone cannot establish that
the material was saved correctly. Check adjacent assets together where a mask
delegates artwork to another asset; that neighbor must actually cover it,
without a gap or overlapping coplanar surfaces. Broad proxy geometry must not
hide source-visible pixels merely because it intersects a projection ray.

Also render the actual saved materials from the original source camera beside
the matching artwork for each state. Derive the audit domain independently of
the acceptance masks: otherwise an erroneous exclusion disappears from both
the texture and its audit. When a patch removes a foreground structure, include
the newly exposed area in the revealed-state audit instead of subtracting the
covered-state silhouette. Exact preservation of a previously approved donor
proves preservation, not source completeness; regrouped assets still need this
comparison.

Bind the coverage review to the model and modified packet hashes. Missing,
failed, or stale coverage evidence must block readiness. For terrain, review
the proposed ground domain against the artwork explicitly; the complement of
scenery masks can still contain omitted structures and props.

For an exterior-only workspace, an inaccurate generic ground plane may be
excluded from source-ray occlusion with an explicit
`source_projection_ground_exclusion` in `workspace.json`. It must contain
`version: 1`, the exact `asset_id` and `object_name`, a nonempty `rationale`,
`source_sha256`, and an absolute `evidence` path with `evidence_sha256`.
The helper accepts only one existing, visible, nonreceiver mesh whose unique
source node is `ground`. It rejects absent/shared names, changed evidence,
receiver exclusions, and layered workspaces. This changes neither the ground
model nor display geometry. Native masks, self-occlusion and all other source
occluders remain active. The full declaration is saved in ownership and camera
review records. Use this only when source artwork demonstrates a terrain-depth
mismatch, and record the terrain requirement for later integration.

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

For paired texture endpoints, keep one primary `texture-review.json` marked
`ready-for-user`. Its `texture_states` list names each additional endpoint with
`id`, `name`, and `experiment`; that experiment has a complete independent
review marked `supplemental`. Both experiments must bind the same approved
geometry revision. The shared texture gallery displays both sets of images on
one card, and a texture decision archives and binds both baked models.

For unchanged revealed materials, the primary review may additionally include
`material_states`: entries with `id`, `name`, `textured`, `validation`,
`actual_sheet_sha256`, and `validation_sha256`. The state validation binds
`baked_model_sha256` and records `materials_preserved: true` only after comparing
the original materials/UVs and inspecting the actual state render. These images
and reports are displayed and included in the same texture decision.

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

When explicitly authorized to route the same model through OpenRouter, append
`--provider openrouter` to the generation command. The default remains OpenAI.
This transport reads `OPENROUTER_API_KEY` from the same private environment file,
discovers and archives current image-endpoint capabilities, then sends JSON to
`https://openrouter.ai/api/v1/images` using `openai/gpt-image-2.5-sunburst`.
The input and pure-gray sheet become ordered `input_references`; quality remains
high, `size` remains the exact approved canvas, and output is requested as PNG.
It requires `--no-mask`, while local protection still uses the approved mask.
Provider and endpoint are part of cache identity and provenance; OpenRouter
outputs use the suffix `-openrouter` so previous raw results stay intact.
Returned dimensions and PNG format are checked before composing or baking;
unsupported sizing must fail rather than resize an approved projection packet.

### Single planar atlas exception

A reviewed planar background can use one exact existing atlas instead of eight
redundant projected views. First check its approved ownership report: a fully
known atlas needs no generation. `prepare_planar_texture_packet.py` validates the
current recorded approval, source/texture/mask hashes, and audited opaque GLB.
It derives physical coverage from the existing UV triangles and protects holes
and outside pixels. The current implementation requires a single planar mesh,
one atlas, and the same uniform pure-gray lighting in every approved solid view.
It copies original atlas dimensions and pixels without resizing or reframing.

```bash
python3 level-editor/refinement/prepare_planar_texture_packet.py \
  <review-manifest.json> <asset-id> <new-experiment> \
  <approved-source.png> <approved-known-mask.png> <approved-protected-atlas.png>
```

The normal generation driver recognizes `projection_kind: planar-atlas` and uses
a single-image prompt with the exact aligned `solid.png` as image two. Inspect
the prepared input before calling the API. For a ground atlas, missing object
cutouts represent unseen ground; request continuation of surrounding terrain
materials rather than replacement scenery. Preserve the local protected-pixel
composite and both raw and preserved outputs.

```bash
/usr/bin/blender --background <experiment>/approved-model.blend --threads 2 \
  --python level-editor/refinement/blender/bake_planar_texture.py -- \
  <experiment> <generated-preserved.png> <new-bake-dir>
```

This replaces only the separate worker's atlas image, checks packed source pixels,
geometry, UVs and outside materials, then renders the original eight review
cameras. All eight actual material views still require inspection. It never
publishes the result or changes the approved worker.

### Bake, validate and publish (generation alone is not completion)

After reviewing the fill, bake the selected image back onto the exact approved
geometry using all eight camera transforms and visibility/ownership checks:

```bash
/usr/bin/blender --background <approved-asset.blend> --threads 2 \
  --python level-editor/refinement/blender/bake_reviewed_asset.py -- \
  <experiment-dir>/views.json <selected-generated-preserved.png> <new-bake-dir> 2
```

For optional tone reconciliation, append `<generated-raw.png>` after the final
`2` argument. Keep `generated-preserved.png` as the selected image. The raw
reference estimates local color differences on observed pixels; the correction
changes only inferred pixels and never overwrites protected source atlas texels.
Its path and SHA-256 are recorded and checked as bake evidence. Use a fresh bake
directory and inspect all eight actual views again. This correction cannot align
inconsistent generated hoop, plank, or masonry positions across viewpoints.

`project_reviewed_texture.py` reconciles the generated views with the reviewed
packet and projects onto visible eligible surfaces; it is not a single front
decal or a UV unwrap of the contact sheet. `bake_reviewed_asset.py` guards geometry,
outside materials/UVs and input evidence; it saves `worker.blend`, validation and
`actual/textured.png`. Inspect this actual eight-view mesh render, not just the
AI output. Audit seams and alternate views. Keep covered/revealed layers and
receiver ownership separate. The optional batch wrapper `bake_approved_packets.py`
takes a positional jobs JSON with `manifest`, `generated_image`, `output` and
optional `source_blend`; it does not publish anything.

When near-tie camera blending visibly averages incompatible generated details,
a fresh experiment may explicitly set `texture_view_selection` to
`best-facing-single` in its guarded `views.json`. Each unknown texel uses its
highest-facing visible editable view; ties choose projected pixel density,
then stable view index. The default remains `near-tie-blend`. Masks, source
protection and first-hit checks are unchanged. Reuse cached generation only
when approved inputs and model hashes match exactly, and inspect all eight
actual views for newly introduced seams before accepting the result.

For an exterior-only fill, declare `texture_receiver_object_names` in the bake
manifest as the exact eligible mesh names. Keep the complete reviewed object
set in the visibility scene and keep the original projection layers unchanged.
The bake restricts receiver writes to that scope and guards every other mesh's
materials and UVs, including interior meshes in the same logical asset. Never
apply a covered exterior generated sheet to revealed interior receivers merely
because they share an asset group or source node.

If an approved thin shell has inverted visible-face normals, diagnose actual
camera visibility before changing geometry. `texture_two_sided_object_names`
can explicitly permit absolute-facing view scores for those receiver meshes;
it still requires first-hit visibility and the editable mask, and changes only
unknown texture sampling. Record the affected meshes and normal/visibility
evidence. Do not enable this globally to conceal topology problems.

For mixed room/exterior meshes, `texture_receiver_face_indices` can restrict the
write to explicit polygon indices within each named receiver. Pair it with a
new `texture_material_suffix` so the bake appends a separate atlas/material/UV
layer rather than replacing the room atlas. Guard original atlas bytes, existing
UV layers and unselected face assignments, and compare actual revealed renders.
If the same polygon represents both room and exterior sides, a single UV/material
cannot independently texture those sides; a separate surface representation is
required before treating that region as filled.

If both states see the same side of a polygon, use explicit covered/revealed
material variants; opposite-facing faces alone cannot separate those pixels.
`blender/material_states.py` applies a complete reviewed polygon-to-material
mapping and validates all slots before mutation. Keep both atlases and UV layers,
export both state variants, and compare actual revealed renders byte-for-byte.
The editor/patch integration must switch these materials with visibility; a
covered-state export alone is not a completed revealed-state integration.
When cached covered and revealed generations disagree on shared surface colors
or patterns, bake each endpoint independently and retain its own reviewed worker.
Do not stack the second fill onto the first worker and then present that merged
material set against both generated sheets. Compare each state's actual eight
views against its matching preserved generation; gray coverage alone cannot
detect this cross-state contamination. The publication compiler can preserve
these separate reviewed workers as explicit texture states.

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
Calibrate each map independently. The historical helper default is Derby's
setting and must not silently establish another map's sun direction. Pass an
explicit `lighting` configuration to `prepare()` for new map workspaces.
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

Before reporting completion, reconcile every review item and every catalog
source node against the applied publication chain. Record geometry approval,
texture generation (or an evidenced reason it is unnecessary), validated bake,
and live integration separately. A pending-only gallery with zero cards proves
only that no geometry decisions remain. It does not prove texture completion.
Check supporting meshes shown only as context in split review packets: each
still needs an explicit owner for any required texture fill. Replace obsolete
lighting holds and generation-pending labels with verified current status; do
not mark an item integrated merely because its output exists on disk.

Compare approved geometry with the exported scene as well as with the texture
worker. An old export can contain the correct object names but obsolete meshes.
Conversely, a split worker can contain only part of a source node that the live
scene has since combined. Before replacing that node, compare its full topology
and world-space surface coverage. Preserve any additional accepted faces by
using the complete current receiver or a validated scoped material transfer;
never replace a complete live mesh with a matching-name subset.

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

### Map publication format

Map exports use `<map>.level3d.json` and one reusable local catalog under
`map-assets/3d-assets/`. Both map instances and palette entries reference the same
`<source-map>/<asset-id>/model.glb`, with lowercase source-map directories.
Resolve descriptors and models through `3d-assets/index.json`; do not construct
paths from the asset ID alone. Private payloads are embedded; `blobs/` contains only
cross-asset payloads whose sharing saves at least 256 KiB. Named scenes are
reusable appearances, never map-coordinate versions.
See [the library format](../docs/library-format.md).

After publication, run `pnpm --filter app prepare:library` from `level-editor/`
to refresh the static links and map index used by the editor's HTTP library.
The editor saves map copies in browser OPFS; use **Download** to export a map JSON
for review or publication. It never writes assets or published maps over HTTP.

`scene_filename` in publication plans must end in `.level3d.json`.
`export_editor(..., asset_id=None)` requires the source `level` and JSON output.
It writes local catalog assets and placed instances directly. Temporary Blender
geometry and raw standalone exports are conversion inputs, not published maps.
The staging wrapper exports selected assets/appearances first, then creates the
map and canonical palette references together. Raw asset exports are retained in
`backups/asset-export/`; placement evidence is outside reusable descriptors.

`stage_reviewed_publication.py` reads framing from `editor_document` or the current
library document. Otherwise it starts unbounded. Editing has no fixed boundary;
`exportBounds` records an optional intentional compile crop.

Mission triggers, patch-state graphics and map coordinates remain in map JSON.
The local asset contains only reusable appearances and source identity metadata.
Ordinary float32 conversion roundoff is acceptable; topology, textures, ownership,
collision flags and mission behavior must be preserved. No custom precision
extension is part of the format.

`verify_publication_assets.py` verifies pinned resources and authored coverage.
`prepare_publication_browser.py` preserves editor poses when local export origins
change, writes `browser-document.level3d.json`, and audits the runtime format.
Use `--document <staged-map.level3d.json>` for a first publication.
`promote_staged_publication.py` publishes the canonical map catalog and palette
index with the existing lock, hash guards, backups and rollback behavior. Resources
are installed before their manifests. Keep approval and independent handoff checks
in the existing workflow; conversion is not a new approval.

Frozen handoffs created before this format must be imported explicitly, without
editing their original files:

```bash
python3 level-editor/refinement/scene_manifest.py \
  <old-stage/map.scene.glb> <old-stage/map.level3d.json> <fresh-import-stage>
```

Keep the frozen workers and approval evidence. Run the current staging and browser
verification tools against the imported JSON/assets before preparing promotion;
previously prepared promotion manifests must not be reused across a format change.
