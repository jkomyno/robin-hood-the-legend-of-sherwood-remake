"""Check church covered/revealed packets and source-preserved pixels independently."""
from pathlib import Path
import sys
# Reuse the independently implemented ray/RGB checker, extending its input set
# to the paired display states without changing the underlying pixel checks.
source=Path(__file__).with_name('verify_workspace_known_rgb.py').read_text()
assert source.count("packets=[w/'modified']")==1, "Shared verifier packet contract changed"
source=source.replace("packets=[w/'modified']", "packets=[w/'modified',w/'inspection/final-states/patch-000/covered',w/'inspection/final-states/patch-000/revealed']")
exec(compile(source,str(Path(__file__).with_name('verify_workspace_known_rgb.py')),'exec'))

import bpy,bmesh,json,hashlib,math
from PIL import Image,ImageDraw
w=Path(sys.argv[sys.argv.index('--')+1]).resolve()
work=w.parents[2]
config=json.loads((w/'workspace.json').read_text())
owned=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
defects={}
for obj in owned:
 bm=bmesh.new();bm.from_mesh(obj.data)
 defects[obj.name]={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
 bm.free()
assert not any(any(d.values()) for d in defects.values()),defects
out=w/'inspection/review4-source';out.mkdir(exist_ok=True)
source=work/'source-states/revealed.png'
im=Image.open(source).convert('RGB');draw=ImageDraw.Draw(im)
sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35))
for obj in owned:
 if obj.get('source_node') not in ['building-393','building-394','building-395','building-396','building-414'] or obj.get('projection_component')!='church-retained':continue
 for edge in obj.data.edges:
  a,b=[obj.matrix_world@obj.data.vertices[i].co for i in edge.vertices]
  draw.line([(a.x,-a.y*sine-a.z*cosine),(b.x,-b.y*sine-b.z*cosine)],fill=(255,70,50),width=1)
box=(1830,850,2270,1210)
im.crop(box).resize((880,720)).save(out/'actual-retained-wall-edges.png')
Image.open(source).crop(box).resize((880,720)).save(out/'revealed-source.png')
covered=Image.open(work/'source-states/covered.png').convert('RGB');covered.crop((1800,550,2040,790)).resize((720,720)).save(out/'annex-source.png')
inventory=work/'mask-review/inventory-v11';record=json.loads((inventory/'manifest.json').read_text())['masks'][323]
mask=Image.new('L',covered.size);mask.paste(Image.open(inventory/record['png']),record['box_top_left']);covered.putalpha(mask);covered.crop((1800,550,2040,790)).resize((720,720)).save(out/'annex-native323.png')
report={'status':'PASS','model_sha256':hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),'defects':defects,'source_provenance':{'covered_sha256':hashlib.sha256((work/'source-states/covered.png').read_bytes()).hexdigest(),'revealed_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'native323_png_sha256':hashlib.sha256((inventory/record['png']).read_bytes()).hexdigest(),'native323_record':record},'rim_evidence':'Actual saved retained-mesh edges over unchanged revealed source.28-unit front rims follow the painted masonry cap; source artwork has irregular pixel-scale edges.'}
(w/'church-review4-validation.json').write_text(json.dumps(report,indent=2)+'\n')
