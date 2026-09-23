"""Move the refined gateway jamb volumes to their canonical pier receivers."""
import sys,json,hashlib,copy,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';ASSET='nottingham-castle-gate-arch'
sys.path.insert(0,str(Path(__file__).parent))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,bmesh
 from mathutils import Vector
 from refine_church import neutral,COS,fingerprint
 from refinement_workspace import prepare,modified
 src=WORK/'round-23/assets'/ASSET;out=WORK/'round-24/assets'/ASSET
 bpy.ops.wm.open_mainfile(filepath=str(src/'model.blend'));bpy.context.view_layer.update();records=[]
 for o in bpy.data.collections['nottingham Working'].all_objects:
  if o.type!='MESH' or o.get('asset_group')!=ASSET:continue
  records.append({'node':o['source_node'],'component':o.get('projection_component',''),'vertices':[list(o.matrix_world@v.co) for v in o.data.vertices],'faces':[list(p.vertices) for p in o.data.polygons],'uv':{u.name:[list(v.uv) for v in u.data] for u in o.data.uv_layers},'properties':{k:(o[k].to_list() if hasattr(o[k],'to_list') else o[k]) for k in o.keys()},'hide_render':o.hide_render})
 bpy.ops.wm.open_mainfile(filepath=str(WORK/'grouped/nottingham-grouped-v13.blend'));bpy.context.view_layer.update()
 coll=bpy.data.collections['nottingham Working'];targets=[o for o in coll.all_objects if o.type=='MESH' and o.get('asset_group')==ASSET]
 def identity(o):return(o.get('source_node'),o.get('projection_component',''))
 targetmap={identity(o):o for o in targets}
 if not {'building-349','building-350'}<=set(o.get('source_node') for o in targets):raise ValueError('V13 pier ownership absent')
 for rec in records:
  identity_key=(rec['node'],rec['component'])
  if identity_key not in targetmap:
   # Animation state receivers are part of the arch and share canonical333.
   if not rec['properties'].get('animation_state'):
    matches=[o for o in targets if o['source_node']==rec['node'] and not o.get('animation_state')]
    if len(matches)!=1:raise ValueError(('Missing receiver',identity_key))
    targetmap[identity_key]=matches[0]
    o=matches[0]
   else:
    template=next(o for o in targets if o['source_node']=='building-333');o=template.copy();o.data=template.data.copy();o.name=rec['node']+' / '+rec['component'];coll.objects.link(o);targets.append(o);targetmap[identity_key]=o
  o=targetmap[identity_key];inv=o.matrix_world.inverted();mesh=bpy.data.meshes.new(o.name+' / preserved profile');mesh.from_pydata([inv@Vector(v) for v in rec['vertices']],[],rec['faces']);mesh.materials.append(neutral());mesh.update()
  for name,uvs in rec['uv'].items():
   uv=mesh.uv_layers.new(name=name)
   for a,b in zip(uv.data,uvs):a.uv=b
  o.data=mesh
  for key,value in rec['properties'].items():o[key]=value
  o.hide_render=rec['hide_render'];o.hide_set(rec['hide_render'])
 for o in targets:
  if o['source_node'] in {'building-349','building-350'}:o.hide_render=True;o.hide_set(True)
 # Supply missing neutral display fallback before freezing the disposable scene.
 for o in coll.all_objects:
  if o.type=='MESH':
   if not o.data.materials:o.data.materials.append(neutral())
   if not o.data.uv_layers:o.data.uv_layers.new(name='NeutralFallbackUV')
 # Freeze a fresh V13 input with the old gate and its now-owned piers.
 evidence=WORK/'grouped/nottingham-grouped-v13.evidence'
 prepare(out,asset_id=ASSET,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=src/'reference/source.png',grouping_manifest=evidence/'catalog.json',inventory_path=evidence/'inventory.json',review_path=evidence/'grouping-review.json',projection_manifest=src/'projection-layers.json',source_mask_manifest=src/'source-masks.json',width=320,height=400,context_padding=35,framing_padding=1.18)
 outside={o.name:fingerprint(o) for o in coll.all_objects if o.type=='MESH' and o not in targets}
 body=next(o for o in targets if o['source_node']=='building-333' and not o.get('animation_state'))
 body.data.calc_loop_triangles()
 original=bpy.data.meshes.new('Evaluated gateway triangle surface')
 original.from_pydata([list(v.co) for v in body.data.vertices],[],[list(t.vertices) for t in body.data.loop_triangles])
 original.update()
 def cut(target,positive_z,side=None):
  bm=bmesh.new();bm.from_mesh(original)
  # Work directly in world coordinates and transform back only after capping.
  for v in bm.verts:v.co=body.matrix_world@v.co
  bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=(0,0,205.834/COS),plane_no=(0,0,1),dist=1e-5,clear_inner=positive_z,clear_outer=not positive_z)
  if side:
   bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=(945,0,0),plane_no=(1,0,0),dist=1e-5,clear_inner=side=='right',clear_outer=side=='left')
  boundary=[e for e in bm.edges if e.is_boundary]
  bmesh.ops.holes_fill(bm,edges=boundary)
  bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
  inv=target.matrix_world.inverted()
  for v in bm.verts:v.co=inv@v.co
  mesh=bpy.data.meshes.new(target.name+' / canonical gateway partition');bm.to_mesh(mesh);bm.free();mesh.materials.append(neutral());target.data=mesh;mesh.uv_layers.new(name='UnprojectedSurfaceUV')
  fallback=mesh.attributes.get('reprojection_fallback_material')
  if fallback:mesh.attributes.remove(fallback)
  for face in mesh.polygons:face.material_index=0
  target['castle_arch_partition']='native-z205.834; left/right at x945';target.hide_render=False;target.hide_set(False)
 right=next(o for o in targets if o['source_node']=='building-349');left=next(o for o in targets if o['source_node']=='building-350')
 cut(body,True);cut(right,False,'right');cut(left,False,'left')
 # Cut faces have no independent source evidence; native masks plus source
 # orientation/first-hit tests prevent newly concealed caps from borrowing RGB.
 mask_path=out/'source-masks.json';m=json.loads(mask_path.read_text());rows=m['projections']['exterior']['assignments'];arch=next(a for a in rows if a['source_node']=='building-333' and not a.get('projection_component'))
 for node in ['building-349','building-350']:
  assignment=copy.deepcopy(arch);assignment['source_node']=node;assignment['review_note']='Canonical gate jamb partition, source traced from gateway masonry. Native288 and first-hit geometry constrain ownership; no duplicate full-height arch volume remains.'
  matches=[i for i,a in enumerate(rows) if a['source_node']==node and not a.get('projection_component')]
  if len(matches)!=1:raise ValueError(('Ambiguous pier mask',node,matches))
  rows[matches[0]]=assignment
 mask_path.write_text(json.dumps(m,indent=2)+'\n')
 topology={}
 for o in targets:
  bm=bmesh.new();bm.from_mesh(o.data);topology[o.name]={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)};bm.free()
 if any(any(r.values()) for r in topology.values()):raise ValueError(topology)
 drift=[name for name,h in outside.items() if fingerprint(bpy.data.objects[name])!=h]
 if drift:raise ValueError(('Outside geometry changed',drift))
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));validation=modified(out)
 (out/'pier-partition-report.json').write_text(json.dumps({'status':'PASS','source_model_sha256':sha(src/'model.blend'),'model_sha256':sha(out/'model.blend'),'partition':'333 upper gateway;349 right jamb;350 left jamb. Closed at nativez205.834.','topology':topology,'outside_preserved':len(outside),'tooling':tooling,'validation':validation},indent=2)+'\n')
 print('GATE_PARTITION_COMPLETE',flush=True)
if __name__=='__main__':main()
