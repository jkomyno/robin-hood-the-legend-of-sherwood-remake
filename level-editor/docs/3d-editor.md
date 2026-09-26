# 3D level editor

The editor (`app/`) loads a JSON map document and reusable local library assets.
Built-in maps use the same assets and placement representation as manual palette
insertion. Each part retains a local obstacle footprint and flags; part and group
transforms place it in the map. Mission-specific state belongs to the map.
See [the library format](library-format.md) for files, resource sharing and bindings.

The document is saved as `library/scenes/<map>.level3d.json`. Saving and publishing
are separate from the reconstruction-only game-file baker described below.

## Running

```
cd level-editor && pnpm install
pnpm --filter app dev            # http://localhost:5180
```

Open the hackable datadir (read) and the library folder (read/write; it
holds `scenes/` and `3d-assets/`). Pick a published map, or use **New map** to
start an unbounded canvas without choosing dimensions. Insert assets from the
library and save the map under its own name. The optional export frame records a
compile-time crop and does not restrict placement; it can intentionally clip assets.
There is no automatic reconstruction fallback for missing map manifests.

Choose a mission from the **Mission** menu to open its map and preview its initial
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

| action | how |
|---|---|
| pan / orbit around the point under the cursor / zoom to cursor | left drag / right drag / wheel |
| game camera (the map's own view) | `g` or the button |
| frame everything | `f` |
| select building / single part | click / alt-click (or click again inside the selected building); `Esc` clears |
| move | drag the selected building/part along the ground, or the gizmo (tick "lift" for height), or type dx/dy/dz |
| turn | `q` / `e` (15°) or type rot_deg |
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
