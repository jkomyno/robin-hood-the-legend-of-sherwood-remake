"""Review the foreground cellar hatch independently of the house silhouette."""
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[3]
work = root / 'level-editor/work/nottingham-refinement'
out = work / 'mask-review'
source = work / 'source-states/covered.png'
inventory = out / 'inventory-v5/manifest.json'
records = {r['index']: r for r in json.loads(inventory.read_text())['masks']}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
im = Image.open(source).convert('RGB')
box = (1970, 1920, 2070, 2020)
image = Image.new('RGB', (800, 450), '#222222')
draw = ImageDraw.Draw(image)
for k, indices in enumerate([[42, 43], [45]]):
    accepted = np.zeros((im.height, im.width), dtype=bool)
    for index in indices:
        record = records[index]
        mask = Image.new('L', im.size)
        mask.paste(Image.open(inventory.parent / record['png']).convert('L'), tuple(record['box_top_left']))
        accepted |= np.array(mask) > 127
    pixels = np.array(im)
    pixels[accepted] = (pixels[accepted] * .6 + [0, 80, 100]).clip(0, 255)
    image.paste(Image.fromarray(pixels).crop(box).resize((400, 400)), (400 * k, 40))
    draw.text((400 * k + 4, 4), f'Native masks {indices}', fill='white')
evidence = out / 'green-front-mask-review.png'
image.save(evidence)
a = dict(reviewed=True, source_node='building-045', mask_indices=[45],
         constraint_kind='reviewed-native-silhouette', review_evidence=evidence.name,
         review_note='Front wooden cellar hatch independently isolated by native global45 (layer0/local37). House masks42/43 cut across its sloping top and exclude its front edge. Use only this receiver and source-camera first-hit visibility; approved geometry is unchanged.')
payload = dict(version=1, projection='exterior', assignments=[a],
               source_sha256=sha(source), mask_inventory=str(inventory.resolve()),
               mask_inventory_sha256=sha(inventory), evidence_sha256={evidence.name: sha(evidence)},
               limitation='Working assignment correction only. Frozen input, geometry, cameras, materials before reprojection and other source receivers must remain unchanged.')
(out / 'green-front-overrides-v5.json').write_text(json.dumps(payload, indent=2) + '\n')
print(out / 'green-front-overrides-v5.json')
