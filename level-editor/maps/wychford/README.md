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

`terrain.jpg` is a 5120 × 5120 overhead texture generated with
`openai/gpt-image-2.5-sunburst` through OpenRouter. A drawing derived from the
actual river and road splines fixes the layout; **Robin’s Godfather** and
**Sherwood Forest** renders supply the material references. Four native
2816-square patches overlap by 512 output pixels and blend into the final image.
`terrain-layout.svg` records the courtyard boundary and approach paving;
`terrain-generation.json` records the model, prompt, dimensions and reference hashes.
The castle interior uses worn earth and pale paving, contrasting with the grass,
rocky margins and village lanes outside. Full texture resolution survives export;
the ground mesh supplies camera foreshortening, the ridge and riverbanks.

The gate is rotated 27° to face outward through the curtain opening. The keep
sits farther west within the enclosure, leaving a passage along the eastern wall;
the smithy, keep approach, sentries and ledger placement follow the revised layout.

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
    pnpm --filter pipeline exec node src/populate-wychford.ts

The generator writes Wychford.rhlos-map.json, its terrain GLB and scene metadata to
library/scenes/. Reload the connected library and select **Wychford**. Pass
`--overwrite` to regenerate an existing scene; this replaces local Wychford edits.

To regenerate the ground with the configured `OPENROUTER_API_KEY`:

    pnpm --filter pipeline exec node src/generate-wychford-ground.ts --generate --refine

Inspect the resulting PNG before publishing it. The script prints its cache path;
requests are cached to avoid paying for repeat generations. To publish a reviewed
result without making another API request:

    pnpm --filter pipeline exec node src/generate-wychford-ground.ts --apply --texture /path/to/terrain-5120.png

Publication updates the embedded texture and its provenance, retaining the current
geometry and population. Runtime art uses quality-95 JPEG with full chroma detail
at the original 5120 resolution; the lossless generated patches stay in the cache.

The source Blender workspace and published library models are local assets. The
committed recipe, layout and ground materials reproduce the scene with that library.

## Population

`population.json` authors 21 soldiers, 22 civilians and three beggars, plus 14 item
placements. The layouts of **Attack Derby** and **Robin’s Godfather** informed the
guarded crossings, elevated lookouts and contrast between town and garrison. Guard pairs patrol the market, bridge approach and inner bailey.
Static sentries cover the gate, crossings, stores and stables; four ranged guards
stand on the curtain walk. Six civilian routines connect the church, homes, shops,
well, mill and stable yard. Routes pause at stations and reverse at endpoints.
Pairs use separate lanes so they do not occupy the same waiting position.

Supplies belong to their surroundings: food and money at market stalls, herbs at
the apothecary, ale at the brewery, nets by the ferryman, and ammunition near the
guards. Beggars sit at the church, market and gate approach; their authored hints
and every actor’s duty can be read in the editor’s **Town population** panel.
That panel also pauses animation and displays the nine route lines.

The population builder reads extracted character manifests from
`HACKABLE_DATADIR` (default: the local full-game extraction), packs the required
16-direction idle/walking frames into the connected library and samples the
terrain for placement heights. Run it after regenerating terrain. It updates only
the saved scene’s population and notes, preserving geometry edits. Runtime preview
loads these packed sprites from the library without reconnecting a game datadir.

This is an editor scene, not an installed playable mission. The animated routes
are placement previews; combat AI, beggar dialogue, collecting items, navigation,
mission scripts and game baking for imported geometry/splines remain pending.
The proposed mission is to steal the tollkeeper's ledger from the keep and escape
via the southern footbridge, using either the market road or the garden lanes.
