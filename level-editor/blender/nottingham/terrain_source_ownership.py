"""Conservative village terrain ownership: observed earth/grass minus all native scenery."""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
REGIONS = {
    'north approach earth road': [(645,2862),(750,2810),(827,2750),(1008,2750),(1083,2860),(1120,2910),(1112,2940),(1045,2895),(1007,2860),(866,2860),(755,2885),(673,2910)],
    'middle cultivated earth': [(735,3190),(910,3115),(1035,3125),(935,3350),(820,3360)],
    'northeast cultivated earth': [(1270,2800),(1490,2780),(1660,2880),(1635,3010),(1450,3020),(1340,2950),(1260,2895)],
    'central grassy paths': [(905,3400),(980,3220),(1105,3130),(1230,3100),(1340,3130),(1360,3230),(1280,3335),(1190,3400),(1060,3450),(940,3480)],
    'southeast earth path': [(1620,3160),(1705,3180),(1705,3280),(1600,3410),(1530,3390),(1575,3310),(1605,3230)],
    'southwest grassy paths': [(480,3380),(550,3400),(700,3430),(835,3410),(925,3400),(985,3480),(970,3510),(480,3500)],
}


def main():
    parent = WORK / 'mask-review/source-masks-v11-baseline.json'
    manifest = json.loads(parent.read_text())
    inventory_path = parent.parent / manifest['mask_inventory']
    inventory = json.loads(inventory_path.read_text())
    output = WORK / 'mask-review/inventory-terrain-reviewed'
    output.mkdir(exist_ok=True)
    accepted = Image.new('L', (2304, 3520))
    draw = ImageDraw.Draw(accepted)
    for polygon in REGIONS.values():
        draw.polygon(polygon, fill=255)
    scenery = Image.new('L', accepted.size)
    for row in inventory['masks']:
        source = (inventory_path.parent / row['png']).resolve()
        row['png'] = str(source)
        if row['index'] >= 527:
            continue
        native = Image.open(source).convert('L')
        layer = Image.new('L', accepted.size)
        layer.paste(native, tuple(row['box_top_left']))
        scenery = ImageChops.lighter(scenery, layer)
    # A two-pixel boundary guard avoids ownership errors at antialiased foliage
    # and wall edges. Native mask images remain untouched.
    accepted = ImageChops.subtract(accepted, scenery.filter(ImageFilter.MaxFilter(5)))
    index = max(row['index'] for row in inventory['masks']) + 1
    image_path = output / f'{index:06}.png'
    accepted.save(image_path)
    count = sum(1 for p in accepted.getdata() if p > 127)
    assert count > 10000
    inventory['masks'].append({'index': index, 'layer': 'authored-terrain', 'layer_index': 0,
        'png': str(image_path.resolve()), 'mask_type': 'reviewed-ground',
        'box_top_left': [0,0], 'box_size': list(accepted.size),
        'obstacle_indices': [], 'character_polyline': None, 'projectile_polyline': None})
    (output / 'manifest.json').write_text(json.dumps(inventory, indent=2) + '\n')
    manifest['mask_inventory'] = str((output / 'manifest.json').resolve())
    manifest['projections']['exterior']['assignments'].append({
        'source_node': 'ground', 'mask_indices': [index], 'reviewed': True,
        'constraint_kind': 'measured-ground-regions-minus-native-scenery',
        'accepted_source_pixels': count,
        'review_note': 'Observed village earth/grass regions only, minus every native scenery mask with a two-pixel margin. Water, buildings, trees, foreground walls and unreviewed ground remain unknown.'})
    target = WORK / 'mask-review/source-masks-terrain-reviewed.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    source = Image.open(WORK / 'source-states/covered.png').convert('RGB')
    preview = Image.new('RGB', source.size, (35,35,35))
    preview.paste(source, mask=accepted)
    crop = (460,2750,1710,3520)
    panel = Image.new('RGB', (2500,770))
    panel.paste(source.crop(crop),(0,0))
    panel.paste(preview.crop(crop),(1250,0))
    panel.save(WORK / 'environment-audit/terrain-source-ownership.png')
    evidence = {'regions': REGIONS, 'accepted_source_pixels': count, 'authored_mask': index,
        'source_sha256': hashlib.sha256((WORK / 'source-states/covered.png').read_bytes()).hexdigest(),
        'native_masks_excluded': list(range(527)), 'native_boundary_margin_pixels': 2,
        'scope': 'Positive observed local earth and grass; no claim that the full bitmap is terrain.'}
    (WORK / 'environment-audit/terrain-source-ownership.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(target, count)


if __name__ == '__main__':
    main()
