# Map data: editor → game

Compilation reads **placed assets and the editor scene only**. One-time recovery
from existing levels may populate asset-local metadata; exporting never reads
those levels. Moving, rotating or duplicating an asset must carry its gameplay
with it. Global indices and connections are rebuilt after placement.

**Status:** “Working” means implemented with focused tests, not verified parity
with Derby/York. “Partial” identifies a remaining gap. “Planned” describes the
intended construction, not functionality available today.

| Original map information | Construction from the editor | Status |
|---|---|---|
| Background image and minimap | Render placed models/textures; downsample the minimap. | Working |
| Character occlusion | Bake a 16-bit depth PNG from scene geometry. | Working for static scenes |
| Projectile/view/obstacle masks and masking polylines | Rasterize asset-local coverage triangles after placement; rebuild masking boundaries, receiving layers and obstacle/state links. A depth PNG alone does **not** replace all these semantics. | Partial: explicit mask authoring, raster compilation, ZIP packaging and native state links tested; recovery/publication and visual/depth state integration remain unfinished |
| Walkable regions and layers | Transform asset-local surface polygons and heights; join coplanar regions, local multi-plane regions or matching authored boundary edges across assets, then assign fresh sectors/layers. | Partial: flat/sloped surfaces, holes and cross-asset multi-plane joins tested; join recovery/publication and full-map connectivity unfinished |
| Movement blockers | Transform explicit asset-local movement contours; optionally select permanent part/volume solids and intersect them with walkable surfaces. Sight states stay independent. | Working in synthetic tests; recovered ownership still needs review |
| Openings in movement collision | Asset-local clearances remove only the owning asset's derived collision on the matching plane; sight geometry and other assets remain intact. | Working in compiler/runtime tests; recovery geometry failures remain explicit gaps |
| Navigation graph and fast-find grid | Engine constructs routing and spatial lookup structures from compiled geometry. No copied grids or graph bytes. | Working on synthetic maps |
| Sight/physical obstacles | Transform asset-local shapes, per-vertex heights and solid/opaque flags. Explicit transition references select initial/applied obstacles. | Static geometry working; sight transitions verified through native initialization, apply and reset; recovered state ownership still incomplete |
| Projection surfaces / elevation | Generate height planes linked to the new movement areas. | Partial: planar surfaces; elevation-boundary links unfinished |
| Doors, gates and lock rules | Transform local endpoints and optional click polygons; resolve neighbours geometrically and retain initial/alternate actor lock rules. Asset-local transition links either trigger state changes from doors or swap door permissions. | Compiler/native links implemented; recovered ownership and coverage incomplete |
| Building interiors | Asset-local interior definitions and entrances; matching positioned sockets with opposing directions join independent assets into shared virtual rooms. | Compiler/native tests cover separate, rotated and duplicated assemblies; all recovered room memberships match, including York's shared rooms; definitions remain unpublished; occupants are mission-owned |
| Lifts / special traversal | Asset-local traversal surfaces, type, direction and endpoints; explicit local join sockets combine placed segments into one sector with multiple height planes. | Working in synthetic compiler/runtime tests, including rotated/duplicated compound lifts; recovered metadata not yet published; changing lift surfaces unfinished |
| Jump zones and paired jump edges | Transform asset-local 3D edges and receiving contours; resolve landing anchors, regenerate crossed destination links and preserve long-jump/helper rules. Explicit local sockets pair edges owned by different assets after placement. | All 173 recovered pairs match reference geometry and flags; native registration verified; publication and traversal fidelity remain unfinished |
| Surface materials | Transform asset-local material polygons; rebuild ground, obstacle and receiving-surface links independently. Preserve receiving defaults, footprints and overlap priority. | Compiler/native tests pass; all nine recovery drafts include receiving materials; publication and geometry coverage remain unfinished |
| Light/shadow regions | Transform asset-local planar contours, resolve ordinary or traversal receiving layers and preserve ambience filters. | Partial: compiler/runtime tests cover day/night filtering, stair shadows and interior links; multi-plane regions, receiving gaps and ownership remain unfinished |
| Environmental sound sources | Transform asset-local emitter polylines; retain sample IDs, timing, volume falloff, acoustic altitude, noise-covering distance and ambience filters. Global emitters need no position. | Partial: compiler/runtime coverage; ambiguous local ownership remains in recovery reports |
| Animated scenery / effects | Export asset animations, sprite resources, placement and display rules. | Planned |
| Interactive patches / state changes | Asset-local transitions compile initial/applied movement contours, sight-obstacle references and door links, trigger zones and fresh state bindings across affected navigation areas. | Partial: movement, sight and door bindings implemented; changing visuals, masks and asset recovery remain unfinished |
| Map settings | Scene identity/export bounds; terrain assets supply forest behaviour and default material. Ambience is selected by the mission. | Working in compiler/runtime tests; recovered terrain metadata unpublished |
| Resource banks and references | Package generated resources and resolve shared sprite/audio/profile dependencies. | Partial: baked images; shared resources use the base installation |

The following information belongs to **missions referencing a map**, not map
assets or map export. A separate mission-authoring/export workflow is planned.
Map exports neither require nor generate player spawns or NPCs.

| Mission information | Intended construction | Status |
|---|---|---|
| Player starting locations | Mission-owned placements, resolved against the referenced compiled map. Never embedded in map assets. | Planned |
| Soldiers, civilians, targets and rescue characters | Actor assets plus editor placement, facing, profiles and initial behaviour. | Planned |
| Items, bonuses and scrolls | Item assets plus placement and gameplay properties. | Planned |
| Building occupants | Actor-to-interior associations resolved after placement. | Planned |
| Patrol paths | Editor-authored waypoints with waits/actions, resolved against compiled navigation. | Planned |
| AI tactics | Authored reinforcement, ambush, seek and archery points/regions. | Planned |
| Moving carts | Moving-object assets with routes, collision and animation metadata. | Planned |
| Script points, lines and sectors | Transform named local markers/regions; generate fresh runtime references. | Planned |
| Mission scripts, objectives and triggers | Authored behaviours referencing scene instances and named asset features. | Planned |
| Mission settings | Mission-specific ambience, objectives and initial map state/door-rule selection. | Planned |

The ZIP additionally includes `editor/<map>.rhlos-map.json`, preserving unsaved
scene edits for reopening with the pinned asset library. This is editor source,
not an original game data type. **Full extracted-map gameplay parity is not yet
verified.**

The offline recovery report includes ground reconstruction area differences on
the engine's integer coordinate grid. Terrain drafts fill placed-object cutouts
and move the exclusions into asset-local movement blockers. A zero area difference
alone does not prove correct ownership; adjacent assets, remaining terrain holes,
state-dependent exclusions and elevated ground still require review.

Each recovered draft now includes a compiler-schema candidate when validation
passes. `definitionValidation` lists per-asset failures. Schema validity does not
mean all gameplay was recovered or that the assembled map compiles; drafts stay
separate from the published asset library until their missing information is resolved.

Recovery includes geometry-only assets: local collision shapes remain active
unless explicitly replaced by authored movement contours. Mission-authored
surface geometry is retained without map-wide projection references. Standalone
passages are assigned independently; an interior's entrances remain grouped.
`staticGeometryDiagnostic` checks a disposable copy of the current visible
geometry without state/population behaviours. Its success does not authorize
export or establish gameplay parity; `candidateCompilation` checks the full scene.

Split source surfaces are recovered using each asset part's own footprint;
overlapping or uncovered portions remain explicit ownership gaps. The latest
recovery drafts for Derby, Sherwood, Lincoln, Leicester, Nottingham, Croisement01, Croisement02 and Croisement03
pass the static base-geometry check, excluding explicitly counted movement transitions.
All eight also construct their compiled movement areas, sight obstacles and grids
in the native engine without a datadir. York passes both checks using staged
canonical tower, golden timber house and stone-shop assets, including the tower's
previously missing elevated door landing: 194 movement areas, 1,161 sight obstacles,
244 doors and 72 jump pairs construct successfully after door ownership recovery.
`export-gameplay-diagnostics.ts` generates
these explicitly labelled static probes from draft assets; the ignored
`recovered_static_exports_construct_native_geometry` test reads their manifest via
`ROBIN_ASSET_MAP_DIAGNOSTICS`. This checks construction, not movement/state fidelity.
These are unpublished drafts, not completed map exports or in-game round-trip
parity results. All nine recovered maps have now passed static construction;
no map has yet been certified at full parity, and authored maps still require
published gameplay definitions for their assets.

Ordinary walkable surfaces can declare `navigationJoins`: pairs of local 3D
endpoints on an outer edge, alongside an asset-local `navigationRegion` label.
Compilation validates each edge against its surface, transforms it with the
asset and joins only coincident, opposing boundary edges from different placements.
The assembled region retains each receiving plane and material definition.
Unmatched edges leave independent regions and produce a diagnostic; overlapping
copies, multiple matches and sockets away from the surface boundary fail.
Rotation and duplication tests preserve independent assemblies. Two separate
assets export exactly the existing multi-plane native fixture, whose reachability
check crosses the plane boundary without a door or lift. Packet conversion retains
the local edge definitions without runtime sector identities.

A staged Lincoln north-curtain pair uses this metadata on the east and west wall
assets. Its complete baseline geometry is unchanged; moving either wall one pixel
east detaches the join and increases movement areas from 113 to 114. All three
descriptors load natively with 654 sight obstacles, 89 doors and ten jump pairs.
The initial authored surface drafts and diagnostics are under
`work/map-compile/lincoln-navigation-join-native`. Repeatable migration now uses
`refinement/catalogs/lincoln-navigation-joins.json`, pinned to the source and both
asset models. Recovery validates each named surface and source owner, requires
one shared ordinary source movement region and checks the complete assembled seam
before modifying any packets. Stale pins, conflicting authoring, detached edges
and attempts to join distinct source regions fail. Source indices remain confined
to the migration recipe/report; generated asset definitions contain local edges
and local region labels only.

From `level-editor`, regenerate the current Lincoln drafts with:

```sh
node --max-old-space-size=1536 pipeline/src/recover-asset-gameplay.ts \
  --library work/map-compile/projection-material-library \
  --map work/map-compile/projection-material-library/scenes/lincoln.rhlos-map.json \
  --source library/game-data/Data/Levels/Lincoln.rhp.json \
  --mask-definitions refinement/catalogs/lincoln-masks.json \
  --navigation-definitions refinement/catalogs/lincoln-navigation-joins.json \
  --out work/map-compile/lincoln-navigation-join-recovery
```

Freshly recovered definitions reproduce the previous baseline exactly and both
independent wall moves pass native construction again. Those diagnostics are under
`work/map-compile/lincoln-reviewed-navigation-native`. The definitions remain
unpublished; recovery of the other maps' joins is unfinished. A full-edge candidate
audit found no exact Derby seam in the tested drafts; boundary/height differences
still require authoring work. This does not certify full-map connectivity or actor
traversal on recovered maps.

`pipeline/src/verify-reviewed-navigation-recovery.ts` checks the recovered packet
and compiler candidate against every reviewed edge definition, revalidates pins
and source ownership, compiles the baseline, then moves each owner independently.
It writes native descriptors for successful cases and retains placement failures;
any failure leaves `complete: false` and returns a nonzero exit status. Existing
success manifests are invalidated before inputs are read. This checks assembly
and detachment, not full source-map topology or actor traversal. For example:

```sh
node --max-old-space-size=1536 pipeline/src/verify-reviewed-navigation-recovery.ts \
  --library work/map-compile/projection-material-library \
  --map work/map-compile/projection-material-library/scenes/lincoln.rhlos-map.json \
  --source library/game-data/Data/Levels/Lincoln.rhp.json \
  --recovery work/map-compile/lincoln-navigation-join-recovery \
  --navigation-definitions refinement/catalogs/lincoln-navigation-joins.json \
  --out work/map-compile/lincoln-navigation-cli-native
```

Nottingham's `refinement/catalogs/nottingham-navigation-joins.json` supplies four
exact seams in three groups across seven assets: south gate/tower/curtain wall 2,
the sloped curtain walls 3/4, and the southwest curtain's north/south segments.
Its recovered baseline preserves all geometry and bindings after remapping sector
identities and projection-array order. Drafts are under
`work/map-compile/nottingham-navigation-join-recovery`. The baseline and six
independent one-pixel westward moves construct natively, with 114 movement areas,
741 sight obstacles, 172 doors and 38 jump pairs at baseline.

The north segment of the southwest curtain still fails movement checks in either
direction because the neighboring stair's inside endpoint loses its receiving
surface. Wall 4 also cannot move east within the existing export frame. Both
directional verifier manifests remain incomplete under
`work/map-compile/nottingham-reviewed-navigation-native` and
`work/map-compile/nottingham-reviewed-navigation-west-native`. The seven successful
westward/baseline construction cases are retained separately under
`work/map-compile/nottingham-navigation-construction-native`, with the excluded
placement failure recorded explicitly. These definitions remain unpublished.
The full-edge audit also found eleven candidate edges in York. Leicester,
Sherwood and the three crossing maps had no matches in the tested drafts. This
audit does not cover partial-edge overlaps or certify that unmatched regions
should remain disconnected.

York's `refinement/catalogs/york-navigation-joins.json` recovers three reviewed
groups across six assets: castle east round tower/great hall, cathedral precinct
terrain/stone causeway, and the west precinct footbridge/city wall. Their combined
baseline retains all geometry and bindings after sector identity remapping:
192 movement areas, 1,373 sight obstacles, 254 doors and 72 jump pairs. Drafts are
under `work/map-compile/york-reviewed-join-recovery`; the verifier output is under
`work/map-compile/york-selected-navigation-native`. Five independent one-pixel
eastward moves pass compilation. Moving the causeway fails its doorway's outside
receiving-height check (157.9875 authored versus 158.0735 on the neighboring
slope), so the placement manifest remains incomplete. The baseline and five
successful moves load natively; their construction manifest explicitly records
the excluded failure in `work/map-compile/york-navigation-construction-native`.

Seven other candidate York groups remain unreviewed. Applying all ten groups
changed movement areas from 192 to 195 and projection/sight records from 1,373 to
1,330. Isolated probes show three groups change motion topology, while four change
projection partitions and associated references. Exact edge coincidence alone
therefore does not establish complete region ownership or equivalent gameplay.
The probes and comparisons remain under `work/map-compile/york-navigation-group-probes`.
These differences need comparison against intended source topology; they are not
automatically improvements or regressions. No York join definitions are published,
and full-map connectivity/state/actor traversal remain unverified.

`pipeline/src/compare-projection-coverage.ts` compares the union of receiving
polygons on the compiler's fixed coordinate grid, grouped by exact top/bottom
planes, receiving motion area, flags and ordered material definitions. It resolves
rebuilt motion/material indices, including blocker constructor slots, and rejects
ambiguous or invalid receiving references. It preserves differences in height,
materials or coverage even when record counts happen to agree. Tests distinguish
an equivalent quad subdivision from a missing triangle and changed receiving rules.
This comparison excludes overlapping-plane priority, non-projection geometry,
state references and actor traversal.

The isolated York inner-east curtain join reduces projection records by 25 while
preserving every compared coverage group exactly. Its non-projection data also
matches after motion/interior reference remapping, and both variants load natively
with 192 movement areas, 254 doors and 72 jump pairs. The native probes are under
`work/map-compile/york-inner-wall-partition-native`. Native receiving queries now
expose a real elevation difference despite the exact coverage comparison: 51,381
half-pixel samples include 28,285 receiving points, of which 28,268 differ by up to
0.000015258789 in height. Coverage and material selection match. Comparing the
baseline with itself gives zero differences. The native loader constructs planes
from the first three polygon vertices, so a different subdivision can change
float32 arithmetic even for mathematically identical planes. The join remains
outside the reviewed catalog. Preserving authored receiving planes independently
of subdivision, receiving-priority checks and actor traversal remain necessary.

The ignored native test
`recovered_projection_partitions_preserve_sampled_runtime_queries` reads a
`ROBIN_PROJECTION_COMPARISON` manifest with `before`/`after` descriptor paths and
`cases` containing `before_sector`, `after_sector`, `layer` and inclusive
`bounds: [min_x, min_y, max_x, max_y]`. It queries the runtime receiver, elevation
and material at integer and half-pixel positions, writes a sibling `.report.json`
file, and fails on any difference. This is a sampled check, not continuous-space
or actor-traversal certification. The York manifest is `projection-comparison.json`;
`projection-self-comparison.json` supplies the passing control.
The east bridge terrace candidate instead changes material bindings across
1.366211 square pixels. The riverside wall and middle outer bastion candidates
retain smaller nonzero coverage differences; no tolerance was used to accept them.
Detailed comparisons are under `work/map-compile/york-navigation-group-probes/verified-coverage-*.json`.

The native compiler interchange accepts typed mask bitmaps with character and
projectile polylines, view flags and regenerated sight-obstacle references.
Mask-state transitions reference the compiled array; loading rebuilds the native
per-layer mask references, including interleaved input layers. Mask-only transitions
can initialize, apply and reset without mission actors. Invalid type combinations,
missing layers/obstacles, malformed bitmap rows and multiply controlled masks are
rejected before loading can skip a mask and shift the references. The editor's
binary-silhouette encoder has shared fixtures checked by the native decoder,
including partial bytes, transparent rows and runs longer than one control byte
can represent. Incompressible rows exceeding the format's byte limit require
narrower bake tiles and fail explicitly. This establishes the interchange and
encoding, not full-map mask parity.

Assets can now define local coverage triangles, a receiving-surface anchor,
character/projectile masking boundaries, view flags and local obstacle IDs.
Compilation transforms this geometry, rasterizes binary coverage in 1024-pixel
tiles and regenerates front masking polylines, preserving concave vertical steps.
Character boundaries use projected coordinates; projectile boundaries use world
XY, with obstacle links supplying altitude tests. Explicit triangles preserve
cutouts and can include multiple surfaces; they are not inferred from a bounding
box or an unchanged screen bitmap. Local initial/applied mask IDs bind every
generated tile independently for each placed copy. Tests cover movement,
elevation, rotation, duplication, holes, wide-mask seams, packet conversion and
ZIP retention. An editor-generated fixture verifies native coverage, masking
rules and apply/reset behavior without source-level files or mission actors.
Existing map assets still need recovered/authored coverage and boundaries;
automatic extraction from textured meshes, visual-state resources and coordinated
depth-buffer changes remain unfinished. Assets can explicitly declare
`maskOcclusionNodes` for parts whose complete sprite occlusion is controlled by
their typed masks. Color baking retains those parts; depth baking omits only
their geometry and renders the surfaces behind them. Other parts retain their
depth contribution. This prevents static mesh depth from overriding mask
deactivation for the declared parts. It requires complete authored coverage:
the compiler does not infer this declaration from a partial mask set. Existing
assets have not yet been certified or opted in, and visual-state resources still
need integration, so this does not establish full-map mask parity.
The browser GPU test verifies identical color pixels, exposed underlying ground
depth for a declared part, and unchanged depth for an unrelated part. Unit tests
also verify declaration validation, packet conversion and visibility restoration
after a failed bake.

The Derby southwest postern is not yet eligible for mask-controlled depth. Its
other linked masks, 67/68, lack 72/98 pixels of mesh support (14/19 interior).
The coverage audit reports 11/18 separate connected repair regions, including a
33-pixel gap at `[471,2319,484,2326]` and a 32-pixel gap at
`[581,2469,591,2480]` (exclusive upper bounds). Adding the postern's collision
volume surfaces in a diagnostic probe still leaves 70/7 pixels unsupported.
Masks 70/71 remain fully supported. No depth declaration has been added to this
asset; completing two masks does not certify its other parts.

```sh
node pipeline/src/audit-mask-surfaces.ts \
  --library work/map-compile/projection-material-library \
  --map work/map-compile/projection-material-library/scenes/derby.rhlos-map.json \
  --source library/game-data/Data/Levels/Derby.rhp.json \
  --asset derby-southwest-postern --masks 67,68,70,71 \
  --out work/map-compile/postern-mask-coverage.json
```

The one-time bitmap recovery helper strictly decodes source scanlines and merges
coverage into nonoverlapping screen-space rectangles without filling cutouts.
`node --max-old-space-size=1536 pipeline/src/audit-mask-bitmaps.ts library/game-data/Data/Levels/*.rhp.json`
(from `level-editor`) verifies every pixel after reconstructing those rectangles.
All 3,027 masks across the nine source maps pass. Only 363 have obstacle links;
these are altitude-test references, not sufficient evidence of visual ownership.
The rectangles are intermediate authoring data, not asset geometry: ownership,
intersection with actual asset surfaces, local 3D coordinates, masking boundaries
and state bindings still need recovery before publication.

Surface lifting now clips this intermediate coverage against explicitly supplied
owner mesh triangles, splits overlaps where their depth order changes, and
stores only the frontmost surface in asset-local coordinates. It rejects coverage
outside the mesh instead of extrapolating height. Tests cover sloped faces,
cutouts, crossing surfaces, duplicate faces and foreground islands. This helper
is used by explicit reviewed recipes in the batch asset migration; these
synthetic tests alone do not certify existing-map mask recovery.
The mesh reader handles indexed/unindexed triangles and nested transforms in a
selected model part. Skinned/animated geometry and transparent materials reject
until their state or texture coverage is explicitly handled. Surface clipping
uses fixed-point polygon operations; recovery then rerasterizes with the map
compiler and requires exact source pixel coverage, allowing partially covered
edge cells only when their pixel samples match. Four Derby probes (mask records
15, 27, 67 and 93) still fail coverage against their obstacle-linked candidate
assets' published meshes. They are not recovered or published as gameplay masks.
Those four candidates lack 175, 323, 72 and 332 covered pixels respectively;
the gaps include interior pixels, so accepting boundary rounding alone is
insufficient. Reviewed cottage associations also require geometry work.

Asset character/projectile boundaries can now be explicitly open, independently
of one another; existing authored boundaries remain closed by default. This
preserves source polylines without inventing a closing edge across a concavity.
Monotone open lines retain vertical endpoint steps; other placements recompute
their front envelope. The bitmap audit also verifies all 5,166 nonempty source
polylines across the nine maps are reproduced point-for-point. This verifies the
boundary representation only, not their receiving elevation or asset ownership.

`recover-occlusion-mask.ts` combines verified coverage with explicitly supplied
boundary heights, a receiving anchor and local obstacle ownership. It emits an
asset-local definition without source layer/obstacle indices or bitmap data.
Character heights lift projected points; projectile heights preserve world XY.
Tests recompile every supported flag combination unchanged and verify movement,
elevation and independent authoring data. Missing height/ownership evidence is
rejected. The batch migration still needs reviewed inputs for existing masks;
this authoring function does not certify their recovery or state links.

Patch mask references now use the correct `{layer, index}` schema, with indices
local to each layer. Parsing rejects dangling/flat references. State-link recovery
resolves these into recovered asset-local IDs, refusing missing owners, duplicate
state IDs or implicit cross-asset coordination. Tests cover interleaved source
layers and independent links after asset duplication. All 518 state references
across the nine source maps resolve; none reuses a mask within/across patches.
This does not mean those masks have recovered coverage or published state links.

`pipeline/src/verify-reviewed-mask-recovery.ts` reproduces the reviewed-mask
checks from a scene, pinned library, recovery packets and source-pinned recipes.
It compares exact covered pixels, flags, both optional polylines and obstacle-link
counts, rejecting ambiguous matches rather than choosing one. A source mask
may compile into multiple bitmap tiles. Their coverage must form
an exact disjoint union with consistent layer and obstacle links, and every
compiled mask must be accounted for by a reviewed recipe. Each owning asset
then moves independently; bitmap bytes, dimensions, translated boundaries and
compiled obstacle links must remain exact. A failed run invalidates the previous
manifest, records placement errors and exits unsuccessfully. These are static
diagnostics, not ownership, receiving-layer, visual or full-gameplay certificates.
For example, from `level-editor`:

```sh
node --max-old-space-size=1536 pipeline/src/verify-reviewed-mask-recovery.ts \
  --library work/map-compile/projection-material-library \
  --map work/map-compile/projection-material-library/scenes/derby.rhlos-map.json \
  --source library/game-data/Data/Levels/Derby.rhp.json \
  --recovery work/map-compile/derby-hall-mask-recovery \
  --mask-definitions refinement/catalogs/derby-masks.json \
  --out work/map-compile/reviewed-mask-verification/derby
```

The current six-map batch verifies all 64 reviewed masks and 45 independent asset
moves. All 51 baseline/moved descriptors load natively. Adding the latest masks
leaves baseline non-mask geometry unchanged. Outputs are under
`work/map-compile/reviewed-mask-verification/<map>`. This broader check caught a
fractional-anchor regression on Derby's postern: mask receiver elevation now uses
the authored floating-point position, while polygon membership uses the movement
grid. A sloped fractional-anchor regression test protects this distinction.
The earlier tile-aware verifier rerun is under `work/map-compile/tile-mask-verification`;
all 61 then-reviewed source records pass and all 48 native-tested descriptors are unchanged.
The current batch also uses that verifier, including three additional Lincoln masks.
Horizontal/vertical multi-tile tests reject missing pixels, overlaps and mixed
bindings. All ten oversized source bitmaps also pass a format-only split/reassembly
check (`work/map-compile/oversized-mask-roundtrip.json`): Derby 129/168/172/173,
Leicester 24, Lincoln 268 and Nottingham 126/127/449/504. This does not recover
their asset ownership, geometry, receiving surfaces or state bindings.

Croisement01 has one reviewed static mask in
`refinement/catalogs/croisement01-masks.json`: record 25 (6,258 pixels), owned
by `croisement01-group-007`. Its projectile boundary follows scenery part 074;
character threshold heights follow the owning assembly's sloped part 007.
The receiving anchor is on adjacent navigable terrain. Coverage and both open
boundaries match exactly, including after moving the assembly one pixel east.
Both scenes load natively, and baseline non-mask geometry matches the jump-anchor
diagnostic. Drafts and native checks are under `work/map-compile/croisement01-mask-recovery`
and `work/map-compile/croisement01-mask-native`. There are 102 unrecovered masks;
complete asset coverage, mask-controlled depth and publication remain unfinished.

Seven real static masks are recovered for Derby: southwest postern records
70 and 71, with 385 and 884 covered pixels, and upper gatehouse record 105,
with 4,124 covered pixels, plus lower east/west curtain records 39/44 with
5,753/8,112 covered pixels. The curtain masks have no obstacle links; their
inner-parapet coverage is fully supported by the respective wall meshes and
their receivers use each wall's own flat 150.001-unit navigation surface.
East hall records 153/154 add 4,394/4,604 pixels of projectile-only roof-end
coverage. Their boundaries follow the hall's roof geometry, with receiving
anchors inside adjacent reconstructed ground; neither has obstacle links.
Other fully supported unlinked candidates still require ownership review;
several keep masks have support from multiple overlapping assets.
Record 105 is not referenced by any patch; the
gatehouse's separate changing masks still require state recovery. The reviewed recipe is
`refinement/catalogs/derby-masks.json`; pass it to `recover-asset-gameplay.ts` with
`--mask-definitions`. Source and model hashes pin the authoring evidence. The
migration checks source receiving layers/elevations, local obstacle ownership and
exact mesh-backed coverage, and rejects changing masks until their state recovery
is supplied. All seven definitions compile from asset data only and preserve pixel
coverage and character/projectile boundaries when their owning asset moves one pixel east.
Native construction verifies their bitmap coverage and layer registration. The
baseline and all five independently moved scenes load natively. Baseline non-mask
geometry is unchanged. Updated drafts are under
`work/map-compile/derby-hall-mask-recovery`, with native descriptors under
`work/map-compile/derby-hall-mask-native`. Derby still has 229
unrecovered masks; neither the complete asset nor map is publication-certified.

Leicester has sixteen reviewed static masks in
`refinement/catalogs/leicester-masks.json`. Projectile-only records 288 (church
side tower, 20,011 pixels) and 415 (great keep, 4,552 pixels) are joined by five
character/projectile/view masks: northeast gabled house 120 (4,433 pixels), south
stilt shed 182 (1,184 pixels), and great keep 399/402/404 (2,570/2,590/3,323 pixels).
The keep's character boundaries receive on its flat 140.001-unit surface; the
shed's boundary heights follow its own sloped surface. The house uses ground.
Nine additional unlinked masks belong to the village houses: northeast gabled
house 122/123/124 (621/265/897 pixels), northeast longhouse 132/133 (539/271),
north village cottage 141/155 (4,167/476), mill north cottage 154 (432), and mill
south cottage 166 (2,135). These receive on ground. Records 123 and 132 are
view-only and correctly export without character or projectile boundaries.
All sixteen preserve exact coverage, flags, open boundaries and local obstacle
links after each asset moves one pixel east. Native loading passes for the
baseline and all eight independently moved scenes; baseline non-mask data matches
the same-library jump-anchor diagnostic. Moving the tower detaches one jump pair
and its gate. Updated drafts are under `work/map-compile/leicester-village-mask-recovery`,
with native diagnostics in `work/map-compile/leicester-village-mask-native`.
Leicester still has 450 unrecovered
masks; these assets do not have complete mask coverage or mask-controlled depth enabled.

A broader unlinked static-mask support audit is recorded in
`work/map-compile/<map>-unlinked-mask-candidates.json`. It found 13 supported
records on Croisement01, none on Croisement02/03, 9 on Derby, 75 on Leicester,
157 on Lincoln, 44 on Nottingham, 1 on Sherwood and 140 on York. These are
candidate counts, including overlapping terrain/building support and already
recovered records; they do not establish ownership or parity. The audit excludes
patch-controlled masks and name-filtered terrain/ground/region assets. It also
records unsupported transparent meshes and missing or non-rendering frames
(6/6/4 errors on the crossings, 5 on Leicester and 16 on Sherwood). Those cases
remain unassessed, rather than being counted as evidence of absent coverage.

Nottingham's reviewed recipe (`refinement/catalogs/nottingham-masks.json`)
recovers sixteen static masks: west green shop 52/55 (2,523/1,862 pixels), upper red
house 103 (4,428 pixels), and village small hut 210 (6,932 pixels), plus eleven
unlinked records: east boarded house 21/22 (12,351/917), northeast timber house
94 (562), north dormer house 79 (1,042), south gate house 47 (32,663), southwest
wall house 75 (1,269), upper green house 109 (1,189), upper west lean-to 112
(1,494), village east cottage 138 (683), small hut 211 (5,852), and village mill
155 (4,112). These receivers are ground-level. North stone house 78 adds 948
pixels receiving on its own flat 66.957-unit landing. All coverage and boundary rules
match exactly and follow independent one-pixel asset moves. Native loading passes
for the baseline and thirteen moved scenes. Non-mask geometry matches the current
jump-anchor diagnostic; sound sources match the previous same-library mask
baseline. Four jump-zone receiving references differ from that older baseline
because of the already verified owner-anchor fix, with polygons and helper rules
unchanged. Some moved jump connections detach. Updated drafts and native checks
are under `work/map-compile/nottingham-landing-mask-recovery` and
`work/map-compile/nottingham-landing-mask-native`. There are 511 unrecovered
Nottingham masks; complete asset coverage and mask-controlled depth remain pending.

Moving the north stone house 32 pixels west also preserves its mask exactly and
loads natively (`work/map-compile/nottingham-landing-west-native`). A 32-pixel
east move exposed a neighboring mask receiver covered by movement collision.
Mask compilation now retains a uniquely identified authored receiving layer
under such exclusions, while requiring actual asset surface support and retaining
strict walkability checks for doors/jumps. The compiler change leaves the complete
baseline unchanged. The east move gets past the mask check but still fails because
the moved house's door is outside walkable ground; that placement is not certified.

Lincoln's reviewed recipe (`refinement/catalogs/lincoln-masks.json`) recovers four
masks: keep 390 (16,407 pixels), lower east curtain 192 (4,910), west south curtain
203 (4,652) and northeast square tower 207 (11,503). Their character thresholds use
the owning asset's flat receiving plane: 800.00104, 350.001, 350.001 and 415.001
units respectively, including where thresholds extend beyond navigation. Anchors
are inside both the owning recovered surface and the source receiving layer;
the split east curtain uses its own surface component. Bitmap coverage remains
entirely mesh-supported. Coverage, boundaries and obstacle links match exactly
before and after moving each owner independently one pixel east. All five scenes
load natively, and baseline non-mask geometry is unchanged. Current drafts and
native checks are under `work/map-compile/lincoln-curtain-mask-recovery` and
`work/map-compile/reviewed-mask-verification/lincoln`.
There are 424 unrecovered Lincoln masks.

Annex view-only mask 398 matches all 7,593 pixels at baseline, but remains outside
the reviewed recipe: moving its owner one pixel east makes the annex stair's lower
endpoint disagree with the neighboring slope's height by approximately 0.121 units.
The receiving slope belongs to another asset. Endpoint validation correctly
rejects the traversal connection after this placement.
The failed placement diagnostic is retained under
`work/map-compile/lincoln-raised-mask-native` with `complete: false`.

York's reviewed recipe (`refinement/catalogs/york-masks.json`) recovers twenty static
masks: scaffolded corner house 79/86 (2,777/747 pixels), southwest square corner house
201 (392), central south golden timber house 227/238 (2,126/5,856), southeast lane
eastern timber house 269 (687), south gate lane front timber house 280 (1,036),
and outer east wall stair passage 164 (7,305), plus twelve town-house records:
southwest square rear house 202/215 (421/2,097), west house 204/218 (298/515),
narrow gable house 205/207 (8,244/1,752), east timber house 213 (355), southwest
lane west jettied house 295 (685), north courtyard house 297 (820), market southwest
east timber house 325 (310), and southwest market northwest house 353/354
(2,239/1,078). Record 204 preserves its character/view rules without inventing a
projectile boundary. Mask 269 receives at ground level;
164 uses its owning passage's flat 160.001-unit plane, including the character
threshold beyond navigation. Mask 86 has no character threshold and receives on
the owning house's flat 152.001-unit platform. The remaining receivers use the
flat 90.00101-unit town surface. All twenty match in the baseline and after independent one-pixel
asset moves. Native loading passes for the baseline and all fourteen moved scenes.
Adding the town-house masks leaves baseline non-mask geometry unchanged. Updated drafts and
native checks are under `work/map-compile/york-town-mask-recovery` and
`work/map-compile/york-town-mask-native`. York still has 808 unrecovered masks.
These assets have incomplete mask coverage and do not enable mask-controlled
depth. None of these maps is certified for complete gameplay or publication.

The scaffolded-house movement check exposed a landing anchor selected from a
neighboring asset's portion of a shared jump zone. Recovery now intersects the
unblocked landing region with the owning asset's receiving footprints before
choosing an anchor. It selects a point on the integer movement grid before
evaluating elevation, avoiding fractional-point/rounded-point slope mismatches.
Zone polygons, jump edges and helper rules are preserved. York's baseline now
uses a corrected receiving-sector reference for one zone; all other compiled
fields remain unchanged. Moving the scaffolded house detaches two jump pairs
and their gates without invalidating its neighbor's remaining landing anchor.
All nine maps retain all 173 recovered pairs, pass static compilation, and load
natively in the jump-anchor regression batch. Updated York recovery is under
`work/map-compile/jump-anchor-recovery/york`, with baseline/moved native checks
under `work/map-compile/york-jump-anchor-native`. Traversal fidelity and complete
map publication remain separate requirements.

Recovery discards faces outside a mask's bounds before fitting their depth
planes. This avoids numerical failures from unrelated nearly edge-on faces
without relaxing planarity or coverage checks for contributing surfaces.

`pipeline/src/audit-mask-surfaces.ts` checks pixel support for an explicitly
selected asset and mask indices. It pins source/model/scene hashes, reports missing
pixel counts and repair bounds, and checks whether every mask in each affected
state set was selected and supported. This is geometry evidence only, not ownership
or gameplay certification. Recovery now checks this support before expensive
surface clipping and reports interior gaps separately from silhouette edges.

The Derby upper gatehouse state set (patch 3, records 217–229) is not recoverable
from its current mesh: 217/218/219/221/223/224/225/226 lack respectively
362/960/219/565/121/70/65/206 covered pixels. Every failing record includes interior
gaps. Records 220/222/227/228/229 have full pixel support, but this does not justify
publishing a partial state set. Repair the asset geometry or add reviewed local
occlusion surfaces before recovering that state. The reproducible audit is:

```sh
node pipeline/src/audit-mask-surfaces.ts \
  --library work/map-compile/projection-material-library \
  --map work/map-compile/projection-material-library/scenes/derby.rhlos-map.json \
  --source library/game-data/Data/Levels/Derby.rhp.json \
  --asset derby-upper-gatehouse \
  --masks 217,218,219,220,221,222,223,224,225,226,227,228,229 \
  --out work/map-compile/gatehouse-mask-state-audit.json
```

A separate probe adding the same asset's existing obstacle-volume faces closes
record 225's pixel gap, but seven other records still have missing interior
coverage. Those volumes therefore cannot complete the state set either; no
supplemental surfaces or partial state bindings have been published.

Material recovery stores ground regions on terrain, obstacle regions on their
owning parts, and receiving defaults/region references on asset-local surfaces.
Receiving footprints retain material across blocked portions omitted from walking
contours. Material boundaries split projection faces without splitting navigation;
bounding-height priority and authored tie precedence resolve overlapping receivers.
An empty ground-material list correctly activates no ground regions; obstacle-only
regions do not become ground water or footstep materials. Native tests verify
raised material overrides and defaults, independent ground lookup and traversal
across material boundaries. Rotated/duplicated asset tests rebuild local references.
All nine recovered drafts compile and construct native geometry with these definitions;
all 397 non-lift doors, room memberships and door-linked bindings still match.
A 16-pixel sampling probe found matching material codes at 34,120 points shared
by source and compiled receiving surfaces, plus 88 compiled samples with no matching
source receiver. This is a sampled material check, not complete geometry or gameplay
parity. Definitions remain unpublished and receiving-geometry gaps remain open.

Terrain drafts also carry forest behaviour and fallback material. Recovery
normalizes clearance crossings introduced by integer rounding, preserving valid
regions instead of discarding a polygon whose signed area cancels. Nottingham's
hidden prison part retains its gameplay frame and passes the static check.

Sound recovery attaches global emitters to terrain and local emitters only when
their complete geometry has one containing asset. Overlapping parts within that
asset use a stable local frame; containment spanning different assets remains
ambiguous. Ambiguous/unowned sources
remain explicit gaps; they are not silently attached to terrain. Shared audio
samples are referenced from the base installation, rather than bundled in the ZIP.

Leicester's west moat tower owns source records 12/13 and its southeast cottage
owns record 15 despite overlapping part footprints. All three compile exactly;
moving either asset independently by one pixel preserves the corresponding
emitter displacement and all acoustic parameters. Native construction passes for
the baseline and both moved scenes (85 areas, 503 sight obstacles, 105 doors,
23 jump pairs). Baseline non-sound geometry is unchanged. This staged recovery
accounts for 10 of 24 Leicester sound sources; 14 remain unresolved.

Reviewed environmental lines can also be authored as independent sound-region
assets with a non-rendering gameplay frame. This is an explicit asset-authoring
step, not an automatic fallback for unowned emitters. Derby's west and north edge
emitters (source records 4/5) are authored this way by
`refinement/catalogs/derby-ambient-sounds.json`. The authoring command checks the
source hash and writes standalone descriptors, empty frame models, identical
runtime derivatives with hash receipts, and pinned placement references;
compilation reads only those assets. Catalog publication preserves the
non-rendering gameplay-frame marker and acoustic definitions.

```sh
node pipeline/src/author-ambient-sound-assets.ts \
  --source library/game-data/Data/Levels/Derby.rhp.json \
  --recipe refinement/catalogs/derby-ambient-sounds.json \
  --map Derby --out work/map-compile/ambient-authoring-library
```

The staged scene `ambient-authoring-library/derby-ambient.rhlos-map.json` reopens
with the two new assets. Both sound definitions compile exactly, including
polylines, delays, attenuation, altitude and ambience. Moving the west zone 50
pixels east changes only its emitter geometry. Native construction checks sample
selection, preserved source handles, polylines and delay parameters before/after
the move. This composed Derby diagnostic accounts for 5 of 12 sound sources;
seven remain unresolved. Assets and the composed diagnostic remain staged, not
published as a complete map. Recovery recognizes the placed sound-region assets,
matches their compiled definitions to exactly one unclaimed source each, and
preserves their asset-local definitions. Duplicate or mismatched sources fail
instead of being counted twice. The integrated Derby report contains 43 assets
and seven pending sound sources.

Additional source-pinned ambient recipes cover Croisement03's north edge,
Leicester's northwest edge, and Nottingham's north and northwest edges:
`croisement03-ambient-sounds.json`, `leicester-ambient-sounds.json`, and
`nottingham-ambient-sounds.json` under `refinement/catalogs/`. These four
air-altitude environmental lines have standalone local frames. Their authored
scenes reopen with pinned descriptors and retain the input scenes' state metadata.
Static diagnostic exports preserve every source field and pass native loading
before and after moving each region independently by 50 pixels. Non-sound
compiled geometry stays identical for each move. All four asset definitions and
runtime derivatives also pass offline publication staging.

The staged boundary-sound recovery accounts for 1/6 Croisement03, 11/24 Leicester,
and 6/24 Nottingham emitters. Five, thirteen and eighteen respectively remain
unresolved. These checks do not establish complete map parity or publication:
changing geometry, masks, lighting and remaining emitter ownership still have
separate outstanding requirements.

Light recovery preserves projection priority and fits receiving planes from the
leading three vertices. Elevated light contours may extend outside navigation
when their intersecting receivers agree on one plane, including raised terrain
on layer zero. A non-walkable receiving-footprint notch does not establish a
ground plane; uncovered potentially walkable portions still require a valid
plane, including areas opened by state changes. Ownership can span several parts
of one asset, but their combined footprints must cover the entire light polygon,
including its interior; enclosed gaps and competing asset owners remain errors.
The previous all-map pass recovered 35 of 149 light/shadow regions into asset-local
drafts, including six additional regions on Leicester's keep, west wing and moat
towers. All 35 exported contours and ambience masks match source records, and
the previously recovered regions remain covered. Light regions
also resolve onto stair/lift traversal surfaces; a native test verifies ambience
filtering on the traversal layer without affecting the ground layer or door links.
All nine static diagnostics constructed successfully. The other 114 regions then needed
receiving-geometry fixes, ownership review or multi-plane authoring; they are not
silently assigned to terrain. These drafts remain unpublished.

Splitting multi-plane contours introduced rounding errors in all eleven current
candidates, including loadable York 12/14 descriptors. Recovery now preserves the
complete integer contour and records asset-local receiving anchors independently
of its reference plane. Compilation copies that contour to each resolved layer,
deduplicating repeated anchors on the same layer. Surface partitions establish
ownership and locate anchors; their fractional cut vertices are not exported.
The strict piecewise recovery helper still rejects contour changes after rounding.

York regions 12/14 now recover to the west-town terrain asset with exact original
contours on layers 30/68 and 30/92 respectively. This raises the recovery evidence
to 37/149 regions; 112 remain pending. The native diagnostic checks contour
registration and activation for ambience masks 1, 2 and 4. Updated Leicester,
Lincoln and York drafts are in `work/map-compile/receiver-light-recovery`, with
descriptors in `work/map-compile/receiver-light-native`. Independent receiver
movement and duplicate-layer handling pass compiler tests. Moving the large York
terrain asset alone by one pixel merges a bridge passage's two areas. Unrestricted,
non-clickable passages can now carry `allowContinuous` in their asset definition:
they remain ordinary doors while their areas are distinct and are omitted with a
diagnostic when both endpoints share one area. Recovery sets this flag only when
both sets of access rules are unrestricted and no patch refers to the door.
Interactive, restricted and state-controlled doors cannot be omitted this way;
remaining door/state indices are rebuilt after omission. York's original-placement
output remains identical, including all door references.

The independent terrain move now passes that bridge check but fails another
passage's receiving-height check: its outside endpoint is at height 46.2952 while
the receiving slope at the moved position is 47.8476. This is retained as an error;
independent full-scene terrain movement is still not verified.
Translating the entire York scene one pixel east preserves both regions' exact
contours and ambience on both receiving layers; that check preserves existing
connections and does not replace the independent terrain-movement check.

Jump recovery produces asset-local drafts for all 173 pairs across nine maps.
`compare-jump-geometry.ts` verifies exact endpoint coordinates, polygon boundaries,
helper flags and long-jump flags against the reference records, allowing rebuilt
indices, reversed polygon winding and reordered pairs. All 173 pass. Native checks
also verify paired lines, endpoint elevations and registration on landing sectors.
These checks do not establish traversal connectivity or full gameplay parity.
Edge elevations remain independent of fractional
surface heights. Extraction now preserves the third endpoint coordinate and
remaps zone references, retaining both destinations when a crop crosses a pair.
The passing static diagnostics also include their recovered jump definitions.
Croisement03's door topology now survives recovery: asset-local navigation-region
labels preserve separate coplanar areas, including when their boundaries touch.
Labels are scoped to each placement; unlabelled surfaces retain normal merging.
One local region can now span multiple height planes while compiling to one
ordinary movement area. Each projection plane retains its height, and a native
engine fixture verifies walking across the shared boundary without a gate or lift.
Recovery preserves this relationship when all supports have one unambiguous asset
owner. Ordinary regions spanning different assets still need explicit join authoring.
Ground recovery reports per-region differences as well as overall coverage.
When two pieces have one shared straight cut and lie on opposite sides, recovery
uses that cut to divide the navigation surface without trimming its outer boundary
to the mesh. This preserves Nottingham's stair landing. Missing or ambiguous cuts
keep their unresolved footprint gaps; no nearest-owner assignment fills them.
Hidden mesh parts retain coordinate frames for explicit gameplay; whole hidden
placements remain excluded. Hidden sight geometry is included only when explicitly
referenced by a transition. Nottingham now passes the prison-frame and castle-door
checks and its elevated stair landing. York's compound lift now has
asset-local segment connections, and its staged canonical tower restores the
interior-door landing surface. Lift recovery matches shared
edges once and stores local sockets, never runtime references between assets.

Stable terrain is recovered even when its movement area has changing obstacles.
The recovery inventory preserves all 27 changing-obstacle groups, their initial
and applied contours, and patch associations. Twenty-one now recover into asset-local
movement/sight transitions: five in Croisement01, eight in Croisement02, seven in
Croisement03 and one in Nottingham. Seven belong to physical assets;
fourteen navigation-only boundaries have newly staged assets and editor placements.
These non-rendering assets carry their own local contours and support independent
movement and duplication. They add no mission actors or scripts. Their models,
descriptor hashes and editor index entries are staged but not yet published.
Each transition has one unambiguous asset owner and explicit stable movement
contours or a local list of permanent collision solids. The latter keeps a mixed
asset's unchanged parts and their clearances without deriving permanent collision
from the changing endpoints. Croisement03's compound obstacle uses three permanent
parts and one changing part. Two additional pitched-cover assets combine paired
sloped volumes that share one ridge and cover mask; both pass real-browser
loading, insertion, save/reopen and rendering checks. Their visual/mask state
export remains pending.
Changing contours are split across receiving planes while preserving holes and
projection priority. Output stores local geometry and references, with fresh
movement bindings allocated during compilation. The other six still need explicit
ownership or elevated receiving geometry. One remaining
navigation-only contour extends beyond its elevated receiving surface and is
rejected rather than assigned an inferred height. `movementTransitionRecovery` records
the recovered groups, and each unresolved group has a specific failure reason.
Visual states and effects remain separate pending work.
Door links use local endpoint IDs; compilation allocates fresh non-lift door indices
for each placement, including duplicates. Native fixture tests verify both link
directions, permission changes and restoration on reset. Door-only transitions
are supported without adding navigation or sight changes. Offline recovery maps
source door indices into local endpoint IDs and reports missing owners, cross-asset
links and unrecovered geometry in `pending.doorTransitionBindings`. All 28
door-linked patches across the nine extracted maps now recover: seven in
Nottingham, nine in Lincoln, five in York, five in Leicester, one in Croisement03 and one in Derby.
Explicit `door_sources` authoring declarations cover gate passages whose empty
openings lie beyond nearby wall geometry. They require unique source door indices,
a rationale and one pinned asset frame, and reject conflicting state ownership.
The compiler receives only local endpoints. Derby's two gatehouse declarations
restore its remaining five doors: all 42 non-lift doors and the three-door permission
transition now match source geometry and rules. `declaredDoorOwnershipRecovery`
records the one-time mapping.
Nottingham declarations restore four rooms and five doors in the two green market
frontages, north dormer house and castle main hall. Further declarations attach
parallel passage lanes to the north gate gallery, stream wall and south gate arch.
The castle hall and watchtower form one 35-part asset, keeping their shared
three-door interior together when moved. Nottingham now matches all 100 non-lift
doors, 45 interiors and seven door-linked patches in the geometry/rules comparison.
The staged combined asset passes editor insertion, rendering and save/reopen checks.
Static merging preserves component annotations, translates declared bounds and
namespaces appearance bindings without changing their resolved behavior. Its GLB
writer retains near-identity transforms so binary round trips meet the existing
world-transform tolerance. These assets and gameplay definitions remain staged.
Sherwood's two camp-hut declarations bind entrances to their wall frames within
the current grouped hut assets, including their roofs. Two treehouse declarations
keep the central-west and west rooms with their huts rather than the overlapping
oak/platform assets. All five non-lift doors and five shared interiors now
match the reference geometry/rules. Missing ladder ownership and other navigation
gaps remain separate from this door comparison.
Lincoln declarations attach the hall-terrace gate and western-tower passage to
their corresponding revealed assets, the shed entrance to its room, and all three
keep-floor entrances to one shared keep interior. These restore six doors and two
permission transitions without assigning rooms to supporting terrain. Two further
passage endpoints lie on physical supports outside their assigned receiving areas.
Explicit extraction declarations identify the containing support and an anchor in
the linked area. Recovery checks both, then retains only local heights/coordinates.
The sloped wall-walk step owns one passage; the annex owns the other gate and its
transition. Lincoln now matches all 59 non-lift doors, 19 interiors and nine
door-linked patches in the geometry/rules comparison.
Assets now support optional `outsideAnchor`/`insideAnchor` door coordinates for
selecting receiving areas independently of the visible/traversal endpoints.
These local anchors move, rotate and duplicate with the asset; no sector indices
are retained. They must resolve to one unblocked surface, and an interior's inside
anchor cannot override its shared virtual room. A compiler-generated fixture loads
in the native engine with both endpoint coordinates outside their linked polygons
while retaining the intended gate registrations. Recovery packet conversion
preserves the anchors. Transitions similarly support a local `waypointAnchor`, so
Lincoln's annex transition retains its reference point while linking the intended
landing. This does not certify full navigation connectivity across receiving areas.
Leicester's three drawbridges have shared multi-scene GLBs. Their initial/applied
views now share one gameplay definition per placement. Compilation unions local
state parts, deduplicates shared frames and supplies hidden frames for alternate
states when only the initial view was inserted. It preserves world transforms when
the group's pivot changes, including rotated and elevated placements, without
changing the saved editor scene. Conflicting shared frames and ambiguous separately
edited parts fail explicitly. All 59 non-lift doors, 16 shared interiors and five
door-linked patches now match Leicester's reference geometry and rules. Visual-state
and typed-mask export remain unfinished; these are geometry diagnostics.
Linked changing geometry can establish a door owner only when every obstacle has
one owner and all belong to the same asset. `doorStateOwnershipRecovery` records
this evidence for physical-grouping review; conflicting or missing geometry cannot
select an owner. Recovery also supports sight changes without navigation
changes when every referenced obstacle and door belongs to the same asset.
The 60 recovered initial/applied sight references match source coordinates at native float32 precision
and preserve their flags. All eight initial/alternate permission fields match the source for the 66
linked door references, and each binding retains its trigger direction.
Ordinary passages can connect to stair/lift surfaces in either direction without
becoming lift doors. This restores Lincoln's hall passages onto traversal surfaces.
All nine extracted map diagnostics compile and load; the native round-trip harness
applies/resets their 48 recovered transitions. It checks both
halves of door permissions as well as movement and sight state, including the
door-to-patch links for door-triggered transitions.
Door-linked patch coverage is complete in these diagnostics; visual effects,
navigation fidelity and publication remain unfinished.
Spatial ownership ties can be resolved by slicing solid geometry above the landing,
excluding supporting terrain and preserving disconnected concave pieces. This
restores 84 connection records without dropping previously recovered doors.
Across the nine diagnostics, all 397 non-lift doors now compile and match
source endpoints, click polygons, door types, active flags and initial/alternate
permissions. York's final four entrances belong to two shared interiors spanning
independent buildings. Authored passage sockets restore those rooms while keeping
each entrance with its own building. Inferred physical grouping remains marked for
review before publication; complete door coverage does not certify full gameplay parity.
`compare-door-geometry.ts SOURCE_JSON COMPILED_LEVEL_JSON` independently compares
non-lift door geometry/rules, shared-room membership and door-linked patch rules.
It accepts regenerated indices and equivalent polygon winding, but fails on missing
or extra records, regrouped rooms, changed permissions or mismatched trigger direction.
It does not certify receiving-area connectivity, lift behavior, sight changes or visuals.
Current compiled/source counts (no unexpected records in any map):

| Map | Non-lift doors | Shared rooms | Door-linked patches |
| --- | ---: | ---: | ---: |
| Croisement01 | 3/3 | 0/0 | 0/0 |
| Croisement02 | 1/1 | 1/1 | 0/0 |
| Croisement03 | 5/5 | 0/0 | 1/1 |
| Derby | 42/42 | 14/14 | 1/1 |
| Leicester | 59/59 | 16/16 | 5/5 |
| Lincoln | 59/59 | 19/19 | 9/9 |
| Nottingham | 100/100 | 45/45 | 7/7 |
| Sherwood | 5/5 | 5/5 | 0/0 |
| York | 123/123 | 74/74 | 5/5 |

York's counts use the current library building groupings. Explicit entrance
ownership distinguishes raised terrain from buildings, the bridge gatehouse from
its adjoining tower, and overlapping market-house projections. These declarations
recover ten entrances that were unresolved in the newly grouped scene. Its 72 jump
pairs and five door-linked patches still match, and native geometry construction
and transition apply/reset pass. Two additional shared-room declarations connect
the paired castle lodges through their curtain-wall passage and the market corner
shop with its adjoining gabled house. Recovery requires every source entrance to
have exactly one owner, validates pinned frames and connected sockets, and checks
that each socket touches its owner's wall geometry. These become local positions
and directions in the assets; source building and door indices remain offline.
Optional interior sockets retain a local 3D point and a facing direction. Opposing
sockets within the placement tolerance join rooms; unmatched sockets leave rooms
independent and ambiguous matches fail. Doorless connector assets participate in
joins but create no runtime room without an entrance. Compiler/export fixtures
and native engine tests cover joined and separated room registrations; rotated
and duplicated assemblies retain independent connections and door-transition links.
The recovery packet format preserves these definitions without global identifiers.
The original York arrangement passes native construction with all 123 doors,
74 rooms and 72 jump pairs. A one-pixel courtyard-wall move now compiles and loads
as a static diagnostic with 75 rooms: the two lodges become independent, keeping
their entrances. The wall-to-house jump becomes unavailable, leaving 71 jump pairs.
Unmatched jump sockets emit warnings; unused landing zones are omitted and remaining
zone references are rebuilt. Restoring the asset placement reconnects the jump.
Ambiguous matches and conflicting jump rules still fail. A ten-pixel move also
intersects a neighboring stairway and fails the existing traversal-connectivity
check; this verification does not establish arbitrary-placement or full visual parity.

The twenty-one recovered movement-changing transitions pass native initialization, apply and reset checks:
movement-state bits, obstacle-sector activation and sight flags change and restore.
Transition reference points may lie inside static blockers; they must still resolve
to a unique surface at the authored height. Doors resolve their optional receiving
anchors, or otherwise their endpoints, against unblocked surfaces. Jump landing
anchors likewise require an unblocked receiving position.
The ignored `recovered_asset_transitions_apply_and_reset_native_geometry` test uses
`ROBIN_ASSET_MAP_DIAGNOSTICS` to load the generated transition-bearing probes.
Diagnostic batches fail if any map fails or no maps are exported. Each run invalidates
the previous manifest and removes each map's stale output before attempting recovery;
native checks reject failed entries instead of silently skipping them. A successful
batch still proves only the explicitly checked static geometry and state behavior.
Croisement03's remaining elevated navigation-only change has approximately 24.49
square pixels inside its movement area but outside every receiving surface. This
requires explicit asset authoring; recovery must not silently invent a receiving height.
`omittedMovementTransitions` makes missing transition definitions explicit
in the static diagnostic and prevents it from certifying full compilation.
Ground recovery uses fixed-point polygon operations and reports reconstruction
area differences; generated boundaries are normalized after integer rounding.
Solid/surface intersections use fixed-point clipping. Redundant straight-edge
vertices are removed before rounding to avoid artificial navigation seams.
Recovered clearances retain the free-space boundary and extend only around their
owner's bounds; they can subtract that owner's collision, never another asset's.

Non-rendering gameplay volumes can attach to an existing asset frame without a
mesh. One-time recovery uses explicit catalog ownership (or `--ownership`) and
restores six of York's nine inventoried records against the published scene,
including a missing jump landing surface. Staged canonical tower, golden timber
house and stone-shop assets resolve the remaining three records; all nine now
have asset owners. The stone shop uses an explicit split that preserves its
neighboring building parts in a separate asset with unchanged geometry.
The updated ownership catalog additionally requires complete green timber-house
and striped-awning building assets; staging both restores their two local volumes
without assigning either volume to a partial building. The combined York draft
now constructs 194 movement areas, 1,161 sight obstacles, 244 doors and 72 jump
pairs, whose geometry and traversal flags match the source pairs.
The compiler reads
only the resulting local volumes; source sector and material indices are rejected.
`stage-canonical-static-asset.ts` combines complete static assets only when their
parts exactly match an explicit catalog group. It checks unchanged world collision
positions and decoded model geometry, materials and texture bytes after writing
the merged model. Partial groups require `--split`, which partitions leaf parts
without changing their world transforms, collision coordinates or appearance.
Merged and split models normalize their hierarchy to one Z-up map wrapper and
one identity asset group; the part transforms retain the placed geometry.
The staged index includes each new descriptor and model hash, and other map scenes
remain available in the overlay. The five York canonical assets and the split
remainder pass real-browser loading, insertion, save/reopen and rendering checks.
Every part must be assigned exactly once. Edited placements and state/gameplay
definitions requiring migration are rejected. Its output is a separate library overlay and
pinned editor scene, not a publication or a runtime dependency on source levels.
Jump recovery now requires an owned receiving surface on each elevated side;
missing or ambiguous ownership remains an explicit gap rather than an invalid pair.
Cross-asset edges retain only their own local landing zone and a shared geometric
socket. Compilation rejects missing or ambiguous mates and conflicting long-jump
rules; no source pair index or fixed scene reference links the assets.
Terrain owns ground jumps only between recovered terrain landing regions and
across retained terrain exclusions; any transferred asset-owned exclusion in the
jump corridor prevents that assignment. Split-asset ownership uses each actual
part footprint, allowing an edge to span multiple planes of one asset while
rejecting gaps between them. York's staged stone-shop roof resolves the final two
pairs. Recovery coverage is not a connectivity parity proof.
