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
| Projectile/view/obstacle masks and masking polylines | Generate typed masks and links from asset geometry and states. A depth PNG alone does **not** replace all these semantics. | Planned |
| Walkable regions and layers | Transform asset-local surface polygons and heights; join coplanar regions or explicit local regions spanning several planes, then assign fresh sectors/layers. | Partial: flat/sloped surfaces, holes and ordinary multi-plane regions tested; cross-asset multi-plane joins and full-map connectivity unfinished |
| Movement blockers | Transform explicit asset-local movement contours; optionally select permanent part/volume solids and intersect them with walkable surfaces. Sight states stay independent. | Working in synthetic tests; recovered ownership still needs review |
| Openings in movement collision | Asset-local clearances remove only the owning asset's derived collision on the matching plane; sight geometry and other assets remain intact. | Working in compiler/runtime tests; recovery geometry failures remain explicit gaps |
| Navigation graph and fast-find grid | Engine constructs routing and spatial lookup structures from compiled geometry. No copied grids or graph bytes. | Working on synthetic maps |
| Sight/physical obstacles | Transform asset-local shapes, per-vertex heights and solid/opaque flags. Explicit transition references select initial/applied obstacles. | Static geometry working; sight transitions verified through native initialization, apply and reset; recovered state ownership still incomplete |
| Projection surfaces / elevation | Generate height planes linked to the new movement areas. | Partial: planar surfaces; elevation-boundary links unfinished |
| Doors, gates and lock rules | Transform local endpoints and optional click polygons; resolve neighbours geometrically and retain initial/alternate actor lock rules. Asset-local transition links either trigger state changes from doors or swap door permissions. | Compiler/native links implemented; recovered ownership and coverage incomplete |
| Building interiors | Asset-local interior definitions and entrances; generate virtual interior sectors and links. | Working for empty interiors; occupants remain planned |
| Lifts / special traversal | Asset-local traversal surfaces, type, direction and endpoints; explicit local join sockets combine placed segments into one sector with multiple height planes. | Working in synthetic compiler/runtime tests, including rotated/duplicated compound lifts; recovered metadata not yet published; changing lift surfaces unfinished |
| Jump zones and paired jump edges | Transform asset-local 3D edges and receiving contours; resolve landing anchors, regenerate crossed destination links and preserve long-jump/helper rules. Explicit local sockets pair edges owned by different assets after placement. | All 173 recovered pairs match reference geometry and flags; native registration verified; publication and traversal fidelity remain unfinished |
| Surface materials | Transform asset-local material polygons; rebuild the ground lookup subset and per-obstacle references independently. | Partial: ground/obstacle regions and terrain defaults tested in the engine; elevated-surface links unfinished |
| Light/shadow regions | Transform asset-local planar contours, resolve the receiving navigation layer and preserve ambience filters. | Partial: compiler/runtime tests cover day/night filtering and interior links; multi-plane regions and ambiguous ownership remain recovery gaps |
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
179 doors and 72 jump pairs construct successfully.
`export-gameplay-diagnostics.ts` generates
these explicitly labelled static probes from draft assets; the ignored
`recovered_static_exports_construct_native_geometry` test reads their manifest via
`ROBIN_ASSET_MAP_DIAGNOSTICS`. This checks construction, not movement/state fidelity.
These are unpublished drafts, not completed map exports or in-game round-trip
parity results. All nine recovered maps have now passed static construction;
no map has yet been certified at full parity, and authored maps still require
published gameplay definitions for their assets.

Material recovery now stores ground regions on the terrain asset and obstacle
regions on their owning parts. Elevated projection-material links remain explicit
recovery gaps. An empty ground-material list correctly activates no ground regions;
obstacle-only regions do not become ground water or footstep materials.

Terrain drafts also carry forest behaviour and fallback material. Recovery
normalizes clearance crossings introduced by integer rounding, preserving valid
regions instead of discarding a polygon whose signed area cancels. Nottingham's
hidden prison part retains its gameplay frame and passes the static check.

Sound recovery attaches global emitters to terrain and local emitters only when
their complete geometry has one containing asset part. Ambiguous/unowned sources
remain explicit gaps; they are not silently attached to terrain. Shared audio
samples are referenced from the base installation, rather than bundled in the ZIP.

Light recovery preserves projection priority when resolving receiving heights.
The latest all-map pass recovers 24 of 149 light/shadow regions into asset-local
drafts. The other 125 need ownership review or splitting across receiving planes;
they are not silently assigned to terrain. These drafts remain unpublished.

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
links and unrecovered geometry in `pending.doorTransitionBindings`. Nineteen of the
28 door-linked patches across the nine extracted maps now recover: seven in
Nottingham, five in York, four in Lincoln, two in Leicester and one in Croisement03.
The remaining nine are in Derby (one), Leicester (three) and Lincoln (five).
Linked changing geometry can establish a door owner only when every obstacle has
one owner and all belong to the same asset. `doorStateOwnershipRecovery` records
this evidence for physical-grouping review; conflicting or missing geometry cannot
select an owner. Recovery also supports sight changes without navigation
changes when every referenced obstacle and door belongs to the same asset.
The 42 changing sight shapes match source coordinates at native float32 precision
and preserve their flags. All eight initial/alternate permission fields match the source for the thirty-two
linked doors, and each binding retains its trigger direction.
Ordinary passages can connect to stair/lift surfaces in either direction without
becoming lift doors. This restores Lincoln's hall passages onto traversal surfaces.
All nine extracted map diagnostics compile and load; the native round-trip harness
applies/resets their 39 recovered transitions. It checks both
halves of door permissions as well as movement and sight state, including the
door-to-patch links for door-triggered transitions.
This does not establish complete door-transition coverage or publish those drafts.
The twenty-one recovered transitions pass native initialization, apply and reset checks:
movement-state bits, obstacle-sector activation and sight flags change and restore.
Transition reference points may lie inside static blockers; they must still resolve
to a unique surface at the authored height. Door and jump endpoints require an
unblocked receiving position.
The ignored `recovered_asset_transitions_apply_and_reset_native_geometry` test uses
`ROBIN_ASSET_MAP_DIAGNOSTICS` to load the generated transition-bearing probes.
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
again constructs 194 movement areas, 1,161 sight obstacles, 179 doors and 72 jump
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
