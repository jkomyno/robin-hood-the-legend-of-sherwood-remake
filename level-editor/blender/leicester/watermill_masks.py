"""Freeze watermill component masks before preparing its immutable input packet."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np


def generate(root, output):
    root, output = root.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = root / 'layers/covered.png'
    inventory_path = root / 'source-audit/native-masks/manifest.json'
    inventory = json.loads(inventory_path.read_text())
    for record in inventory['masks']:
        record['png'] = str(inventory_path.parent / record['png'])
    size = Image.open(source).size
    def native(index):
        record = next(r for r in inventory['masks'] if r['index'] == index)
        image = Image.new('L', size)
        image.paste(Image.open(record['png']), tuple(record['box_top_left']))
        return np.array(image) > 0
    def polygon(points):
        image = Image.new('L', size)
        ImageDraw.Draw(image).polygon(points, fill=255)
        return np.array(image) > 0
    # Only traced visible walkway top faces are accepted; its vertical sides
    # remain unknown. The far stone lip is a separate occluding raised surface.
    platform = polygon([(2378,953),(2405,945),(2434,970),(2482,968),(2495,986),(2417,990)])
    platform |= polygon([(2488,971),(2517,964),(2557,953),(2610,940),(2637,932),(2650,951),(2495,986)])
    for index in (59,170,171,172,173,174,175):
        platform &= ~native(index)
    # Native172 deliberately covers the spoke apertures and foreground stones.
    # Geometry supplies the aperture; this source-traced boundary removes the
    # stone lip that must never appear on the wooden wheel.
    front_lip = [(2468,961),(2481,960),(2529,949),(2536,935),(2558,930),
                 (2561,936),(2564,940),(2611,932),(2614,937),(2660,930),
                 (2660,1040),(2468,1040)]
    lip_outline = [(2481,960),(2529,949),(2536,935),(2558,930),
                   (2561,936),(2564,940),(2611,932),(2614,937),
                   (2617,941),(2560,954),(2482,969)]
    lip = polygon(lip_outline) & ~native(175)
    platform &= ~lip
    wheel = native(172) & ~polygon(front_lip) & ~native(175) & ~lip
    derived = [(19001,'platform',platform),(19002,'wheel',wheel),(19003,'stone-lip',lip)]
    counts = {}
    for index, label, bitmap in derived:
        path = output / f'{label}.png'
        Image.fromarray(bitmap.astype('uint8')*255).save(path)
        inventory['masks'].append(dict(index=index, png=str(path), box_top_left=[0,0],
            box_size=list(size), derived=True, evidence='Source-traced component partition; see watermill-inspection/platform-grid.png and village-inspection/watermill-wheel-grid.png.'))
        preview = np.array(Image.open(source).convert('RGB'))
        preview[~bitmap] = 115
        Image.fromarray(preview).crop((2300,800,2670,1007)).resize((1110,621)).save(output/f'{label}-known.png')
        counts[label] = int(bitmap.sum())
    inv = output / 'inventory.json'
    inv.write_text(json.dumps(inventory,indent=2)+'\n')
    rows=[]
    def assign(node, indices, exclusions=()):
        row=dict(source_node=f'building-{node:03}',mask_indices=indices,reviewed=True,
                 evidence='Watermill source/canonical-node overlay and native component silhouettes manually inspected; source-visible component ownership only.')
        if exclusions:
            row.update(exclude_mask_indices=list(exclusions),exclusions_reviewed=True,
                       exclusion_reason='Visible foreground chimney, bay, wheel, railing, or low wall belongs to its separate source component.')
        rows.append(row)
    assign(76,[19001])
    for n in (77,78): assign(n,[171],(98,175))
    for n in (79,80): assign(n,[170],(172,173,174,175))
    assign(81,[174],(173,))
    assign(82,[98])
    assign(83,[173])
    for n in range(84,88): assign(n,[19002])
    manifest=dict(version=1,mask_inventory=str(inv),projections={'exterior':dict(
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        state='Covered Day static watermill artwork. No wheel animation or patch transition is reconstructed by this packet.',assignments=rows)})
    (output/'source-masks.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (output/'evidence.json').write_text(json.dumps(dict(accepted_pixels=counts,
        platform_polygons='Two source-visible top-face polygons, excluding native59 foreground foliage and building/machinery masks.',
        wheel_front_stone_exclusion=front_lip,
        limitations=['Native wheel silhouette includes background in spoke apertures; actual geometry must keep these openings empty.',
                     'Hidden wheel circumference/depth cannot be established by these masks.',
                     'Stone-front lip and railing require separate geometry; platform masks authorize top faces only.']),indent=2)+'\n')
    return counts


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    print(generate(args.root,args.output))
