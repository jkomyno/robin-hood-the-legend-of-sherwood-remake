"""Audit every source pixel on original and inferred portcullis surfaces."""
import sys,json,hashlib,math,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';ASSET='nottingham-castle-gate-arch'
def main():
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from mathutils import Vector
 from mathutils.bvhtree import BVHTree
 from PIL import Image,ImageDraw
 from refinement_review import _tree
 round_name=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'round-38'
 w=WORK/round_name/'assets'/ASSET
 tower=WORK/'round-23/assets/nottingham-castle-gate-east-tower/model.blend'
 bpy.ops.wm.open_mainfile(filepath=str(tower));names=[o.name for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')=='nottingham-castle-gate-east-tower' and not o.hide_render]
 bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'))
 bpy.context.view_layer.update()
 for o in list(bpy.data.collections['nottingham Working'].all_objects):
  if o.get('asset_group')=='nottingham-castle-gate-east-tower':o.hide_render=True
 with bpy.data.libraries.load(str(tower),link=False) as (a,b):b.objects=names
 for o in b.objects:
  world=o.matrix_world.copy();o.parent=None;o.matrix_world=world;bpy.data.collections['nottingham Working'].objects.link(o);o.hide_render=False;o.hide_set(False)
 bpy.context.view_layer.update()
 report=json.loads((w/'gate-center-report.json').read_text());ext={r['object']:r for r in report['extensions']}
 objs=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==ASSET]
 layers=json.loads((WORK/'source-states/layers.json').read_text())['patches'][3]
 s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));records=[]
 for state in ['initial','applied']:
  vertices=[];triangles=[];owners=[];inferred=[]
  for o in objs:
   if o.get('animation_state') and o['animation_state']!=state:continue
   o.data.calc_loop_triangles();offset=len(vertices);vertices.extend(o.matrix_world@v.co for v in o.data.vertices)
   for t in o.data.loop_triangles:
    triangles.append(tuple(offset+i for i in t.vertices));owners.append(o.name);inferred.append(o.name in ext and t.polygon_index>=ext[o.name]['original_faces'])
  tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True)
  scene_objects=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and (not o.hide_render or o.get('animation_state')==state and o.get('asset_group')==ASSET) and not (o.get('asset_group')==ASSET and o.get('animation_state') and o['animation_state']!=state)]
  scene_tree,scene_owners,_=_tree(scene_objects);scene_counts=collections.Counter()
  brown_counts=collections.Counter();brown_owned=collections.Counter();brown_witnesses=[]
  brown_poly=[(966,1414),(980,1427),(981,1488),(966,1477)]
  brown=Image.new('L',(2304,3520));ImageDraw.Draw(brown).polygon(brown_poly,fill=255)
  for by in range(1414,1489):
   for bx in range(966,982):
    if not brown.getpixel((bx,by)):continue
    origin=Vector((bx+.5,-(by+.5)*s,-(by+.5)*c))+toward*10000
    hit,normal,j,d=scene_tree.ray_cast(origin,-toward);obj=scene_owners[j] if j is not None else None
    own_hit,_,oi,_=tree.ray_cast(origin,-toward);brown_owned[owners[oi] if oi is not None else 'none']+=1
    key=(obj.get('source_node','unknown')+':'+str(obj.get('projection_component',''))) if obj else 'none';brown_counts[key]+=1
    if len(brown_witnesses)<10:brown_witnesses.append(dict(pixel=[bx,by],first=key,object=obj.name if obj else None,native_hit=[hit.x,-hit.y*s,hit.z*c] if hit else None))
  frame=layers[state+'_graphic'];sprite=Image.open(WORK/'source-states'/frame['image']).convert('RGBA');left,top=frame['bbox'][:2]
  crop=(875,1310,1000,1520);source=Image.open(w/'reference/source.png');im=source.crop(crop).resize((625,1050),Image.Resampling.NEAREST);draw=ImageDraw.Draw(im);counts=collections.Counter();witnesses=collections.defaultdict(list)
  for y in range(crop[1],crop[3]):
   for x in range(crop[0],crop[2]):
    origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,n,i,d=tree.ray_cast(origin,-toward)
    opaque=0<=x-left<sprite.width and 0<=y-top<sprite.height and sprite.getpixel((x-left,y-top))[3]>127
    if i is not None and inferred[i]:
     key='inferred-visible'
     _,_,j,_=scene_tree.ray_cast(origin,-toward)
     scene_counts[scene_owners[j].get('source_node','unknown') if j is not None else 'none']+=1
    elif opaque:key='sprite-visible' if i is not None and owners[i] in ext else 'sprite-blocked'
    else:continue
    counts[key]+=1
    if len(witnesses[key])<300:witnesses[key].append([x,y,owners[i] if i is not None else None])
    color={'inferred-visible':'red','sprite-visible':'lime','sprite-blocked':'orange'}[key];draw.rectangle(((x-crop[0])*5,(y-crop[1])*5,(x-crop[0])*5+3,(y-crop[1])*5+3),fill=color)
  im.save(w/f'inspection/gate-source-{state}.png');records.append(dict(state=state,counts=dict(counts),inferred_scene_first_hits=dict(scene_counts),brown_domain=dict(polygon=brown_poly,counts=dict(brown_counts),gateway_only_counts=dict(brown_owned),witnesses=brown_witnesses),witnesses=dict(witnesses)))
 result=dict(model_sha256=hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),tower_model_sha256=hashlib.sha256(tower.read_bytes()).hexdigest(),states=records,method='Strict first geometric hit within complete gateway; paired scene substitutes approved easttower23. All source sprite pixels and all projected added surfaces tested. Red added surfaces must be hidden before acceptance.')
 (w/'inspection/gate-source-audit.json').write_text(json.dumps(result,indent=2)+'\n');print([{k:v for k,v in r.items()if k!='witnesses'} for r in records],flush=True)
if __name__=='__main__':main()
