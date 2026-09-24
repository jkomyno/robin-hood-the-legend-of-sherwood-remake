# Wychford — The Tollkeeper's Ledger

An editable fortified market town assembled from Leicester, Derby and Sherwood
assets. The village occupies the west bank; the stronghold stands on the ridge
across the river to its east. Lincoln assets are not used.

## Layout

The market bridge connects the western church, shops and working yards to the
stronghold gate. Smaller lanes connect cottages, gardens and the mill crossing.
The eastern pasture contains the stable yard and gatekeeper's lodging. Fences
mark gardens, church boundaries and paddocks rather than blocking the roads.
Wooded margins, bank meshes and distinct Sherwood boulders break up the terrain.

`layout.json` contains the building, prop, fence, terrain and main-lane placements.
The recipe adds doorstep paths, trees, market furniture, river and fortifications.
The current scene has 158 placed asset groups, 33 road splines, one river and one
curtain wall, using 82 distinct shared models including the derived corner towers.

The curtain uses Derby's wall segment and matching conical turret. Its irregular
perimeter has straight curtain spans, a width of 44 units, and uniformly scaled
1.65× towers without additional horizontal widening. Sharp turns
insert towers automatically and terminate adjacent wall spans; gentler controls
retain a continuous curved wall. The gate opening remains deliberate. The wall's
parapet faces outward. Tower placement, minimum turn angle, size, orientation and
individual corner opt-outs remain editable in the Paths panel. A named wall preset
can be saved for reuse across levels in the same browser. Presets are browser
preferences; a map saves its own settings and pinned model references.

The four selected tree models are Leicester's irregular moat-bank and southeast
cottage trees plus Sherwood's leaning and spreading forms. The export helper
freezes Sherwood's animated leaf atlas into a static cutout texture with explicit
UVs and alpha for editor rendering and shadows. Other staged tree forms remain
available in the library but are not used in this layout.

## Ground, paths and lighting

`terrain.png` is image-generated overhead ground art, referenced to the game's
rendered palette. It contains no buildings or painted roads. Ground-plane image
proportions are approximately 3600 × 4184; the recipe compresses them to the
3600 × 2400 map image so the 35° camera provides the correct foreshortening.
The ground mesh supplies a raised eastern ridge and sloped riverbanks.

`path.png` supplies fine earth and gravel for editable footpaths, with a softened,
irregular alpha edge. Dense height samples keep the authored paths on the ground.
`river.png` is the repeating water and bank tile. The main crossing uses the open
East Village Footbridge, with a smaller timber crossing near the mill.

Sun direction and shadow strength save with the map. Wychford starts with a
northwest sun and 78% shadow opacity; buildings, trees and walls cast onto terrain.
Their baked source colors remain unchanged.

## Build and open

From `level-editor/`, stage the supplemental Sherwood pack into a fresh directory:

    blender --background work/sherwood-refinement/sherwood-refinement.blend --python blender/export-wychford-sherwood.py -- --output work/wychford/sherwood-pack
    pnpm --filter pipeline exec node src/publish-model-assets.ts ../work/wychford/sherwood-pack ../library/3d-assets
    pnpm --filter pipeline exec node src/compose-wychford.ts

The generator writes Wychford.level3d.json, its terrain GLB and scene metadata to
library/scenes/. Reload the connected library and select **Wychford**. Pass
`--overwrite` to regenerate an existing scene; this replaces local Wychford edits.

The source Blender workspace and published library models are local assets. The
committed recipe, layout and ground materials reproduce the scene with that library.

This is an editor scene, not an installed playable mission. Navigation, patrols,
mission scripts and game baking for imported geometry/splines are not implemented.
The proposed mission is to steal the tollkeeper's ledger from the keep and escape
via the southern footbridge, using either the market road or the garden lanes.
