# Sherwood source-pixel ownership

Follow [PROCEDURE §4](../../refinement/PROCEDURE.md#4-use-masks-and-patches-as-ownership-authority)
and [the source-mask reprojection interface](../../refinement/reprojection.md).
Grouping approval establishes which meshes form an asset. It does not establish
which painted pixels belong to those meshes.

## Current preview limitation

The current `textures/reproject-v2` worker, and the grouping candidate derived
from it, are geometry/grouping previews. The Sherwood Day bake currently calls
`source_projection_bake.bake` **without `source_mask_manifest`**. Its NPZ texel
provenance records first-hit visibility, not reviewed native source ownership.
The ground cleanup mask and separate physical foliage opacity do not close that
gap. Do not treat those previews as mask-validated source textures or use their
protected-source flags as final texture authority.

The four already-generated OpenRouter candidates are bound to those earlier
packets. Their protected-pixel checks prove only that the old packet was preserved;
they do not prove that its original-art pixels belonged to the correct receivers.
After corrected reprojection, prepare fresh packets and invalidate stale generation
and bake bindings. No additional synthesis or texture publication should proceed
from the preview worker.

## Required sequence after grouping review

1. Freeze the accepted grouping and unchanged geometry. Inventory the native
   Sherwood mask PNGs, layer/patch metadata and exact original artwork for each
   applicable state. Keep Day artwork separate from animated-tree source layers.
2. Audit mask assignments against original art at source resolution. Assign masks
   explicitly to source nodes and, where needed, projection components. In
   particular, the ladder/tree split of source 24 and house/access split of source
   102 need component-level ownership. A merged group is not permission to use a
   broad union on every component. Bounding boxes, proximity, a render ID buffer,
   or mask indices resembling obstacle numbers are not ownership evidence.
3. Write a reviewed `occlusion_constraints.py` source-mask manifest. Bind each
   projection to the exact source PNG SHA-256 and state. Record accepted mask
   indices, reviewed foreground exclusions and any state-specific occluder
   constraints. Hash the manifest, inventory and every referenced bitmap.
   Explicitly check coverage: the shared bake leaves unassigned objects
   unconstrained, so merely passing a manifest is insufficient. Receivers with
   unresolved ownership must remain unknown and be reported, not silently
   accepted through the unconstrained fallback.
4. Reproject original RGB through **both** reviewed ownership masks and source
   camera visibility. Keep physical alpha, source ownership and generation/edit
   eligibility separate. Reject foreign art, hidden surfaces and out-of-image
   samples. Preserve world geometry and UVs unless a separately reviewed change
   explicitly requires otherwise. Grouping changes must not copy a neighbouring
   roof, branch, ladder or terrain texture onto the wrong component.
5. Validate accepted and rejected pixels, foreign and duplicate ownership,
   outside-object preservation, exact accepted source RGB, and geometry/UV/world
   transforms. Inspect adjacent assets together and show mask overlays on raw
   original artwork, including an independent source-visible domain check so an
   erroneous exclusion cannot hide itself. Record unresolved gaps explicitly.
6. Only then prepare fresh source-textured and solid Sunburst sheets. The first
   tile must be the original camera. Local editable masks protect accepted source
   texels; `--no-mask` refers only to omitting an API mask and never disables local
   ownership/protection. Synthesize genuinely unknown surfaces, bake using the
   frozen cameras and ownership, and require zero changes to accepted source RGB
   or physical opacity. Remaining uncovered texels stay explicit until completed.
7. Review the actual baked worker and exported materials before publication.
   Bind source artwork, native masks, assignments, worker geometry, camera sheets,
   generated output and validation receipts to the reviewed revision.

Keep the current grouping gallery and submitted decisions stable while the user
reviews it. The corrected mask-constrained texture preview will be a separate
revision; it must not overwrite or silently rebind existing grouping evidence.

## Executable audit and synthesis guard

`prepare_mask_audit.py` renders all 166 native masks beside the original Day
artwork. `source-mask-candidates.json` records explicit semantic associations,
inspected comparison-image hashes, referenced bitmap hashes and unresolved
boundaries. `build_mask_review.py` renders those associations and their proposed
foreground exclusions; it does not approve them.

`compile_source_masks.py --output <new-audit-directory>` compiles only inspected
rules. Every unresolved or absent assignment gets an explicit black bitmap;
the coverage check rejects any receiver that would reach the shared API's
unconstrained fallback. The compiler's `synthesis_ready` field remains false
while source nodes, canopy layers or the terrain domain are unresolved.

`reproject_masked_preview.py` is an **audit-only** Day pass. It opens the approved
grouped worker, resets RGB, projects through reviewed masks and first-hit depth
into the existing UV atlases, and retains physical opacity. It does not promote
unresolved regions to hidden surfaces or synthesize them. `verify_masked_preview.py`
reopens the saved worker and checks the packed RGB, source pixel coordinates,
mask membership, geometry/UV fingerprint and complete receiver coverage.
The `reproject-v3-audit` artifact uses the first 44 inspected Day assignments;
subsequent mask inspections are separate from that frozen bake.

`texture_packets.py` now requires a `source_ownership_validation` binding with
an immutable receipt path and SHA-256 before preparing, generating or baking.
The receipt must say `status: PASS`, bind the exact `worker_sha256`, report zero
`unresolved_source_nodes` and `unconstrained_receivers`, and include nonempty
hashed `evidence`. This final receipt also requires the visual and independent
domain checks in step 5 above; the partial audit verifier cannot produce it.
Previously prepared packets and the four old OpenRouter outputs cannot bypass
this guard. Rebuild them after the full source audit passes.
