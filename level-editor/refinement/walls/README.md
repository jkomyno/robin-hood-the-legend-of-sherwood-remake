# Prepared spline sources

The editor's preset gallery uses dedicated `spline-*` copies, not arbitrary
compound wall models. The original shared models and map placements are untouched.

The initial audit inventoried 1,223 non-Wychford assets and rendered 346 likely
wall/boundary candidates. The 19 shipped strips cover Derby, Leicester, Lincoln,
Nottingham, York, Sherwood, and Croisement01–03. Natural banks and bridge railings
are named explicitly. Round corner models are selected from standalone towers.

`recipes.json` records source model IDs, selected components, spatial cuts,
longitudinal direction and trims. For modeled battlements/posts, `feature_height`
sets a reviewed horizontal slice above the rail or crenel floor. Extraction snaps
both trims inward to gap midpoints. This retains complete features, and the join
gap is the average of the two original end gaps. Descriptors record the feature
count and measured seam/internal gaps. A window with fewer than two gaps fails.
The final clipped mesh is measured again to reject truncated or missing features.
`level_feature_tops` removes the source's longitudinal height slope while retaining
crenel depth. Texture-only sources use reviewed scene-unit `interval` cuts and
`repeat_note` documents the visible landmarks; `level_top` removes height jumps.
`cross_interval` clips across the wall after rotation into its longitudinal frame,
so attached stairs/platforms can be excluded without cutting diagonally through
the curtain. Leicester's castle preset uses the southwest curtain's three complete
merlons; its former single-crenel source joined two end merlons into an oversized one.
Triangle clipping interpolates the original UVs
and vertex attributes. Solid-wall copies can straighten their cross-sections;
low banks can level their ends. Fences retain the thickness differences between
posts and rails. Every output descriptor records the source model/descriptor
hashes and exact recipe. Mesh corrections only affect these copies.

Run from `level-editor`, with the Vite app serving on port 5181:

```sh
python3 refinement/walls/inventory.py
TMPDIR=/home/phire/.cache node refinement/walls/render-audit.mjs
python3 refinement/walls/contact-sheets.py
python3 refinement/walls/build_segments.py
TMPDIR=/home/phire/.cache node refinement/walls/render-audit.mjs --segments --force
python3 refinement/walls/report.py
```

Inspect `work/wall-presets/review.html`, `repeat-joins.jpg`, `all-strips.jpg` and `overview.jpg`.
Each full-model comparison has game-camera and angled views of the original,
prepared strip, three repeats, an S-curve, a corner and an enlarged join centered
in the frame. The browser checks that
the repeated and curved wall meshes are nonempty and finite. `--ids=id1,id2` limits a render run.

After reviewing those images:

```sh
python3 refinement/walls/publish_segments.py
```

Publication rejects stale model hashes, changed preset parameters and changed
original source assets. It installs only the dedicated copies, rebuilds the
catalog, and generates `app/src/assets/wall-presets.json`. Generated library
models and review images remain in the repository's existing ignored output
directories; the recipes and tools are versioned.

For a focused revision, both Python build/publish commands accept `--ids id1 id2`;
other staged/published presets are preserved. Render uses `--ids=id1,id2`.
`texture_profile.py id1 id2` renders an unlit source front with scene-unit X labels
for checking painted features that cannot be detected from the mesh silhouette.

The gallery compares segments, not complete reconstructions of every original
level wall. Some projection-only source models retain baked shadows, coarse
back faces and visible texture repetition. No new texture painting is applied.
Spline gameplay/collision compilation remains separate from this visual editor
work; these derived source descriptors do not invent obstacle footprints.

Verification:

```sh
python3 -m unittest discover -s refinement/walls -p 'test_*.py'
pnpm --filter app typecheck
pnpm --filter pipeline exec node --test ../app/src/spline-geometry.test.ts ../app/src/editor-viewport.test.ts
TMPDIR=/home/phire/.cache CHROME=chromium TEST_PAGE=spline-picker.html node app/tests/run-lifecycle.mjs http://127.0.0.1:5181
TMPDIR=/home/phire/.cache CHROME=chromium TEST_PAGE=spline-library.html node app/tests/run-lifecycle.mjs http://127.0.0.1:5181
```
