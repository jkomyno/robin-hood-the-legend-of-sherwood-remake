# Interactive battlement corner editor

This editor records a human's exact source-artwork corner choices. Use it when
automatic or agent-picked crenellation positions are still visibly wrong.
It does not automatically rebuild or publish the model: a 2D line alone does
not determine wall thickness, hidden faces or depth. Preserve the user's points
as constraints when rebuilding the corresponding front/rear edge in Blender.

Prepare a project from review packets (each has `modified/views.json`):

```sh
python3 level-editor/refinement/prepare_corner_editor.py \
  --output level-editor/work/map-corners/project.json \
  path/to/first/review-packet path/to/second/review-packet
python3 level-editor/refinement/corner_editor.py \
  level-editor/work/map-corners/project.json --port 5182
```

Open http://localhost:5182. Select the wall, zoom with the wheel, and pan with
right-drag or Space-drag. Existing editable estimates are green/orange;
optional red edges are the previous saved mesh and remain read-only.
Use **New constrained zigzag**: click two endpoints for the upper boundary,
then click once below it to set the parallel lower boundary. Each further click
adds a vertical transition at that X position. Transitions are automatically
ordered along the run and alternate between upper and lower boundaries.
**Swap high / low** changes which boundary starts the zigzag. Drag endpoint
squares to change the slope, the lower diamond to change the separation, and
transition circles sideways. Both boundaries remain parallel and transitions
remain vertical. Use separate constrained runs when the wall turns.

Constraints are saved in each path's `rails` field: `upper` contains two
source-pixel endpoints, `depth` is the positive vertical separation,
`transitions` contains source X coordinates, and `startsUpper` sets the phase.
`points` is also regenerated as the ordered zigzag for existing downstream
consumers. Unfinished setup is saved too. These constraints preserve fractional
derived Y coordinates rather than rounding away parallelism.

**Freehand line** retains the original arbitrary-corner workflow and old saves.
Shift-click a segment inserts a corner. Arrow keys nudge one source pixel;
Shift-arrow nudges ten. Name separate runs, and specify front or rear edge.
Use separate lines for discontinuous or concealed runs rather than drawing
across unknown gaps. Hide lines with H to check the untouched artwork.

**Save to disk** writes `edited-corners.json` beside `project.json`, atomically.
Previous saves are retained in `corner-history/`. Download JSON also works.
Reload restores the disk save. Conflicting saves from another tab are rejected;
download your edits before reloading that tab. Unsaved edits prompt on exit.

Saved coordinates are full original-image pixels `[x,y]`, not crop-relative,
canvas or zoom coordinates. Each asset retains its original image SHA-256,
model path, source-camera elevation, crop and ordered paths. A path contains
`id`, `name`, `edge` (`front`, `rear`, `unspecified`) and `points`. Starting
estimates are not user approvals. South-wall projects without compatible
ordered corner lists start empty; trace them with New zigzag.

For the next Blender pass, read the ordered points directly from
`edited-corners.json`; do not replace them with evenly spaced or guessed
stations. Solve depth against the appropriate wall plane, retaining the source
camera from the packet (not the sunlight angle). If constraints cannot fit one
plane, show that discrepancy rather than silently moving user landmarks.
Reapply ownership-aware source projection, render actual saved-mesh edges on
the same art and return the result to the review gallery for geometry approval.
Texture synthesis still waits for geometry approval.

The reusable server only serves configured images and writes its fixed output
file. It binds to loopback and validates local-origin saves. It does not need
Blender running. Geometry rebuilds use Blender MCP or the reusable background
Blender workflow in [PROCEDURE.md](PROCEDURE.md).

Browser acceptance (isolated temporary project, no production annotation edits):

```sh
node level-editor/refinement/test_corner_editor.mjs path/to/project.json
```

It checks both Derby wall assets, drawing, dragging, insertion, undo/redo,
exact-coordinate disk save and reload, and the saved-mesh overlay toggle.
