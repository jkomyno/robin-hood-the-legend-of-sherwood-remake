# 3D level editor

The editor (`app/`) loads a JSON map document and reusable local library assets.
Built-in maps use the same assets and placement representation as manual palette
insertion. Each part retains a local obstacle footprint and flags; part and group
transforms place it in the map. Mission-specific state belongs to the map.
See [the library format](library-format.md) for files, resource sharing and bindings.

**Save** stores `<map>.level3d.json` in the browser's Origin Private File System
(OPFS), under `sherwood-level-editor/maps/`. Saving a library map switches to its
local copy, labeled **(Modified)** in the map menu and document status. The original
remains separately selectable under its plain name; both entries are available
after reopening on the same browser and origin. Existing browser saves also appear
as modified copies without changing their stored files.
Built-in maps have capitalized English display names (including Crossroads 1–3);
their file and mission identifiers stay unchanged. **Download** exports the current
document, including unsaved changes, as JSON with a local date and time to the second,
using hyphens and no timezone suffix, for example `york_2026-09-26T16-30-12.rhlos-map.json`.
Clearing site data removes local
copies, so download maps you want to keep outside the browser. Saving and publishing
are separate from the reconstruction-only game-file baker described below.
Drop one map JSON file onto the viewport to load it, including a timestamped download.
The document's map name determines its identity. Referenced assets must exist in
the connected library and pass validation. Imports remain unsaved until **Save**;
imports of built-in maps use the modified copy and keep the original selectable.

## Running

```
cd level-editor && pnpm install
pnpm --filter app dev            # http://localhost:5180
```

The library loads automatically over HTTP and remains read-only. The development
command prepares static links to the published files, excluding backups; Vite
serves them normally, without custom middleware. `3d-assets/index.json` lists
assets, and `scenes/index.json` lists map filenames. After publishing new files,
run `pnpm --filter app prepare:library` and refresh the page. For a local production
preview use `pnpm --filter app preview` after building. A standalone deployment
must also serve those static library files at `/library/`; the editor build does
not copy the large library into its output.

Optionally connect a hackable game datadir (read-only) for mission files, sprite
banks, and reference terrain/elevation. It is not the asset library or a save
destination. Pick a published **Map**, or use **New map** to
start an unbounded canvas without choosing dimensions. Insert assets from the
library and save the map under its own name. The optional export frame records a
compile-time crop and does not restrict placement; it can intentionally clip assets.
There is no automatic reconstruction fallback for missing map manifests.

The **Mission** menu to the right of **Map** shows only missions for that map,
using the same readable names as the highscore list. Choose one to preview its initial
placements. The map must have a published JSON manifest in the connected library. Soldiers,
civilians, and rescue characters use their configured sprite profile and initial
pose, with all 16 directions selected relative to the camera. Missing initial poses
use idle with a visible notice. Targets, pickups, scrolls, and mobile objects load
their own sprites; bonus quantities select the corresponding item variant.
Animation assets resolve the mission ambiance, then Day, then the animation root.
Spawn points appear as green markers. Missing sprite banks are reported explicitly
with magenta placement markers. Older hackable exports may omit bonus/relic banks;
the converter now includes those runtime object masters. Scripts, campaign party spawning, animation
playback, and mission editing/saving are not simulated by this preview.

Character placement recovers height from the support obstacle's top plane;
nonnegative target Z values override that calculation. The **Perspective** slider
runs from orthographic (0) to a 65° field of view, smoothly preserving the map's
average projected scale while introducing distance scaling. The fit uses the
whole scene rather than switching between outermost vertices. Both cameras use
tight scene depth ranges, with reversed depth on supported GPUs, to preserve
surface depth precision across zoom levels and narrow fields of view. Upright character
pixels project onto an approximate cylinder shell and top cap; dead, unconscious,
and tied poses use shallow ground volumes. Pickups use low object depth, while
scenery uses upright surfaces. These profiles preserve the source-camera image
while changing shape with elevation. Coats of arms use a cylinder rather than a
shallow pickup volume. Only prone characters use fixed 22.5° projection angles;
other directional sprites face the camera continuously. Single-view sprites
remain fixed in the world.
**Lock sprite orientations** switches other directional sprites between facing
the camera and fixed 22.5° projection angles, independently of camera rotation
locking. It is on by default and applies immediately; prone characters remain
locked in either mode.
Perspective panning translates the camera along the floor at a fixed height,
without refitting the lens as the map moves across the view.
Right-drag orbit keeps a fixed distance to the point under the cursor. Wheel zoom
moves the lens closer without refitting the whole map, so repeated zoom-in steps
continue to magnify the scene.
While drawing a path, click empty ground to add a point and left-drag empty ground
to pan without adding points. Drag a control point to move it. Control points and
the centerline stay visible above path surfaces, including transparent rivers.
**Lock rotation to 16 angles** snaps horizontal camera rotation to 22.5° steps
aligned with the sprite views. It snaps immediately when enabled and keeps tilt
continuous in both orthographic and perspective modes. The option is off by default.
Extreme angles remain an approximation because
the sprites do not contain unseen elevation views. Legacy sprite color keys are
decoded into color and authored shadow layers. Shadows project onto the support
plane, keep their world orientation during orbit, and use the game's 40% darkening
(10% in fog) instead of generic contact circles.

Switching missions on the same map preserves unsaved building edits and the camera.
**Map only** clears the mission overlay; **Mission entities** toggles its visibility.
Failed or superseded loads retain the current scene and release candidate resources.

## Controls

One header combines map and mission selection, editing actions, and the optional
game-data connection. Controls wrap within that bar on narrower windows.
The asset library's arrow collapses it to a narrow title strip. Drag its right
edge to resize it, or focus that edge and use the arrow keys. Reopening preserves
the chosen width and filters. Wider panels add asset columns while keeping previews compact.
Hovering an asset prepares its placement model. Dragging into the viewport renders
the actual instance under the cursor before release; returning to the library removes
that provisional instance. Dropping commits one undoable insertion. Transform input
drags likewise preview live and commit one undo step; Escape cancels the drag.

| action | how |
|---|---|
| pan / orbit around the point under the cursor / zoom to cursor | left drag / right drag / wheel |
| reset to the map's own view | `g` or **Reset view** |
| frame everything | `f` |
| select building / single part | click / alt-click; repeated normal clicks keep the whole building selected; `Esc` clears |
| move | drag the selected building/part along the ground, use the gizmo (tick "lift" for height), or type/drag the X, Y, Z inputs |
| turn | `q` / `e` (15°), or type/drag the rotation input; Shift gives finer input dragging |
| duplicate / delete | `d` / `Del` |
| hide | checkbox (hidden buildings and parts are left out of the bake) |
| snap a floating part | parts tagged "float?" show the suggested Δ; the button shifts y and z by −Δ (same map pixels) |
| undo / redo | `ctrl+z` / `ctrl+shift+z` |
| save | `ctrl+s` |
| overlays | obstacle outlines (document state), elevation lines |

Turning happens in game coordinates, where footprints are rectangles; in
the scene frame (Y stretched by 1/sin elevation) that is an affine map, so
each object is a translation wrapper (the gizmo's target) around a node
carrying the affine matrix.

## Bake

This CLI reconstructs the original obstacle volumes and textures; it does not
render placed library geometry or generated texture atlases. Editor/asset
publication and game-file baking are separate workflows.

Published catalog maps, unbounded maps and explicit export frames are not supported
by this CLI. It rejects these inputs rather than replacing reviewed geometry with
reconstructed boxes. An authored-map compiler remains to be implemented.

For reconstruction-only documents, an unchanged native mission-patch preview may remain:
the reconstruction path verifies its pinned source model and explicit `native_patch_preview`
binding, original mission-file hash, profile, initial state, membership,
footprint, visibility, and identity transforms. It omits that preview from
static reconstruction while preserving the existing native mission data.
Moved, hidden, duplicated, deleted, or otherwise changed previews are rejected,
as are imported standalone models. The CLI cannot export edited mission models
or new animation. The narrow exception preserves the older static-map bake
workflow without turning the preview into a fake sight obstacle.

```
pnpm bake --map york [--doc library/scenes/york.level3d.json] [--out work/york-bake] [--fill proc|synth]
```

Reconstructs the map like `volumes.ts` (textures always come from the
original positions), places every object with its transform (duplicates
share the source's faces), renders the map from the game camera with the
software rasterizer at full resolution and writes
`<out>/Data/Levels/Day/<map>.map.png`, `<map>.min.png` (original minimap
size) and `<map>.rhp.json` with the objects' obstacles moved (deleted ones
become empty polygons so indices stay valid, duplicates are appended).
Copy those over a hackable datadir to play. Without a document the output
is the round-trip test: York comes back with 97.7 % of the pixels identical
to the patched map (mean abs diff 3.2 of 765); the rest are 1-px seams at
face boundaries and grazing faces.

Not yet (see `3d-editor-plan.md`): masks are carried through unchanged (a
moved building keeps its old masks), patch states / interiors, Night and
Fog, other ambiances, in-browser bake, footprint editing, mission entity editing.
