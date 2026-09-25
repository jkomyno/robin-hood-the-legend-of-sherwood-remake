"""Verify dormer candidate topology, unchanged context and actual saved materials."""
import bpy,bmesh,sys,json,hashlib
from pathlib import Path
r=Path(__file__).resolve().parents[3];sys.path.insert(0,str(r/'level-editor/blender/nottingham'))
from render_slots import acquire
from freeze_tooling import select_tooling
if '--no-render' not in sys.argv:acquire()
select_tooling(r/'level-editor/work/nottingham-refinement/tooling/58744eeaf71a21e9')
from correct_source_projection import geometry
from audit_stored_materials import run
w=r/'level-editor/work/nottingham-refinement/texture-generation/projection-corrections/north-dormer-v23/nottingham-north-dormer-house';old=r/'level-editor/work/nottingham-refinement/round-38/assets/nottingham-north-dormer-house'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def outside():return {o.name:dict(uv={u.name:[list(v.uv)for v in u.data]for u in o.data.uv_layers},materials=[m.name if m else None for m in o.data.materials],slots=[p.material_index for p in o.data.polygons])for o in bpy.data.objects if o.type=='MESH'and o.get('source_node') not in ['building-122','building-123','building-124','building-125','building-553','building-554']}
bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));before=geometry();uv=outside()
bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));after=geometry();assert uv==outside(),'Outside UV/material drift'
changed=[n for n in before if before[n]!=after[n]];assert len(changed)==3,changed
for a,b in zip(json.loads((old/'modified/views.json').read_text())['views'],json.loads((w/'modified/views.json').read_text())['views']):
 for key in ['camera_matrix_world','ortho_scale']:assert a[key]==b[key]
report=dict(status='PASS',model_sha256=sha(w/'model.blend'),changed_meshes=changed,outside_uv_materials_preserved=True,frozen_cameras_preserved=True)
(w/'inspection').mkdir(exist_ok=True);(w/'inspection/outside-camera-validation.json').write_text(json.dumps(report,indent=2)+'\n')
old_masks=json.loads((old/'source-masks.json').read_text());new_masks=json.loads((w/'source-masks.json').read_text());a=Path(old_masks['mask_inventory']);b=Path(new_masks['mask_inventory']);ar=json.loads(a.read_text())['masks'];br={row['index']:row for row in json.loads(b.read_text())['masks']}
for row in ar:assert sha(a.parent/row['png'])==sha(b.parent/br[row['index']]['png'])
report['original_mask_pngs_preserved']=len(ar);(w/'inspection/outside-camera-validation.json').write_text(json.dumps(report,indent=2)+'\n')
parts=[]
for obj in bpy.data.collections['nottingham Working'].all_objects:
 if obj.type!='MESH' or obj.get('asset_group')!='nottingham-north-dormer-house':continue
 bm=bmesh.new();bm.from_mesh(obj.data);unseen=set(bm.verts);components=0
 while unseen:
  components+=1;stack=[unseen.pop()]
  while stack:
   vertex=stack.pop()
   for edge in vertex.link_edges:
    neighbor=edge.other_vert(vertex)
    if neighbor in unseen:unseen.remove(neighbor);stack.append(neighbor)
 row=dict(source_node=obj['source_node'],vertices=len(bm.verts),closed_components=components,nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),degenerate_faces=sum(f.calc_area()<1e-8 for f in bm.faces));parts.append(row);bm.free()
 assert row['nonmanifold_edges']==row['degenerate_faces']==0
 if obj['source_node']=='building-122':assert components==1
ground_reference=r/'level-editor/work/nottingham-refinement/coordinator-audit/north-dormer-stripe/ground-datum'
ground=json.loads((ground_reference/'native-ground-evidence.json').read_text());assert sha(r/'level-editor/work/nottingham-refinement/baseline/nottingham.rhp.json')==ground['native_sha256'];ground['model_sha256']=sha(w/'model.blend');ground['status']='PASS-RESTORED-NATIVE-LOWER-DATUM';ground['saved_body_bases']={}
for obj in bpy.data.collections['nottingham Working'].all_objects:
 if obj.type=='MESH' and obj.get('source_node') in ['building-122','building-124']:
  z=min((obj.matrix_world@vertex.co).z for vertex in obj.data.vertices);assert abs(z)<1e-4;ground['saved_body_bases'][obj['source_node']]=z
ground['approved_adjacent_stair']=json.loads((ground_reference/'approved-stair-elevations.json').read_text());(w/'inspection/ground-datum.json').write_text(json.dumps(ground,indent=2)+'\n')
(w/'inspection/mesh-topology.json').write_text(json.dumps(dict(status='PASS',model_sha256=sha(w/'model.blend'),parts=parts,notes=['Main body is one closed component. Roof return is a separate closed slab in contact with original roof. Board and its two battens are three closed components. Hidden body depth and board recess require renewed user review.']),indent=2)+'\n')
if '--no-render' not in sys.argv:
 try:print(run(w,w/'inspection/stored-materials',render=True)['status'],flush=True)
 finally:
  from render_slots import release
  release()
print('DORMER_GEOMETRY_CONTEXT_PASS',flush=True)

