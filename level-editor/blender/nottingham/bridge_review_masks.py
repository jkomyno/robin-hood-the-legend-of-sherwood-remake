"""Reject measured foreground vegetation from the bridge source projection."""
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
box = (1230, 3000, 1670, 3300)
image = Image.new('RGB', (880, 650), '#222222')
draw = ImageDraw.Draw(image)
for k, index in enumerate([197, 200, 199, 254]):
    record = records[index]
    mask = Image.new('L', im.size)
    mask.paste(Image.open(inventory.parent / record['png']).convert('L'), tuple(record['box_top_left']))
    accepted = np.array(mask.crop(box)) > 127
    pixels = np.array(im.crop(box))
    pixels[accepted] = (pixels[accepted] * .6 + [0, 80, 100]).clip(0, 255)
    x, y = k % 2 * 440, k // 2 * 325
    image.paste(Image.fromarray(pixels), (x, y + 25))
    draw.text((x + 4, y + 4), f'Excluded native{index}, layer{record["layer"]}/local{record["layer_index"]}', fill='white')
evidence = out / 'bridge-vegetation-exclusion-review.png'
image.save(evidence)
assignments = []
for node, component, indices in [(290, None, [202, 203]), (291, None, [202, 203]),
        (290, 'Two-arch bridge / arch masonry and deck', [202, 203, 528])]:
    a = dict(reviewed=True, source_node=f'building-{node:03}', mask_indices=indices,
             constraint_kind='reviewed-native-and-source-polygon' if component else 'reviewed-native-silhouette',
             review_evidence=evidence.name,
             review_note='Bridge front/rear masonry envelopes202/203 require exact receiver and first-hit visibility; component retains previously reviewed deck strip528.',
             exclude_mask_indices=[197, 199, 200, 254], exclusions_reviewed=True,
             exclusion_reason='Native197/200 isolate rear tree/reeds visible across the parapet;199 isolates front left-bank reeds;254 isolates front right-bank bush. These painted plants must not project onto bridge stone.')
    if component:
        a['projection_component'] = component
    assignments.append(a)
payload = dict(version=1, projection='exterior', assignments=assignments,
               source_sha256=sha(source), mask_inventory=str(inventory.resolve()),
               mask_inventory_sha256=sha(inventory), evidence_sha256={evidence.name: sha(evidence)},
               limitation='Working assignments only; inventory and source geometry remain unchanged. Excluded stone beneath vegetation is unknown and remains gray, not reconstructed from adjacent pixels.')
(out / 'bridge-vegetation-overrides-v6.json').write_text(json.dumps(payload, indent=2) + '\n')
print(out / 'bridge-vegetation-overrides-v6.json')
