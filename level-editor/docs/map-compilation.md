# Compile a map into a game mod

Open a map in the level editor and click **Export mod ZIP**. No local compiler,
server-side bake service or filesystem grant is needed. The button compiles the
current committed document revision, including unsaved edits. Finish or cancel
an in-progress spline before exporting. Save and Download still save the editable
map document; compilation does not mark edits as saved.

Place the downloaded ZIP in the game's configured mods directory (normally
`datadirs/mods`, or the directory selected with `ROBINHOOD_MODS_DIR`), then launch
the map from Custom Missions. The installed base datadir supplies characters and
shared resources. The ZIP is an overlay, not a standalone copy of the game.

The output contains:

```text
details.json
Data/Levels/editor-<map>.level.json
Data/Levels/Day/editor-<map>.map.png
Data/Levels/Day/editor-<map>.min.png
Data/Levels/Day/editor-<map>.occlusion-depth.png
compile-report.json
README.txt
```

Names are normalized and prefixed with `editor-` to avoid replacing base maps.
Two maps whose names normalize to the same name must not be installed together.
The descriptor remains editable JSON, including the automatically selected spawn.

## Rendering and coordinates

Compilation renders the actual placed assets and spline geometry from the map
camera at one pixel per map unit. It excludes selection outlines, grids,
population/mission previews and other editing guides. Hidden objects/groups are
excluded. Patch visuals always use their initial state, independent of preview
switches. Synthesized texture fill is included regardless of the display switch.
The document's sunlight settings are included.

An explicit export frame wins over the source map size. Otherwise a bounded map
keeps its dimensions and an unbounded map fits its visible mesh vertices.
Fractional crop edges round outward. Geometry and the camera are rebased by the
same crop origin. Exports above 16,384 pixels per side or 64 megapixels fail before
allocating the output buffers. Rendering uses 1024-pixel tiles to avoid depending
on the viewport size or creating one enormous GPU render target.

Depth is a grayscale 16-bit PNG aligned with the map. Its values are
`round(clamp((surface_ground_y - crop_y) / height, 0, 1) * 65535)`, with zero for
uncovered pixels. Physical texture alpha clips the depth pass; alpha used only
for texture provenance does not. The engine compares this field with character
ground Y to hide sprites behind the baked scene.

## Current gameplay scope

The result is an **unscripted map sandbox**, not an export of a selected mission.
Authored obstacle footprints follow object/group transforms and the crop origin.
Sight volumes use each obstacle's minimum bottom and maximum top height. Solid
obstacles intersecting ground level become movement blockers. The compiler finds
a spawn with 16 map units of clearance from those blockers; it reports an error
if it cannot find one.

The following remain to be compiled:

- Multiple navigation layers, raised walkways, lifts, jumps and sloped volumes.
- Mission scripts, objectives, triggers, population and items.
- Interactive patch transitions and their changing geometry/graphics.
- Collision for scenery without authored obstacles and for spline surfaces.

For now, walkable space is the export rectangle minus ground-level blockers.
Terrain holes and surfaces without authored obstacles do not constrain movement.
These limitations also appear in the editor and in the archive's compile report.

## Verification

From `level-editor/`:

```sh
pnpm --filter app exec node --test src/map-compile.test.ts src/editor-viewport.test.ts
pnpm --filter app typecheck
pnpm --filter app dev --host 127.0.0.1 --port 5182 --strictPort
```

With the dev server running, in another terminal:

```sh
CHROME=chromium TEST_PAGE=map-bake.html node app/tests/run-lifecycle.mjs http://127.0.0.1:5182
```

The browser fixture tests crop alignment, tile boundaries, hidden geometry,
sRGB output, texture alpha semantics and lossless depth encoding. To regenerate
the small archive used by the Rust loader contract test, add
`TEST_BAKE_ZIP=../crates/robin_rs/tests/fixtures/editor-bake-contract.zip` to that
command. From the repository root run:

```sh
cargo test -p robin_rs --test editor_mod_export
```

This test discovers and mounts the real browser-produced archive, expands the
descriptor into runtime sight/motion data and reads the map, minimap and depth
through the engine's terrain loaders.
