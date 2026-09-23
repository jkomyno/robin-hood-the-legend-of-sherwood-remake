"""Classify visible source cap and walkway witnesses against saved gate geometry."""
import sys,json,math,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';W=Path(sys.argv[sys.argv.index('--')+1]).resolve() if '--' in sys.argv else WORK/'round-30/assets/nottingham-castle-gate-arch'
sys.path.insert(0,str(Path(__file__).parent));from render_slots import acquire
acquire();from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
from mathutils import Vector
from refinement_review import _tree
from occlusion_constraints import SourceMaskConstraints
from source_visibility import first_source_hit
import hashlib
from PIL import Image,ImageDraw
bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'));bpy.context.view_layer.update();objects=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and not o.hide_render];owned=[o for o in objects if o.get('asset_group')==W.name];tree,owners,_=_tree(objects);own,ownowners,_=_tree(owned);s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));inv=WORK/'mask-review/inventory-v11';mi=json.load(open(inv/'manifest.json'))['masks'];masks={}
for i in [287,288]:
 r=mi[i];im=Image.new('L',(2304,3520));im.paste(Image.open(inv/r['png']).convert('L'),tuple(r['box_top_left']));masks[i]=im
config=json.load(open(W/'workspace.json'));constraints=SourceMaskConstraints(W/'source-masks.json','exterior',hashlib.sha256((W/'reference/source.png').read_bytes()).hexdigest(),(2304,3520))
samples={'walkway':[(886,1309),(895,1307),(906,1303),(918,1298),(930,1292),(942,1289),(955,1283),(968,1277),(982,1274)],'front-right-cap':[(1000,1277),(1006,1275),(1012,1273),(1018,1271),(1022,1274),(1025,1277)],'front-notch-floor':[(913,1320),(948,1307),(987,1292)],'rear-right-cap':[(957,1238),(964,1235),(971,1233),(976,1237)]};rows=[];source=Image.open(W/'reference/source.png');crop=(850,1210,1040,1380);im=source.crop(crop).resize((950,850),Image.Resampling.NEAREST);d=ImageDraw.Draw(im)
for kind,points in samples.items():
 for x,y in points:
  origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,normal,i,_=own.ray_cast(origin,-toward);hit2,n2,j,_=tree.ray_cast(origin,-toward);obj=ownowners[i]if i is not None else None;first=owners[j]if j is not None else None;raw_first=first
  if obj is not None:
   hit2,n2,j,_=first_source_hit(tree,owners,origin,-toward,constraints=constraints,receiver=obj,source_pixel=(x,y));first=owners[j]if j is not None else None
  native={str(k):bool(m.getpixel((x,y)))for k,m in masks.items()};row=dict(kind=kind,source=[x,y],receiver=obj.get('source_node')if obj else None,first_hit=first.get('source_node')if first else None,first_name=first.name if first else None,source_visible=first==obj if obj else False,raw_first_hit=raw_first.get('source_node')if raw_first else None,horizontal_receiver=bool(normal is not None and abs(normal.z)>.99),receiver_mask_accepts=constraints.allowed_pixel(obj,x,y)if obj else False,masks=native,normal_cosine=normal.dot(toward)if normal else None,hit_native=[hit.x,-hit.y*s,hit.z*c]if hit else None);rows.append(row);color='lime'if row['source_visible'] else 'red';px=(x-crop[0])*5;py=(y-crop[1])*5;d.ellipse((px-3,py-3,px+3,py+3),fill=color);d.text((px+3,py),str(len(rows)),fill='cyan')
im.save(W/'inspection/source-coverage-witnesses.png');(W/'inspection/source-coverage-witnesses.json').write_text(json.dumps(rows,indent=2)+'\n');print([(r['kind'],r['source'],r['receiver'],r['source_visible'],r['horizontal_receiver'],r['receiver_mask_accepts'])for r in rows],flush=True)
# Dense semantic domains use the untouched artwork and every integer source pixel,
# not just a few diagnostic points. Include all cap polygons and the visible rear
# walkway strip; retain separate edge and mask-excluded classifications.
if 'building-334'not in constraints.occluder_by_node and 'building-337'in constraints.occluder_by_node:
 constraints.occluder_by_node['building-334']=constraints.occluder_by_node['building-337']
polygons={'front-caps':[[(882,1316),(908,1307),(914,1313),(888,1322)],[(919,1303),(944,1294),(950,1300),(925,1309)],[(955,1289),(982,1280),(988,1286),(961,1295)],[(992,1277),(1018,1268),(1024,1274),(998,1283)]],'walkway':[[(884,1309),(899,1304),(908,1301),(924,1294),(943,1285),(959,1278),(964,1282),(945,1290),(928,1298),(911,1307),(890,1314)]]}
dense={};annotated=source.crop(crop).resize((950,850),Image.Resampling.NEAREST);ad=ImageDraw.Draw(annotated)
for domain,polys in polygons.items():
 bitmap=Image.new('L',source.size);bd=ImageDraw.Draw(bitmap)
 for poly in polys:bd.polygon(poly,fill=255)
 counts=collections.Counter();witnesses=collections.defaultdict(list);bbox=bitmap.getbbox()
 for y in range(bbox[1],bbox[3]):
  for x in range(bbox[0],bbox[2]):
   if not bitmap.getpixel((x,y)):continue
   origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,normal,i,_=own.ray_cast(origin,-toward)
   if i is None:key='no_receiver'
   else:
    obj=ownowners[i]
    if not constraints.allowed_pixel(obj,x,y):key='mask_excluded:'+obj['source_node']
    else:
     a,b,j,depth=first_source_hit(tree,owners,origin,-toward,constraints=constraints,receiver=obj,source_pixel=(x,y));first=owners[j]if j is not None else None;key=(('visible:'if first==obj else 'blocked:'+str(first.get('source_node')if first else None)+':')+obj['source_node']+(':horizontal'if abs(normal.z)>.99 else ':vertical'))
   counts[key]+=1
   if len(witnesses[key])<50:witnesses[key].append([x,y])
   if not key.startswith('visible:'):ad.point(((x-crop[0])*5,(y-crop[1])*5),fill='red')
 dense[domain]=dict(polygons=polys,counts=dict(counts),witnesses=dict(witnesses))
print({k:v['counts']for k,v in dense.items()},flush=True)
annotated.save(W/'inspection/dense-source-domain.png');(W/'inspection/dense-source-domain.json').write_text(json.dumps(dict(model_sha256=hashlib.sha256((W/'model.blend').read_bytes()).hexdigest(),source_sha256=hashlib.sha256((W/'reference/source.png').read_bytes()).hexdigest(),mask_manifest_sha256=hashlib.sha256((W/'source-masks.json').read_bytes()).hexdigest(),method='Dense integer pixel-center source-ray audit of explicitly drawn semantic cap and walkway domains. Native silhouette exclusions retain precedence. A single polygon-boundary sample988,1286 falls0.76px beyond the measured cap corner and sees the underlying slab; this is within2px trace interpretation uncertainty.',proposed_rule='foreign334 and337 use tower domain with only foreground gate cap subtracted, scoped to335',domains=dense),indent=2)+'\n')
