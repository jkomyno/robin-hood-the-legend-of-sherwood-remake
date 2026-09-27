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
| Lifts / special traversal | Asset-local traversal surfaces, type, direction and endpoints. | Working in synthetic compiler/runtime tests; recovered metadata not yet published |
| Jump zones and paired jump edges | Transform local jump geometry; resolve landing surfaces and pair compatible edges. | Planned |
| Surface materials | Transform asset-local material polygons; rebuild the ground lookup subset and per-obstacle references independently. | Partial: ground/obstacle regions and terrain defaults tested in the engine; elevated-surface links unfinished |
| Light/shadow regions | Transform asset-local shadow polygons, resolve layers and preserve ambience filters. | Planned |
| Environmental sound sources | Transform asset-local emitter polylines; retain sample IDs, timing, volume falloff, acoustic altitude, noise-covering distance and ambience filters. Global emitters need no position. | Partial: compiler/runtime coverage; ambiguous local ownership remains in recovery reports |
| Animated scenery / effects | Export asset animations, sprite resources, placement and display rules. | Planned |
| Interactive patches / state changes | Compile asset states into changing visuals, collision, sight, masks, interaction zones and door links. Native transitions support movement changes across multiple navigation areas. | Editor compilation still planned; native transition groundwork only |
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
recovery drafts for Derby, Sherwood, Lincoln and Leicester pass the static geometry check.
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
