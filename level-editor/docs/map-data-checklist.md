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
unless explicitly replaced by authored movement contours. Preview-only part bounds
do not create navigation or collision; those parts require separately authored
gameplay. Standalone
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
outside the reviewed catalog. This exposed the need to preserve authored receiving
planes independently of subdivision and to verify receiving priority and traversal.

Receiving materials now support ordered asset-local `planePoints`. One-time
recovery copies the three plane-defining anchors into each owned surface;
compilation transforms them with the asset and carries them unchanged through
material clipping as `projection_plane`. Native loading validates thin, planar
receivers and uses those anchors for top/bottom height evaluation. Assets without
this metadata retain polygon-derived planes. Tests cover clipping, translation,
rotation, duplicated placements, invalid anchors and native/shipping round-trips.
The binary shipping schema advances to datadir 19 / mission 10; older binary
bundles must be regenerated. Existing source files and hackable JSON without the
optional field retain their loading behavior.

York was recovered again into `work/map-compile/york-plane-anchor-recovery` and
both variants compiled into `work/map-compile/york-plane-anchor-native`. The same
51,381 native queries now have zero coverage, material or elevation differences.
This fixes the observed float32 subdivision mismatch, without accepting a height
tolerance. Exact coverage grouping still detects approximately 2.777463 square
pixels assigned to different ordered plane anchors, even though those flat planes
give identical sampled native heights. Full receiving-priority and traversal
verification is still required; the candidate remains outside the reviewed catalog
and the regenerated definitions remain unpublished.

The receiving-plane migration was also checked across all nine source maps.
`work/map-compile/all-plane-anchor-native/diagnostics.json` records nine successful
native constructions. `pipeline/src/compare-receiving-plane-anchors.ts` compares
ordered anchor triples at float32 bit precision, including the export-frame
offset, and reports receivers without anchors separately. Its baseline audit
(`anchor-roundtrip.json` in the same directory) finds all 698 explicit receiver
triples unchanged: Croisement01 27, Croisement02 21, Croisement03 14, Derby 78,
Leicester 63, Lincoln 118, Nottingham 106, Sherwood 17 and York 254. This checks
anchor values, not whether the correct source receiver owns each point.

That baseline also contained 413 elevated receivers using polygon-derived planes and default
material 0. These are generated fallback coverage outside the explicit material
supports; they need separate coverage/ownership review. Their total projected
area is not uniformly negligible: approximately 4,744.89 pixels squared in
Leicester, 3,501.57 in Sherwood, 1,331.40 in Lincoln and 735.89 in Derby. Passing
construction and anchor-value checks therefore does not establish full receiving
coverage or material parity. All recovered definitions remain unpublished.

The compiler no longer fills unsupported portions of a merged movement boundary
with default-material receivers when explicit receiving supports are present.
Implicit default coverage is restricted to the surfaces that actually author it.
This preserves openings such as the Sherwood platform hole, where the reference
receiving polygons provide no receiver. An exported synthetic platform fixture
verifies the same behavior through native queries: no receiver in the opening,
with elevation preserved on its surrounding edges.

Recompilation into `work/map-compile/receiving-gap-native` removes 412 unsupported
receivers across the nine maps. All nine descriptors construct natively; their
non-sight geometry is unchanged after remapping interior constructor references,
and all 698 anchored receivers are unchanged. That diagnostic retained one
unanchored receiver on Derby's `derby-second-drawbridge`, covering 731 square pixels.
These checks still do not certify whole-map
receiving priority, source coverage or actor traversal.

Further inspection found that last receiver was incorrectly inferred from an
editor preview bounding box, whose asset metadata explicitly says it has no sight
association. Recovery now creates no walkable surface from preview projection
placeholders. Compilation also excludes preview bounds from automatic part
collision, while explicit asset surfaces, passages and volumes remain usable.
Referencing a preview box as a gameplay obstacle requires an authored volume
instead. The bridge's actual state geometry and behavior still need asset authoring;
removing the fabricated surface does not complete that work.
The batch under `work/map-compile/preview-bounds-native` passes native construction
for all nine maps. Derby now has 60 movement areas, 348 sight records, 70 doors and
two jump pairs; the other eight compiled geometries are unchanged. No unanchored
receivers remain in this recovered static batch. This does not certify the
unrecovered state geometry or publication readiness.

`pipeline/src/inventory-patch-dependencies.ts` audits shared sight, mask and door
references across supplied patches and flags sight changes that activate receiving
projection surfaces. It keeps each patch and initial/applied role distinct, checks
for stale sight indices, and distinguishes masks by layer plus index. It does not
assign asset ownership, recover motion changes or import mission actors/scripts.

The authoring inventory in `work/map-compile/mission-map-effects.json` covers all
39 retained mission files and records hashes of each mission and its map source.
Derby's three missions all link both drawbridge patches to initial sight obstacle
267; the second additionally activates projection 268 and binds doors 37/38.
Obstacle 267 lies at the first bridge, so assigning both geometries to the second
asset would break independent placement. This shared dependency needs an explicit
map/mission ownership decision in the implementation, not an inferred asset merge.
The second bridge's visual elevation also differs between mission variants (1 vs
110), and its old preview source hash no longer matches the current JSON. No state
recipe has been approved from that stale pin.

Leicester's map patches activate projections 389, 384 and 390. Native interchange accepts projection obstacles
in initial/applied sight lists, with the same missing-reference and duplicate-control
validation as other obstacles. Runtime tests cover activation, swapping and reset:
collision follows activation, while elevation/material lookup retains all registered
receivers, including inactive ones, and navigation storage remains unchanged.
Assets can now link a walkable surface to a local part or volume with `projectionVolume`, replacing
its generated thin receiver with that volume's full geometry, thickness, flags and
material links. Existing initial/applied sight lists control its activation. Tests
cover movement, rotation, duplication, export into the native fixture, and native
top/underside collision plus opaque-ray blocking through activation and reset.
Missing links, mismatched heights, disjoint walking contours and multiple receiving
areas are rejected. Navigation can extend beyond its receiver without inventing
extra receiving coverage, matching their independent authored boundaries.
Overlapping physical/generated receivers require explicit
volumes on both surfaces, avoiding ambiguous overlap ordering.

One-time recovery now links uniquely owned, state-controlled projection surfaces
to their existing physical parts or local volumes. Across all nine source maps,
the three affected map-patch receivers are Leicester 384, 389 and 390. Fresh
Leicester recovery in `work/map-compile/projection-volume-recovery/leicester`
retains their ordered float32 vertices, top/bottom heights, physical flags and
default materials exactly. Compiled receiver indices 93, 56 and 243 respectively
bind their owning drawbridges' applied sight states. The diagnostic in
`work/map-compile/projection-volume-native` constructs successfully in Rust and
applies/resets all five recovered Leicester transitions, checking sight activation,
door rights and movement state restoration. This is not actor-traversal or visual
parity: the full scene still rejects unsupported visual states, 450 masks remain
unrecovered, and these candidates remain unpublished. Mission-carried projection
effects and shared controllers still need separate ownership and recovery work.
Physical receiving-plane validation now uses the first three ordered volume
vertices, retaining later vertex heights instead of requiring the whole volume
top to be planar. The authored walking surface must still agree with that plane;
degenerate first triples and height mismatches remain errors.

An all-map candidate audit in `work/map-compile/static-receiver-audit/audit.json`
found 557 static surface links whose uniquely owned physical parts exactly match
source float32 vertices and flags; 32 other surfaces lack that ownership/geometry
evidence. These are proposed links, not published definitions. Croisement03's 14
links compile and construct natively as 30 movement areas, 106 sight obstacles,
15 doors and 10 jump pairs. The other eight candidate maps remain rejected:
Croisement01/02, Leicester, Lincoln, Nottingham and Sherwood have physical
receivers spanning multiple generated movement areas; Derby and York first fail
on overlapping receiving-material priority. Fixing these requires navigation and
overlap authoring, not duplicating a physical obstacle across areas or flattening
its geometry. Native construction does not yet prove receiving-query, visual or
actor-traversal parity for Croisement03.

Receiver ownership now intersects authored walkable coverage with the compiled
area **including holes and blockers**. Outer-boundary overlap alone incorrectly
assigned a surrounding platform's receiver to a separate island inside its hole.
The editor/native island fixture verifies distinct receiver references, correct
stone/leaves material lookup, retained height and no direct walking route across
the gap. Physical receiving footprints themselves remain intact.

Recompilation in `work/map-compile/receiver-ownership-native` removes 96 wrongly
assigned generated receiver records from the previous static diagnostics: 2 in
Croisement01, 6 in Croisement02, 12 in Derby, 2 in Leicester, 23 in Lincoln, 1 in
Sherwood and 50 in York. Other geometry fields outside sight/building references
and warnings are unchanged; all nine diagnostics construct natively. A repeat of
the physical-part candidate audit still rejects eight maps. Derby now reaches a
real split of the east-hall receiver between two movement areas; York still first
fails material-priority checks. These remaining errors must be resolved through
navigation/overlap authoring before those candidate links can be published.

The 14 Croisement03 links now have a repeatable one-time recovery recipe in
`refinement/catalogs/croisement03-projections.json`. Run recovery with
`--projection-definitions refinement/catalogs/croisement03-projections.json`.
It validates the source/model pins, unique physical ownership, ordered float32
geometry and flags, and material references before changing any packet. Output
uses local part IDs; recipe source indices do not become runtime links. Stale pins,
changed shapes, missing material definitions and duplicate recipes fail atomically.

Fresh output in `work/map-compile/reviewed-projection-recovery/croisement03`
matches the prior audited baseline. The baseline plus independent one-pixel moves
of all 13 owning assets compile and construct natively in
`work/map-compile/reviewed-projection-native` (14 cases). Connection counts can
change when moved endpoints detach. These definitions are still unpublished:
Croisement03 retains 131 unrecovered masks, two missing movement transition
groups, and unverified visuals and actor traversal.

Croisement03's upper-terrace navigation boundary now has an explicit authoring
plane for the portion outside receiving coverage. The source-pinned recipe
`refinement/catalogs/croisement03-transition-planes.json` selects the associated
terrace receiver's plane for placing that changing contour only; it adds no
walkable or receiving surface. Recovery accepts it via `--transition-planes`;
`stage-navigation-state-assets.ts` accepts the same recipe after its ownership
argument. Missing coverage still fails when no explicit plane is supplied.

Staging created `croisement03-navigation-boundary-004` in
`work/map-compile/croisement03-transition-plane-stage-v2`. Fresh recovery into
`work/map-compile/croisement03-transition-plane-recovery` now has eight recovered
movement groups and one missing group (the multi-asset sight change). The export
in `work/map-compile/croisement03-transition-plane-native` retains exactly the
previous sight geometry, flags and material links, with regenerated area references.
All eight recovered transitions pass native apply/reset state checks. Masks,
shared state ownership, navigation coverage, visuals and actor traversal still
require verification before publication or a full-parity claim.

The remaining Croisement03 movement group now has one physical asset owner.
`refinement/catalogs/croisement03-state-assembly.json` groups complete obstacle
parts 102–105 into `croisement03-southwest-state-assembly`; one map patch enables
all four, and no other map patch controls them. The canonical staging tool retains
the complete model resources and part geometry in a common movable frame.
The staged library is `work/map-compile/croisement03-state-assembly-stage` and
fresh recovery is `work/map-compile/croisement03-state-assembly-recovery`.

All nine map movement groups now recover for this scene. The baseline and a
one-pixel eastward assembly move preserve the four parts' exact ordered float32
vertices and flags, and both pass native apply/reset checks for all nine transitions
in `work/map-compile/croisement03-state-assembly-native`. The assembly waypoint
moves with its geometry. This verifies movement/sight state binding only: patch 8
also controls layer-0 masks 122–124 (global mask records 128–130), which remain
unrecovered, along with visual states. The candidates remain unpublished and do
not yet certify actor traversal or full patch/map parity.
Mission-carried records also include traps, hiding places and
York gate effects; their presence in a mission file does not establish permanent
map ownership. The earlier recovered transition counts cover map-source recovery,
not this additional inventory. No mission population or scripts were added to maps.

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
selected model part. Skinned/animated geometry and blended materials reject
until their state or coverage is explicitly handled. Surface clipping
uses fixed-point polygon operations; recovery then rerasterizes with the map
compiler and requires exact source pixel coverage, allowing partially covered
edge cells only when their pixel samples match. Four Derby probes (mask records
15, 27, 67 and 93) still fail coverage against their obstacle-linked candidate
assets' published meshes. They are not recovered or published as gameplay masks.
Those four candidates lack 175, 323, 72 and 332 covered pixels respectively;
the gaps include interior pixels, so accepting boundary rounding alone is
insufficient. Reviewed cottage associations also require geometry work.

Cutout (`MASK`) materials can now supply physical alpha coverage to reviewed
recovery and `audit-mask-surfaces.ts`. The reader decodes pinned asset textures,
clips mesh triangles in UV space against nearest-sampled base-level alpha, and
interpolates the original surface positions and vertex alpha. Uniform material
alpha and degenerate UV mappings are supported. Opaque provenance atlases remain
opaque; foliage's explicitly declared vertex ownership channel does not multiply
physical opacity. Tests cover holes, cutoff equality, sloping geometry, vertex
alpha, degenerate UVs and the foliage metadata contract.
UVs outside the unit square, texture transforms, linear magnification and blended
materials still reject; mipmap/minification silhouettes are not certified by this
base-level authoring geometry.

The central Sherwood oak now passes through the alpha-aware support audit:
`work/map-compile/sherwood-central-oak-alpha-support.json`. Its cutout mesh expands
to 660,698 triangles. Of seven nearby mask probes, record 150 has complete support
for all 375 pixels; records 32/34/62/70/151/153 still lack coverage. This probe does
not establish ownership or recover a complete mask definition. Subsequent asset
review places record 150 on the central platform's lower ladder, not the tree.
The platform mesh still misses 146 of its 375 pixels (24 interior pixels); records
151 and 153 also lack platform coverage. Do not recover these masks onto the
overlapping tree. The reviewed mask total remains 72. Reviewed recovery now discards mesh triangles outside the
union of the requested masks' projected bounds before expanding texture alpha.
For these seven probes it reduces the candidate geometry from 660,698 to 3,327
triangles (99.5%) with identical complete support/gap reports, recorded in
`work/map-compile/sherwood-central-oak-alpha-bounded-support.json`. Accepted texels
also merge regardless of stored alpha when vertex alpha is uniform; varying
vertex alpha retains distinct clipping thresholds. Full-tree silhouette hashes
remain identical at baseline and 45-degree rotation. This does not simplify or
alter the published tree model. A fresh Croisement03 recovery also produces
identical gameplay candidates for all 93 assets, including its recovered mask
and state geometry (`work/map-compile/croisement03-bounded-mask-recovery`).
Broader tree recovery and visual filtering
fidelity remain unfinished.

Sherwood recovery now restores three omitted physical ladder volumes (97/98/101)
into the central-oak and ladder-oak platform assets. Their authored local volumes
also supply receiving geometry, preserving thickness and ordered height planes.
Lift connections explicitly select their local traversal surface, so two ladders
can share a part frame without ambiguous bindings; volume clearance IDs are also
independent. Clearance subtraction uses fixed-point clipping for near-coincident
edges that otherwise fail to close a polygon.

`work/map-compile/sherwood-ladder-volume-recovery` validates all 81 asset drafts.
The baseline and central-platform translation construct native maps with 29 areas,
294 sight obstacles, 15 doors and one jump pair. The ladder-oak platform also
compiles independently when translated 100 units away, or one unit together with
its separate oak asset. Across all four cases the three restored volume shapes
and flags match the source at float32 precision, and all four lift endpoint sets,
directions, types and lock rules match after translation. See
`work/map-compile/sherwood-ladder-volume-native` and its generator
`work/map-compile/verify-sherwood-ladders.mjs`.

The one-unit platform-only move still fails: isolating collision for each of the
81 assets identifies the unmoved oak as the only owner whose collision removal
makes it pass. Its recovered openings lie on the original traversal planes; they
remain with the tree when the ladder moves. This is a cross-asset collision and
clearance limitation, not missing ladder metadata. Do not erase neighbouring
collision to force a successful export. Native passage callbacks pass for all
12 directed lift endpoint pairs in each of the four successful scenes (48 pairs),
with a test actor entering and leaving the expected sector and layer. These checks
do not simulate approach routing, authorization or climb animation, and do not
certify full traversal or map parity. Recovery now inventories every sight record lacking a
physical asset owner: Sherwood retains record 13 (referenced by mask 76), plus
166 unrecovered masks, one light region and five sound sources. Counts of owned
sight records establish metadata presence only, not geometric fidelity.

The same passage-callback check passes across the nine earlier static drafts in
`work/map-compile/receiver-ownership-native`: Derby 32 directed pairs, Leicester
38, Lincoln 24, Nottingham 92, York 170 and the older Sherwood draft two. The
three crossing drafts contain no recovered lifts, so they exercise no callbacks.
The updated Sherwood cases above cover its additional restored ladders.

`work/map-compile/all-sight-owner-audit/audit.json` inventories all nine source
maps against their pinned assets and current explicit ownership declarations.
Only two source sight records still have no physical asset owner: Derby 35
(referenced by mask 6) and Sherwood 13 (referenced by mask 76). Both are solid,
opaque and mouse-active and neither belongs to a state patch. The other seven
inventories have no missing owner, but that does not prove the owned geometry is
equivalent, correctly grouped, published or complete in other gameplay features.
This audit omits mask recovery and is not a publication candidate. Wychford has
no corresponding source map for this comparison.

Visual inspection identifies both missing records as separate canopies, not
non-rendering pieces of neighbouring buildings: Derby's small canvas shelter
beside the lower west curtain and Sherwood's thatched preparation-table canopy.
The reviewed `derby-obstacle-drafts.json` and `sherwood-obstacle-drafts.json`
recipes pin their source data and record that ownership. Run
`pipeline/src/author-obstacle-drafts.ts --source LEVEL_JSON --recipe RECIPE_JSON
--out NEW_DIRECTORY` to author independent assets with local physical volumes
and visible volume-preview meshes. These are explicitly unfinished appearance
drafts; they contain no mission actors, invented navigation or source-map lookup.

The staged `derby-canopy-stage` and `sherwood-canopy-stage` scenes under
`work/map-compile` reopen successfully and recover 42/82 asset definitions with
zero unowned sight records. Baseline and 100-unit canopy translations match each
restored volume's ordered vertices and flags at float32 precision and construct
native maps (`canopy-draft-native`): Derby has 60 areas, 337 sight obstacles,
70 doors and two jump pairs; Sherwood has 29/295/15/1. This does not certify the
other geometry or promote these drafts to published complete assets.

Roof-volume geometry alone still lacks 87 mask pixels for Derby record 6 and
1,311 for Sherwood record 76, including support poles and silhouette details.
The `derby-canopy-mask-audit.json` and `sherwood-canopy-mask-audit.json` reports
retain these gaps; neither mask is recovered. Textures and appearance completion
remain required. Saving/reopening also now restores an empty resource list for
scene assets whose descriptor omits that optional field, avoiding a validation
failure after compact serialization removes the redundant saved list.

Canopy drafts now accept explicitly authored visual support posts beneath the
roof. The posts are model children in the same local asset frame and add no
gameplay collision. Derby's visible front post reduces mask 6's unsupported
pixels from 87 to 32 (no interior gaps); Sherwood's three visible posts reduce
mask 76's gaps from 1,311 to 805 (381 interior pixels). These measurements are in
`derby-canopy-pole-mask-audit.json` and `sherwood-canopy-post-mask-audit.json`
under `work/map-compile`. Remaining thatch, roof-edge and timber detail gaps
still require geometry authoring; neither mask is recovered yet.
`verify-canopy-drafts.mjs --posts` verifies the complete compiled gameplay output
is unchanged for both maps at baseline and after moving each canopy 100 units.
The newer scenes are `derby-canopy-pole-stage` and `sherwood-canopy-post-stage`;
textures and completed appearances remain unfinished.

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

Reviewed mask migration now accepts state-controlled masks only when the whole
patch mask set belongs to one asset and one recovered local transition. It writes
the local IDs into that transition's initial/applied mask lists after geometry
recovery succeeds. Missing masks, competing controllers and cross-asset ownership
remain errors. Tests cover both phases, duplicate transition discovery and invalid
ownership; the mesh-backed migration test also exercises a controlled mask.
When a reviewed set has no movement changes or door links, recovery can create
its local mask/sight transition directly. Every referenced sight obstacle must
belong to the same asset. Unrecovered movement or door behavior is an error;
this path cannot silently replace either with a mask-only state.

Croisement03's staged southwest assembly owns all three applied masks of patch 8
(global records 128–130; layer-local records 122–124), but its mesh lacks support
for 981, 803 and 5 covered pixels respectively, including 661 and 520 interior
pixels in the first two masks. The reproducible `audit-mask-surfaces.ts` report is
`work/map-compile/croisement03-state-assembly-mask-audit.json`. These masks need
authored surface geometry and remain unrecovered; state ownership alone does not
establish mask parity. The reviewed static-mask total remains 64.

Croisement03 also has one recovered changing mask: western platform record 126,
with all 2,592 pixels supported by `croisement03-group-062`. The pinned recipe in
`refinement/catalogs/croisement03-masks.json` uses the platform's 82.00001-unit
receiving elevation and binds its initial cover to local `movement-change-5`.
Baseline and a one-unit asset move preserve exact coverage, masking rules and
transition links; baseline non-mask geometry is unchanged. Drafts are under
`work/map-compile/croisement03-controlled-mask-recovery`, and diagnostics under
`work/map-compile/croisement03-controlled-mask-native`. Both scenes pass native
apply/reset checks for all nine transitions, now including mask activation and
unchanged unrelated masks. The map still has 130 unrecovered masks. This brings
reviewed recovery at that stage to 65 masks across seven maps, including 64 static masks;
publication, receiving-layer fidelity and changing visual/depth integration remain
unfinished.

Derby's west tower now contributes two applied masks (records 200/201, with
36,837/8,192 pixels), as one local mask-only transition. Leicester's great keep
contributes initial roof mask 436 and its local sight obstacle 375 as one
mask/sight transition, retaining three local roof-obstacle mask links. Both use
their authored receiving floors for character thresholds and preserve projectile
world XY. These additions bring reviewed recovery to 68 masks: 64 static and
four changing masks across seven maps. Derby has nine reviewed masks and 227
remaining; Leicester has seventeen reviewed masks and 449 remaining.
Drafts and baseline/moved diagnostics are under
`work/map-compile/{derby,leicester}-controlled-mask-{recovery,native}`. Derby's
baseline and six independently moved assets pass exact mask and native state
checks; Leicester's baseline and eight independently moved assets do likewise.
Visual patch effects, complete receiving-layer fidelity and publication are still
unfinished; these checks do not certify full map parity.

Nottingham adds two complete prison-door mask swaps: upper prison records
365/366 (1,444/1,812 pixels) and southwest prison records 407/408 (2,422/338 pixels).
Both pairs bind to existing asset-local door-triggered sight transitions. Upper
prison character thresholds use its 250.001-unit platform; southwest thresholds
receive on ground. The updated pinned mask catalog verifies twenty source masks
at baseline and after fifteen independent asset moves, with 507 masks remaining.
Drafts and diagnostics are under `work/map-compile/nottingham-controlled-mask-recovery`
and `work/map-compile/nottingham-controlled-mask-native`.
All sixteen descriptors pass native apply/reset checks. The diagnostic additionally
passes a test actor through each mask-controlled door in both directions, checking
destination sector/layer and the triggered mask/sight changes. These are passage
callback checks, not approach routing, lock-authorisation or animation playback.
Reviewed recovery now totals 72 masks across seven maps: 64 static and eight changing.

The nine-map changing-mask support audit is recorded in
`work/map-compile/controlled-mask-support-summary.json`. It found complete mesh
support for the recovered Derby, Leicester, Nottingham and Croisement03 sets,
plus five Lincoln candidates requiring ownership review. Support from terrain
alone does not assign a building mask to that terrain. The audit is incomplete
for textured-alpha tree meshes, some terrain frame selections and non-rendering
frames; it also filters candidate names and bounding boxes. Its zero-candidate
results therefore do not establish missing geometry or absence of recoverable masks.

`pipeline/src/verify-reviewed-mask-recovery.ts` reproduces the reviewed-mask
checks from a scene, pinned library, recovery packets and source-pinned recipes.
It compares exact covered pixels, flags, both optional polylines and obstacle-link
counts, rejecting ambiguous matches rather than choosing one. A source mask
may compile into multiple bitmap tiles. Their coverage must form
an exact disjoint union with consistent layer and obstacle links, and every
compiled mask must be accounted for by a reviewed recipe. Each owning asset
then moves independently; bitmap bytes, dimensions, translated boundaries and
compiled obstacle links must remain exact. A failed run invalidates the previous
manifest, records placement errors and exits unsuccessfully. For recovered
changing masks it also checks complete initial/applied mask sets against exactly
one compiled transition, before and after movement. These are geometry/state
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

The six-map static batch verifies its 64 reviewed masks and 45 independent asset
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

The earlier twenty-one-transition recovery batch passed native initialization, apply and reset checks:
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
Croisement03's elevated navigation-only change has approximately 24.49 square
pixels inside its movement area but outside every receiving surface. The reviewed
transition-plane recipe described above now supplies its boundary height without
adding receiving coverage. Its later southwest assembly recovery brings that
map's movement-group recovery to nine of nine; mask and visual state remain incomplete.
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

The physical-volume audit also checks whether visual component bounds preserve
the shared sight footprint and ordered bottom/top planes. Twenty-six split
records across Lincoln, Nottingham, Sherwood and York differ in footprint or
height; these are not certified equivalent merely because every record has an
asset owner. The audit is `work/map-compile/sight-partition-audit.json`.

York record 650 is wholly owned by the dedicated west-market shared occlusion
asset. Its five visual component bounds add about 1,154 square game units and
change the height planes. A reviewed `physical_volume_sources` declaration now
restores one asset-local volume and disables collision from the component bounds.
Recovery checks source/model hashes and exclusive ownership of every physical
part; receiving geometry or material regions require separate authoring. The
compiler reads only the resulting local definition, which moves with the asset.
The visual model remains intact. Other split records span separate assets and
still require ownership and geometry work; they cannot use this whole-asset fix.

`work/map-compile/york-whole-volume-recovery` retains the twenty reviewed masks.
The baseline and translated drafts reproduce the shared volume's ordered points
and flags at engine precision and construct 192 movement areas, 1,197 sight
obstacles, 254 doors and 72 jump pairs in Rust. Duplicating the complete asset
retains the first volume and adds exactly one independently translated volume;
the resulting 1,198-obstacle draft also constructs in Rust. Unit tests cover
rotation and duplication through the recovery-to-compiler path.
This is scoped geometry validation;
808 York masks and other previously listed gaps remain pending. No asset or map
is certified or published by this recovery.

Nottingham's front-market record 12 now has an explicitly reviewed partition
recipe in `refinement/catalogs/nottingham-market-volume-partitions.json`.
`pipeline/src/author-volume-partitions.ts` verifies source, model and descriptor
hashes, assigns every owner once, and writes independent draft descriptors. It
preserves the outer contour and constant bottom/top heights while removing the
east-green stall's extra collision across a notch. The four original meshes and
all other physical parts remain unchanged. Sloped, receiving, material-linked,
mask-linked and changing volumes require separate authoring and are rejected.

The reopened overlay is `work/map-compile/nottingham-market-volume-stage-v3`;
its recovered definitions are in `nottingham-market-volume-recovery`. The four
compiled pieces differ from the reference footprint by 0.000056 square game
units under fixed-point clipping, compared with roughly 2,512 extra square units
before correction. All bottom heights are exactly zero and top heights match at
engine precision. The baseline constructs 114 areas, 671 sight obstacles, 172
doors and 38 jump pairs in Rust. Each stall also compiles and constructs when
independently moved one unit east, with the other three volumes unchanged.
Those movements separate navigation sockets and therefore change connection
counts; they are placement checks, not baseline connectivity parity claims.
Trial translations of 100 units east/south blocked nearby entrances and were
rejected without suppressing collision. These separated-volume drafts did not
establish sight-query equivalence across partition seams; see the assembly check
below. Visual parity and publication remain unverified. These drafts
retain sixteen reviewed static masks; 507 Nottingham masks remain pending in
this recovery. The diagnostic manifest is `nottingham-market-volume-native`.

Native ray checks confirmed that an artificial partition face blocks a ray whose
endpoints are both inside the shared volume, while the complete volume leaves it
clear. Asset parts now support directed, local `sight_join_edges`. Compilation
joins matching placed edges only for compatible flat, static volumes; unmatched
edges leave independent pieces. Ambiguous matches, overlapping pieces, holes,
different flags/heights, or receiving/material/mask/state links are rejected.
Movement geometry stays owned by each asset. Sight references on unrelated masks
and transitions are rebuilt after joining, and duplicated or moved assets match
only their current geometric neighbors. No map identifiers or source indices
participate in seam matching.

The Nottingham authoring recipe now emits these seams. The reopened
`nottingham-market-volume-seams-stage` overlay and its `-seams-recovery` definitions
compile the four touching stalls into one volume with the reference vertices at
engine precision. The baseline constructs 114 areas, 668 sight obstacles, 172
doors and 38 jump pairs. Four independently moved drafts also construct, leaving
669 or 670 sight volumes as their seams separate. The native
`recovered_sight_assembly_preserves_native_ray_queries` diagnostic compares 100,000
deterministic rays against the reference volume, including impact presence,
coordinates and ray parameter; all match exactly. Its input is
`nottingham-market-volume-seams-native/sight-query-case.json` under
`work/map-compile`. This verifies sampled queries against this assembled volume,
not full-scene impact ordering, all placements, visual behavior or map parity.

The southwest parapet's flat record 219 uses a second reviewed partition recipe,
`refinement/catalogs/nottingham-southwest-parapet-volume-partitions.json`. Its north
and south assets now meet at the true bend, retain the southern inner corner and
have exactly ground-level bottoms. Their former component bounds added about
9,470 square game units and raised the bottoms by 0.00035–0.00044 units. The new
assembled footprint has zero difference under the clipping audit, and its eight
vertices match the reference at engine precision. Another 100,000 native sight
and impact queries match exactly.

`stage-volume-partitions.ts` stages draft descriptors in a new library overlay,
preserving model/resource paths and unchanged files. It verifies draft hashes,
input model/descriptor pins and the asset index, rejects conflicting per-instance
collision overrides, updates scene/index hashes and reopens the compact scene.
Its tests verify unchanged source files and model bytes, reload fidelity, stale
pin rejection, override rejection and exclusive creation of the output directory.

The combined market/parapet overlay is `work/map-compile/nottingham-parapet-volume-stage`;
recovery and native diagnostics use the matching `-recovery` and `-native`
directories. The baseline constructs 114 areas, 667 sight obstacles, 172 doors
and 38 jump pairs. Moving both wall assets and the attached southwest stair one
unit west also constructs, with 171 doors and 37 jump pairs as external sockets
separate. After correcting comparison of equivalent receiving planes, moving only
the north wall east now reaches the separate stair's unsupported landing check;
moving it west also leaves that landing unsupported. Those failures remain
explicit. This does not certify arbitrary detached wall/stair placements,
receiving-surface parity, appearance or publication.

York records 213 and 876 now have reviewed partition recipes in
`york-arcade-volume-partitions.json` and
`york-precinct-parapet-volume-partitions.json`. Each follows the existing component
seam, projected onto the exact outer contour. Record 213 restores ground-level
bottoms beneath the arcade/gallery volume instead of the roughly 89.9-unit gap
in component bounds. Record 876 restores the bastion's inner arc instead of
filling it, and corrects its slightly negative bottoms and raised top. Both retain
independent assets and assemble only when their local seams coincide.

The combined overlay is `work/map-compile/york-flat-volume-stage`, with definitions
in `york-flat-volume-recovery` and diagnostics in `york-flat-volume-native`.
It also retains the earlier correction for record 650. The baseline constructs
192 movement areas, 1,195 sight obstacles, 254 doors and 72 jump pairs. Each of
the four assets also constructs after an independent one-unit eastward move,
with 1,196 sight obstacles. Moving the arcade house separates two external door
and jump connections; the other three tested placements retain baseline counts.
Each assembled volume reproduces its reference vertices at engine precision and
passes 100,000 exact native sight/impact comparisons. The twenty reviewed York
masks remain present; 808 masks and the other listed gaps remain pending.
These are draft geometry/query checks, not publication or complete map parity.

Some scene-pinned York assets are absent from the older palette index. Partition
staging now registers those verified descriptors in the new overlay's index;
duplicate entries or conflicts with existing scene pins still fail. Tests verify
that the source index remains unchanged. Five of the twenty-six audited split
records now have correction drafts; the other twenty-one remain uncorrected in
that audit, including receiving volumes and more complex ownership cases.

Lincoln records 99 and 110 now have reviewed recipes in
`lincoln-southeast-parapet-volume-partitions.json` and
`lincoln-south-parapet-volume-partitions.json`. The existing turret/curtain and
bastion/curtain seams coincide with boundary vertices, so each asset retains an
exact portion of the contour and explicit local joining edges. Record 99 now
runs from ground to 363.001 instead of component bounds at 350–380. Record 110
runs from ground to 340.001 instead of bottom 320 and mismatched tops 355/364.
Their assembled reference vertices match at engine precision, and each passes
100,000 exact native sight and impact comparisons.

The overlay is `work/map-compile/lincoln-parapet-volume-stage`; recovery uses the
matching `-recovery` directory and retains four reviewed masks, with 424 still
pending. The baseline constructs 113 areas, 567 sight obstacles, 89 doors and 10
jump pairs. All four assets independently moved one unit east now compile and
construct in Rust. The corner turret produces 569 sight obstacles; the other
three produce 568, with unchanged door/jump counts throughout. The complete
successful batch is `lincoln-parapet-volume-native`. The baseline-only query
inputs are also retained under `lincoln-parapet-volume-baseline-native`.
Visual parity and publication remain unresolved. Seven of the twenty-six audited
split records now have correction drafts; nineteen remain uncorrected in that audit.

Receiving-material conflict checks compare the native binary32 height-plane
coefficients after winding correction, rather than requiring identical anchor
coordinates. Moving a flat surface can change its anchors without changing its
runtime plane. The compiler retains authored anchors and still rejects different
materials or coefficients, including signed-zero differences. Regression tests
cover these distinctions; 10,000 deterministic flat/sloped triangles matched Rust
initialization bit-for-bit using `editor_receiving_plane_coefficients_match_native_initialization`
and `ROBIN_PROJECTION_PLANE_CASES`. This fixes the false Lincoln conflicts without
claiming complete receiving coverage, traversal or map parity.

To reproduce the coefficient comparison, run
`node --test shared/src/native-projection-plane.test.ts` from `level-editor` with
`ROBIN_PROJECTION_PLANE_CASES` set to an absolute output JSON path. Then use the
same environment variable from the repository root with
`cargo test -j 1 -p robin_engine --lib editor_receiving_plane_coefficients_match_native_initialization -- --ignored --nocapture`.
