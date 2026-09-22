"""Review independent foreground props clipped by their parent house masks."""
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[3]
work = root / 'level-editor/work/nottingham-refinement'
out = work / 'mask-review'
source = work / 'source-states/covered.png'
inventory = out / 'inventory-v6/manifest.json'
records = {r['index']: r for r in json.loads(inventory.read_text())['masks']}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
im = Image.open(source).convert('RGB')
image = Image.new('RGB', (1000, 800), '#222222')
draw = ImageDraw.Draw(image)
assignments = []
measurements = []
for row, (node, old_indices, new_index) in enumerate([(5, [4, 7], 8), (42, [37, 38, 40], 41)]):
    r = records[new_index]
    x, y = r['box_top_left']; w, h = r['box_size']
    box = (x-20, y-15, x+w+20, y+h+15)
    masks = []
    for col, indices in enumerate([old_indices, [new_index]]):
        accepted = np.zeros((box[3]-box[1], box[2]-box[0]), dtype=bool)
        for index in indices:
            record = records[index]
            mask = Image.new('L', (box[2]-box[0], box[3]-box[1]))
            mask.paste(Image.open(inventory.parent / record['png']).convert('L'),
                       (record['box_top_left'][0]-box[0], record['box_top_left'][1]-box[1]))
            accepted |= np.array(mask) > 127
        masks.append(accepted)
        pixels = np.array(im.crop(box))
        pixels[accepted] = (pixels[accepted] * .6 + [0, 80, 100]).clip(0, 255)
        crop = Image.fromarray(pixels); crop.thumbnail((450, 360)); crop = crop.resize((crop.width*4, crop.height*4))
        crop.thumbnail((450, 350))
        image.paste(crop, (col*500+20, row*400+40))
        draw.text((col*500+5, row*400+8), f'Node{node:03} {"before" if col==0 else "reviewed"}: native{indices}', fill='white')
    measurements.append(dict(source_node=f'building-{node:03}', native_opaque_pixels=int(masks[1].sum()),
                             previously_rejected_native_pixels=int((masks[1] & ~masks[0]).sum())))
    assignments.append(dict(reviewed=True, source_node=f'building-{node:03}', mask_indices=[new_index],
        constraint_kind='reviewed-native-silhouette', review_evidence='town-front-barrels-review.png',
        review_note=f'Independent foreground barrel is isolated by native{new_index} (layer{r["layer"]}/local{r["layer_index"]}). Parent-house mask lower boundary clips this barrel; exact receiver and first-hit visibility remain required. Geometry unchanged.'))
evidence = out / 'town-front-barrels-review.png'
image.save(evidence)
payload = dict(version=1, projection='exterior', assignments=assignments,
    source_sha256=sha(source), mask_inventory=str(inventory.resolve()), mask_inventory_sha256=sha(inventory),
    evidence_sha256={evidence.name: sha(evidence)}, measurements=measurements,
    apply_only_owned_assignments_after_geometry_recipe=True,
    limitation='Apply only to the matching asset working manifest. Shared terrace base012 correctly excludes barrel8: do not remove that exclusion. No geometry, frozen input or other assignments change.')
(out / 'town-front-barrel-overrides-v6.json').write_text(json.dumps(payload, indent=2)+'\n')
print(json.dumps(measurements))
