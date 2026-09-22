"""Build scoped hall ownership revisions without changing frozen mask authority."""
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
OUT = WORK / 'mask-review'
INVENTORY = OUT / 'inventory-v11/manifest.json'
records = {r['index']: r for r in json.loads(INVENTORY.read_text())['masks']}
covered = WORK / 'source-states/covered.png'
revealed = WORK / 'state-review/owned-masks/revealed-with-open-doors-and-initial-mechanisms.png'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def mask(index, size):
    r = records[index]
    canvas = Image.new('L', size)
    canvas.paste(Image.open(INVENTORY.parent / r['png']).convert('L'), tuple(r['box_top_left']))
    return np.array(canvas) > 127

# Foreground tower, separate spires and chimney are explicitly excluded even
# where coarse receiver geometry might incorrectly become the first hit.
foreground = [440, 441, 442, 443, 444, 445, 451]
assignments = []
def add(node, component, indices, exclusions, note, label='exterior'):
    a = dict(reviewed=True, source_node=f'building-{node:03}',
             projection_component=component, mask_indices=indices,
             constraint_kind='reviewed-native-silhouette',
             review_evidence='hall-component-ownership-review.png', review_note=note)
    if exclusions:
        a.update(exclude_mask_indices=exclusions, exclusions_reviewed=True,
                 exclusion_reason='Separate foreground towers, spires and chimney are not hall receiver pixels.')
    assignments.append((label, a))

for node in [505, 506]:
    for component in ['castle-hall-retained-roof', 'castle-hall-removable-cover']:
        add(node, component, [453], foreground,
            'Covered roof silhouette is reviewed at layer8/local5 (global453). Only this named roof component and source-camera first-hit surface may receive it; the envelope also contains facade pixels and is not independent ownership.')
    add(node, 'castle-hall-retained-roof', [460], [442, 444, 445, 451],
        'Revealed layer6/local11 (global460) isolates the retained tiled roof rim. Source-camera first-hit component intersection is mandatory.', 'interior-patch-008')
for node in [507, 527, 528]:
    add(node, 'castle-hall-removable-cover', [453], foreground,
        'Covered upper hall roof envelope; restricted to the measured roof component and source-camera first-hit surface.')
for node in [502, 531, 532]:
    for component in ['castle-hall-retained-wall', 'castle-hall-removable-cover']:
        add(node, component, [449], foreground,
            'Covered full hall silhouette layer0/local337 (global449), minus separate foreground structures. Only the measured wall component may receive it; hidden/rear faces stay rejected by first-hit visibility.')
# Ceiling is hidden under the roof and must not borrow an unrelated roof image.
# Floor remains governed by the existing authored footprint531 in the state sidecar.
projections = {label: [a for l, a in assignments if l == label]
               for label in ['exterior', 'interior-patch-008']}
image = Image.new('RGB', (1440, 900), '#242424')
draw = ImageDraw.Draw(image)
box = (210, 170, 780, 1310)
rows = [('exterior', 453, foreground), ('exterior', 449, foreground),
        ('interior-patch-008', 460, [442, 444, 445, 451])]
counts = []
for k, (label, index, excluded) in enumerate(rows):
    source = Image.open(covered if label == 'exterior' else revealed).convert('RGB')
    accepted = mask(index, source.size)
    for other in excluded:
        accepted &= ~mask(other, source.size)
    a = np.array(source)
    a[accepted] = (a[accepted] * .62 + np.array([0, 170, 210]) * .38).astype('uint8')
    thumb = Image.fromarray(a).crop(box)
    thumb.thumbnail((430, 850))
    image.paste(thumb, (k * 480, 45))
    draw.text((k * 480 + 5, 8), f'{label}: native{index}, scoped/excluded', fill='white')
    counts.append(dict(projection=label, mask=index, eligible_pixels=int(accepted.sum())))
path = OUT / 'hall-component-ownership-review.png'
image.save(path)
payload = dict(version=1, baseline='source-masks-v11-baseline.json',
               mask_inventory='inventory-v11/manifest.json', mask_inventory_sha256=sha(INVENTORY),
               apply_only_owned_assignments_after_geometry_recipe=True,
               source_sha256={'exterior': sha(covered), 'interior-patch-008': sha(revealed)},
               projections=projections, evidence_sha256={path.name: sha(path)},
               eligible_envelope_pixels=counts,
               limitation='Envelopes require exact named receiver and first-hit visibility; they do not authorize back faces, missing geometry or another source state. Ceiling530, shaft378 and other unreviewed canonical receivers stay unchanged. Existing floor530 and furniture assignments remain in force.')
(OUT / 'hall-overrides-v11.json').write_text(json.dumps(payload, indent=2) + '\n')
print(json.dumps({'output': str(OUT / 'hall-overrides-v11.json'), 'assignments': len(assignments), 'counts': counts}))
