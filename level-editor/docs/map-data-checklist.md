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
| Walkable regions and layers | Transform asset-local surface polygons and heights; join coplanar regions and assign fresh sectors/layers. | Partial: flat/sloped surfaces and holes; full connectivity unfinished |
| Movement blockers | Transform explicit asset-local movement contours on their height plane; otherwise intersect collision volumes with walkable surfaces. Sight geometry stays independent. | Working in synthetic tests; recovered ownership still needs review |
| Openings in movement collision | Asset-local clearances remove only the owning asset's derived collision on the matching plane; sight geometry and other assets remain intact. | Working in compiler/runtime tests; recovery geometry failures remain explicit gaps |
| Navigation graph and fast-find grid | Engine constructs routing and spatial lookup structures from compiled geometry. No copied grids or graph bytes. | Working on synthetic maps |
| Sight/physical obstacles | Transform asset-local shapes, per-vertex heights and solid/opaque flags. | Working for static geometry |
| Projection surfaces / elevation | Generate height planes linked to the new movement areas. | Partial: planar surfaces; elevation-boundary links unfinished |
| Doors, gates and lock rules | Transform local endpoints and optional click polygons; resolve neighbours geometrically and retain initial/alternate actor lock rules. | Partial: rules preserved; state-transition triggers still missing |
| Building interiors | Asset-local interior definitions and entrances; generate virtual interior sectors and links. | Working for empty interiors; occupants remain planned |
| Lifts / special traversal | Asset-local traversal surfaces, type, direction and endpoints; explicit local join sockets combine placed segments into one sector with multiple height planes. | Working in synthetic compiler/runtime tests, including rotated/duplicated compound lifts; recovered metadata not yet published; changing lift surfaces unfinished |
| Jump zones and paired jump edges | Transform asset-local 3D edges and receiving contours; resolve landing anchors, regenerate crossed destination links and preserve long-jump/helper rules. | Partial: native zones/gates and duplicated assets tested; cross-asset pairing and unresolved recovery ownership remain unfinished |
| Surface materials | Transform asset-local material polygons; rebuild the ground lookup subset and per-obstacle references independently. | Partial: ground/obstacle regions and terrain defaults tested in the engine; elevated-surface links unfinished |
| Light/shadow regions | Transform asset-local planar contours, resolve the receiving navigation layer and preserve ambience filters. | Partial: compiler/runtime tests cover day/night filtering and interior links; multi-plane regions and ambiguous ownership remain recovery gaps |
| Environmental sound sources | Transform asset-local emitter polylines; retain sample IDs, timing, volume falloff, acoustic altitude, noise-covering distance and ambience filters. Global emitters need no position. | Partial: compiler/runtime coverage; ambiguous local ownership remains in recovery reports |
| Animated scenery / effects | Export asset animations, sprite resources, placement and display rules. | Planned |
| Interactive patches / state changes | Asset-local movement transitions compile initial/applied blocker polygons, trigger zones and fresh state bindings across all affected navigation areas. | Partial: movement-only transitions implemented; changing visuals, sight, masks and door links remain unfinished |
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
recovery drafts for Derby, Sherwood, Lincoln, Leicester, Croisement01, Croisement02 and Croisement03
pass the static base-geometry check, excluding explicitly counted movement transitions.
These are unpublished drafts, not completed map exports or in-game round-trip
parity results. Other maps still fail geometry checks; no original map has yet
been certified at full parity.

Material recovery now stores ground regions on the terrain asset and obstacle
regions on their owning parts. Elevated projection-material links remain explicit
recovery gaps. An empty ground-material list correctly activates no ground regions;
obstacle-only regions do not become ground water or footstep materials.

Terrain drafts also carry forest behaviour and fallback material. Recovery
normalizes clearance crossings introduced by integer rounding, preserving valid
regions instead of discarding a polygon whose signed area cancels. Nottingham
now reaches the next static-check blocker: gameplay on a hidden prison part.

Sound recovery attaches global emitters to terrain and local emitters only when
their complete geometry has one containing asset part. Ambiguous/unowned sources
remain explicit gaps; they are not silently attached to terrain. Shared audio
samples are referenced from the base installation, rather than bundled in the ZIP.

Light recovery preserves projection priority when resolving receiving heights.
The latest all-map pass recovers 24 of 149 light/shadow regions into asset-local
drafts. The other 125 need ownership review or splitting across receiving planes;
they are not silently assigned to terrain. These drafts remain unpublished.

Jump recovery produces asset-local drafts for 83 of 173 pairs; 90 still need
ownership or geometry authoring. Edge elevations remain independent of fractional
surface heights. Extraction now preserves the third endpoint coordinate and
remaps zone references, retaining both destinations when a crop crosses a pair.
The passing static diagnostics also include their recovered jump definitions.
Croisement03's door topology now survives recovery: asset-local navigation-region
labels preserve separate coplanar areas, including when their boundaries touch.
Labels are scoped to each placement; unlabelled surfaces retain normal merging.
Ground recovery reports per-region differences as well as overall coverage.
Nottingham's hidden prison part remains a blocker. York's compound lift now has
asset-local segment connections; its static check advances to a solid/surface
polygon-intersection failure elsewhere in the map. Lift recovery matches shared
edges once and stores local sockets, never runtime references between assets.

Stable terrain is recovered even when its movement area has changing obstacles.
The recovery inventory preserves all 27 changing-obstacle groups, their initial
and applied contours, and patch associations. These still need asset-local
transition ownership. `omittedMovementTransitions` makes that exclusion explicit
in the static diagnostic and prevents it from certifying full compilation.
Ground recovery uses fixed-point polygon operations and reports reconstruction
area differences; generated boundaries are normalized after integer rounding.
