"""Freeze a conservative source-visible stone domain for the source-visible grass bank168."""
from pathlib import Path
import copy, hashlib, json, shutil
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[3]
work = root / 'level-editor/work/nottingham-refinement'
out = work / 'mask-review'
source = work / 'source-states/covered.png'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
parent = out / 'inventory-v11'
inventory_dir = out / 'inventory-v11-grass-bank'
if not inventory_dir.exists():
    shutil.copytree(parent, inventory_dir, ignore=shutil.ignore_patterns('manifest.json'))
inventory = json.loads((parent/'manifest.json').read_text())
manifest = json.loads((out/'source-masks-v11-baseline.json').read_text())
# Clear grass substrate only. This is an authored domain; source first-hit
# geometry clips it further to the actual bank, preserving neighboring surfaces.
polygon = [(1410,1174),(1446,1174),(1443,1186),(1437,1200),(1434,1213),(1422,1220),(1412,1218)]
mask = Image.new('L', (2304,3520))
ImageDraw.Draw(mask).polygon(polygon, fill=255)
image_path = inventory_dir/'authored-grass168-visible-ground.png'
mask.save(image_path)
box=(1380,1160,1466,1261)
preview=Image.open(source).convert('RGB').crop(box).resize((688,808))
draw=ImageDraw.Draw(preview)
points=[((x-box[0])*8,(y-box[1])*8)for x,y in polygon]
draw.line(points+[points[0]],fill='cyan',width=3)
evidence=out/'grass168-visible-ground-review.png'
preview.save(evidence)
index=max(r['index']for r in inventory['masks'])+1
inventory['masks'].append(dict(index=index,png=image_path.name,box_top_left=[0,0],box_size=[2304,3520],
    layer=None,layer_index=None,synthetic=True,constraint_kind='reviewed-authored-source-domain',
    source_sha256=sha(source),review_evidence=str(evidence.resolve()),polygon=polygon,
    scope='Conservative visible grass substrate168; tower, annex wall, foreground roof and bare path excluded. This is authored review evidence, not a native game mask.'))
manifest['mask_inventory']=str((inventory_dir/'manifest.json').resolve())
assignments=manifest['projections']['exterior']['assignments']
old=next(a for a in assignments if a['source_node']=='building-168')
new=dict(reviewed=True,source_node='building-168',mask_indices=[index],
    constraint_kind='reviewed-authored-source-domain',review_evidence=str(evidence.resolve()),
    review_note='Native material3 and measured source-camera self hits identify this low grass bank. No positive native mask covers it; this authored polygon accepts clear grass substrate and excludes adjacent tower, stone wall, roof and bare path. Source-camera first-hit visibility remains mandatory.')
assignments[assignments.index(old)]=new
manifest['limitations'].append('Grass-bank derivative changes only exterior receiver168. Native records and all other state labels remain unchanged; authored543 is conservative visible grass, not inferred hidden texture.')
def freeze(path,data):
    encoded=json.dumps(data,indent=2)+'\n'
    if path.exists() and path.read_text()!=encoded:
        raise RuntimeError('Refusing authority mutation: '+str(path))
    path.write_text(encoded)
# The initial directory copy from an interrupted first build may still hold
# the unchanged parent manifest; it has not become a frozen derivative yet.
manifest_path=inventory_dir/'manifest.json'
if manifest_path.exists() and manifest_path.read_bytes()==(parent/'manifest.json').read_bytes() and not (out/'source-masks-v11-grass-bank.json').exists():
    manifest_path.write_text(json.dumps(inventory,indent=2)+'\n')
freeze(manifest_path,inventory)
freeze(out/'source-masks-v11-grass-bank.json',manifest)
report=dict(version=1,parent_inventory_sha256=sha(parent/'manifest.json'),inventory_sha256=sha(inventory_dir/'manifest.json'),
    source_sha256=sha(source),evidence_sha256=sha(evidence),new_mask_index=index,
    native_records_unchanged=inventory['masks'][:527]==json.loads((parent/'manifest.json').read_text())['masks'][:527],
    assignment=new,polygon=polygon,accepted_source_pixels=sum(mask.histogram()[128:]),
    fresh_workspace_required=True,
    depth_evidence=str((work/'town-audit/grass168-first-hits.json').resolve()))
freeze(out/'grass168-visible-ground-validation.json',report)
print(json.dumps(report))
