# Wychford — The Tollkeeper's Ledger

An original fortified riverside market town assembled from the shared Leicester
and Derby asset catalog. The town controls a narrow river crossing; the keep
overlooks a market and working yards, while the opposite bank remains rural.

## Layout

- **North: tollkeeper's keep.** A compact walled bailey, guarded gatehouse and
  administrative courtyard form the destination.
- **Center: market square.** The well is the visual landmark. Cottages, a guildhall,
  carts and delivery yards frame the square without filling the pedestrian routes.
- **West: church and gardens.** A quiet approach through orchard cover and
  residential backyards reaches the bailey's western side.
- **East: river and workshops.** Two crossings connect the riverside work yards
  with cottages on the rural bank. Trees and cargo break long sightlines.
- **South: entry road.** A broad road introduces the market and the keep beyond.
  A western lane and eastern river path offer early alternatives.

The River Wych and the bailey battlements are editable 3D splines. Select them
in the Paths panel to reshape the river or fortifications. Wall width is measured
across each local section, so a bent source segment retains a substantial walkway.
Five straight curtain sections join corner defenses and the gate. Their cross-sections
are flipped to face the parapets outside the bailey; the Paths panel exposes this
as **Flip battlement side**. The ground mesh has a raised bailey and sloping banks
around the winding river. Gardens, wooded ridges, fences and working yards make
the space between buildings part of the layout.

The recipe uses 50 distinct shared assets, including five tree models and a
watermill. `terrain.png` is an image-generated ground background that follows the
placement recipe's roads and courtyards, using the library's terrain and a game
scene as references. It is painted in ground-plane proportions (approximately
2600 × 3836) and compressed to map-pixel proportions on export, matching the
35° camera's foreshortening rather than displaying overhead texture details. `river.png` is a separate image-generated repeating water tile based
on the library's moat palette; it stays attached to the editable river spline.
The main crossing uses the open East Village Footbridge asset.

**Sun & shadows** controls the light direction, elevation and shadow strength.
The scene starts with a northwest sun. Buildings, battlements and foliage cast
shadows onto the terrain while their baked texture colors remain unchanged.
Lighting settings save with the map and participate in undo/redo.


## Proposed mission

Recover the tollkeeper's ledger from the keep and escape over the southern
footbridge. The market road is the direct, exposed route. The orchard and church
yards provide the cautious route. The river workshops provide the longer flank.
Guard positions, patrols, mission scripts and navigation are design proposals,
not implemented mission content.

## Build and open

From level-editor/:

    pnpm --filter pipeline exec node src/compose-wychford.ts

The generator writes Wychford.level3d.json, its terrain GLB and scene metadata,
to library/scenes/. Reload the editor with that library
connected and select **Wychford**. All placed assets remain individual editable
groups and retain pinned references to the shared library. To regenerate an
existing scene, pass `--overwrite`; this replaces local edits to Wychford.

This is an editor scene, not an installed playable level. The current game baker
does not support imported standalone geometry. The deterministic placement recipe
and terrain generation are in pipeline/src/compose-wychford.ts.
