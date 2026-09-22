"""Freeze reviewed grass/earth ownership for the woodland-bank receiver.

The source-facing footprint is measured from the existing exported geometry.
Its visible ground was independently inspected against the original artwork;
foreground native foliage masks are removed, including their exact pixel holes.
"""
import json
import hashlib
from pathlib import Path
import sys
from PIL import Image, ImageChops

root=Path(sys.argv[1]).resolve();workspace=root/'round-1/assets-v2/leicester-southwest-woodland-bank';output=root/'mask-audit/woodland-bank-v9'
output.mkdir(parents=True,exist_ok=False)
manifest=json.loads((workspace/'source-masks.json').read_text());parent=Path(manifest['mask_inventory']);inventory=json.loads(parent.read_text());records={m['index']:m for m in inventory['masks']}
for m in inventory['masks']:m['png']=str((parent.parent/m['png']).resolve())
mask=Image.open(workspace/'inspection/texture-coverage-diagnosis/source-facing-footprint.png').convert('L')
for index in [14,32,33,69]:
    m=records[index];foreground=Image.new('L',mask.size);foreground.paste(Image.open(m['png']).convert('L'),m['box_top_left']);mask=ImageChops.subtract(mask,foreground)
box=mask.getbbox();cropped=mask.crop(box);cropped.save(output/'300383.png')
inventory['masks'].append({'index':300383,'box_top_left':list(box[:2]),'box_size':[box[2]-box[0],box[3]-box[1]],'png':str(output/'300383.png'),'reason':'Visually reviewed exposed grass, earth and rock inside the source-facing woodland-bank footprint, excluding native14/32/33/69 foreground foliage.','source_sha256':hashlib.sha256((workspace/'reference/source.png').read_bytes()).hexdigest(),'evidence':'Archived inspection/texture-coverage-diagnosis/source-context.png and ownership-gap-overlay.png; exact projected triangles in coverage.json.','limitations':['Footprint depth remains the inherited terrain hypothesis.','No background outside the measured bank surface is authorized.','Foreground vegetation remains unknown on the bank; reverse faces receive no source pixels.']})
(output/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n');manifest['mask_inventory']=str(output/'inventory.json')
for a in manifest['projections']['exterior']['assignments']:
    if a.get('source_node')=='building-383':
        a.update(mask_indices=[300383],exclude_mask_indices=[14,32,33,69],evidence='Source-facing footprint rasterized from saved geometry and visually compared to original source: clear grass/earth was omitted by the former rock-only462/463 assignment.',exclusion_reason='Foreground native14/32/33 trees and69 shrub remain excluded; derived mask already removes their pixels.')
(output/'source-masks.json').write_text(json.dumps(manifest,indent=2)+'\n')
(output/'review.json').write_text(json.dumps({'status':'reviewed','reviewer':'props worker','native_foreground_exclusions':[14,32,33,69],'previous_assignment':[462,463],'source_pixel_counts':json.loads((workspace/'inspection/texture-coverage-diagnosis/coverage.json').read_text()),'source_model_sha256':hashlib.sha256((workspace/'model.blend').read_bytes()).hexdigest()},indent=2)+'\n')
