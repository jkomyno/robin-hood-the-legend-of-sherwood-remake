"""Freeze independently reviewed source-only walkway and masonry polygons."""
import hashlib,json,shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageChops
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';proof=WORK/'castle-audit/review4-texture';parent=WORK/'mask-review/inventory-v11';dest=WORK/'mask-review/inventory-review4-east-wall-v2';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
polygons=json.loads((proof/'east-wall-positive-polygons.json').read_text());assert polygons['source_sha256']==sha(WORK/'source-states/covered.png');inv=json.loads((parent/'manifest.json').read_text());records={m['index']:m for m in inv['masks']}
def native(i):
 m=records[i];out=Image.new('L',(2304,3520));out.paste(Image.open(parent/m['png']).convert('L'),tuple(m['box_top_left']));return out
positive=Image.new('L',(2304,3520))
for region in polygons['regions']:
 p=Image.new('L',positive.size);ImageDraw.Draw(p).polygon(region['points'],fill=255);p=ImageChops.darker(p,native(region['native_mask']))
 for i in region['exclude_native_masks']:p=ImageChops.subtract(p,native(i))
 positive=ImageChops.lighter(positive,p)
positive=ImageChops.subtract(ImageChops.lighter(ImageChops.lighter(positive,native(291)),native(300)),native(293))
if not dest.exists():shutil.copytree(parent,dest,ignore=shutil.ignore_patterns('manifest.json'))
index=max(records)+1;name='reviewed-east-wall-visible-masonry.png';positive.save(dest/name);inv['masks'].append(dict(index=index,png=name,box_top_left=[0,0],box_size=list(positive.size),layer=None,layer_index=None,synthetic=True,constraint_kind='reviewed-authored-source-domain',source_sha256=polygons['source_sha256'],review_evidence=str(proof/'east-wall-positive-polygons.png'),scope='Explicit positive masonry and walkway regions inside native292/296/298; shelter shingles, foreground greenhouse and tower293 excluded.'))
manifest=json.loads((WORK/'round-1/assets/nottingham-castle-east-courtyard-wall/source-masks.json').read_text());manifest['mask_inventory']=str(dest/'manifest.json')
for e in manifest['projections']['exterior']['assignments']:
 if e['source_node'] not in ['building-325','building-326']:continue
 node=e['source_node'];e.clear();e.update(source_node=node,reviewed=True,mask_indices=[index],constraint_kind='reviewed-authored-source-domain',review_evidence=str(proof/'east-wall-positive-polygons.png'),review_note='Native291/300 plus independently reviewed positive stone-only source domains, globally excluding tower293. Native292/296/298 clipped to observed masonry, excluding shelter shingles/greenhouse/tower. Full-scene source first-hit remains mandatory.')
def freeze(p,j):
 data=json.dumps(j,indent=2)+'\n'
 if p.exists() and p.read_text()!=data:raise ValueError('Authority already differs: '+str(p))
 p.write_text(data)
freeze(dest/'manifest.json',inv);freeze(proof/'castle-east-courtyard-wall-final-masks.json',manifest);freeze(proof/'east-wall-authored-mask-final-validation.json',dict(version=1,index=index,source_sha256=polygons['source_sha256'],polygons_sha256=sha(proof/'east-wall-positive-polygons.json'),mask_sha256=sha(dest/name),mask_inventory_sha256=sha(dest/'manifest.json'),positive_pixels=sum(positive.histogram()[128:]),native_records_unchanged=inv['masks'][:527]==json.loads((parent/'manifest.json').read_text())['masks'][:527],author='resume_forest',independent_reviewer='review4_castle_texture',review='Source/source-only image inspected: no shelter shingle or foreground greenhouse roof accepted; conservative2px uncertainty documented.'))
print(index,sum(positive.histogram()[128:]))
