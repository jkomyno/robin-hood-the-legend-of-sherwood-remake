"""Freeze a conservative source-visible stone domain for annex buttress050."""
from pathlib import Path
import copy, hashlib, json, shutil
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[3]
work = root / 'level-editor/work/nottingham-refinement'
out = work / 'mask-review'
source = work / 'source-states/covered.png'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
parent = out / 'inventory-v11'
inventory_dir = out / 'inventory-v11-annex-wall'
if not inventory_dir.exists():
    shutil.copytree(parent, inventory_dir, ignore=shutil.ignore_patterns('manifest.json'))
inventory = json.loads((parent/'manifest.json').read_text())
manifest = json.loads((out/'source-masks-v11-baseline.json').read_text())
# Stone only: the lower buttress is concealed by flowers, and the narrow dark
# gap on its left is not a stone surface. These pixels deliberately stay unknown.
polygon = [(2194,1897),(2203,1901),(2202,1927),(2189,1927),(2190,1906)]
mask = Image.new('L', (2304,3520))
ImageDraw.Draw(mask).polygon(polygon, fill=255)
image_path = inventory_dir/'authored-annex050-visible-stone.png'
mask.save(image_path)
box=(2170,1875,2225,1968)
preview=Image.open(source).convert('RGB').crop(box).resize((440,744))
draw=ImageDraw.Draw(preview)
points=[((x-box[0])*8,(y-box[1])*8)for x,y in polygon]
draw.line(points+[points[0]],fill='cyan',width=3)
evidence=out/'annex050-visible-stone-review.png'
preview.save(evidence)
index=max(r['index']for r in inventory['masks'])+1
inventory['masks'].append(dict(index=index,png=image_path.name,box_top_left=[0,0],box_size=[2304,3520],
    layer=None,layer_index=None,synthetic=True,constraint_kind='reviewed-authored-source-domain',
    source_sha256=sha(source),review_evidence=str(evidence.resolve()),polygon=polygon,
    scope='Conservative visible buttress stone050; foreground flowers and adjacent dark gap excluded. This is authored review evidence, not a native game mask.'))
manifest['mask_inventory']=str((inventory_dir/'manifest.json').resolve())
assignments=manifest['projections']['exterior']['assignments']
old=next(a for a in assignments if a['source_node']=='building-050')
new=dict(reviewed=True,source_node='building-050',mask_indices=[index],
    constraint_kind='reviewed-authored-source-domain',review_evidence=str(evidence.resolve()),
    review_note='Visible left buttress stone is absent from annex native46. Composite native42 contains it but also foreground flowers; conservative authored polygon accepts only clear stone and leaves covered lower wall unknown. Source-camera first-hit visibility remains mandatory.')
assignments[assignments.index(old)]=new
manifest['limitations'].append('Annex-wall derivative changes only exterior receiver050. Native records and all other state labels remain unchanged; authored543 is conservative visible stone, not inferred hidden texture.')
def freeze(path,data):
    encoded=json.dumps(data,indent=2)+'\n'
    if path.exists() and path.read_text()!=encoded:
        raise RuntimeError('Refusing authority mutation: '+str(path))
    path.write_text(encoded)
# The initial directory copy from an interrupted first build may still hold
# the unchanged parent manifest; it has not become a frozen derivative yet.
manifest_path=inventory_dir/'manifest.json'
if manifest_path.exists() and manifest_path.read_bytes()==(parent/'manifest.json').read_bytes() and not (out/'source-masks-v11-annex-wall.json').exists():
    manifest_path.write_text(json.dumps(inventory,indent=2)+'\n')
freeze(manifest_path,inventory)
freeze(out/'source-masks-v11-annex-wall.json',manifest)
report=dict(version=1,parent_inventory_sha256=sha(parent/'manifest.json'),inventory_sha256=sha(inventory_dir/'manifest.json'),
    source_sha256=sha(source),evidence_sha256=sha(evidence),new_mask_index=index,
    native_records_unchanged=inventory['masks'][:527]==json.loads((parent/'manifest.json').read_text())['masks'][:527],
    assignment=new,polygon=polygon,accepted_source_pixels=sum(mask.histogram()[128:]),
    fresh_workspace_required=True)
freeze(out/'annex050-visible-stone-validation.json',report)
print(json.dumps(report))
