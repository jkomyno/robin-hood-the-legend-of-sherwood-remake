"""Align the concealed gateway tunnel with the native pier depth axis."""
import sys,json,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
ASSET='nottingham-castle-gate-arch'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,bmesh
 from mathutils import Vector
 from refine_church import SIN,COS,fingerprint,neutral
 from refinement_workspace import prepare,modified
 src=WORK/'round-30/assets'/ASSET;out=WORK/('round-39' if '--exact-sprite' in sys.argv else 'round-38')/'assets'/ASSET
 c=json.loads((src/'workspace.json').read_text())
 bpy.ops.wm.open_mainfile(filepath=str(src/'model.blend'))
 if not out.exists():prepare(out,asset_id=ASSET,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=src/'reference/source.png',grouping_manifest=src/'reference/grouping.json',inventory_path=src/'reference/inventory.json',review_path=src/'reference/grouping-review.json',projection_manifest=src/'projection-layers.json',source_mask_manifest=src/'source-masks.json',width=320,height=400,context_padding=35,framing_padding=1.18)
 coll=bpy.data.collections[c['collection_name']]
 objs=[o for o in coll.all_objects if o.type=='MESH' and o.get('asset_group')==ASSET]
 before={o.name:fingerprint(o) for o in coll.all_objects if o.type=='MESH'}
 ratio=35.94214/31.6296;offset=11/(1/ratio+.348)
 records=[]
 for o in objs:
  if o.get('animation_state') or o['source_node'] not in ['building-333','building-349','building-350']:continue
  inv=o.matrix_world.inverted();n=len(o.data.vertices)
  # The final eight vertices are the reviewed walkway slab. The preceding
  # 72 vertices are the six twelve-point moulding profiles.
  trim_start=n-80 if o['source_node']=='building-333' else None
  changed=[];front=[]
  for v in o.data.vertices:
   p=o.matrix_world@v.co;x,y,z=p.x,-p.y*SIN,p.z*COS
   d=1617-(x-910)*.348-y
   if trim_start is not None and v.index>=n-8:continue
   if trim_start is not None and v.index>=trim_start:
    shift=30*ratio if v.index>=trim_start+48 else 0
   else:
    shift=max(0,d)*ratio
   if abs(shift)<.001:front.append(v.index);continue
   v.co=inv@Vector((x-shift,p.y,p.z));changed.append(v.index)
  o.data.update();records.append(dict(object=o.name,changed_vertices=changed,unchanged_front_vertices=front))
  if trim_start is not None:
   # The corrected body now covers the former narrow walkway filler in full.
   # Remove that separate six-face slab to prevent overlapping top surfaces.
   old=o.data;slab=[o.matrix_world@v.co for v in old.vertices[-8:]]
   for p in slab:
    x,y=p.x,-p.y*SIN;front_y=1617-(x-910)*.348;rear_y=front_y-30*(1+.348*ratio)
    assert rear_y-.001<=y<=front_y+.001,(x,y,rear_y,front_y)
   mesh=bpy.data.meshes.new('Continuous corrected gateway with integral walkway');mesh.from_pydata([v.co[:] for v in old.vertices[:-8]],[],[tuple(p.vertices) for p in old.polygons if max(p.vertices)<n-8]);mesh.materials.append(neutral());mesh.uv_layers.new(name='UnprojectedSurfaceUV');mesh.update();o.data=mesh
 # Extend the clipped sprite's hidden side bars. Its authoritative pixel mesh
 # remains byte-for-byte in the vertex/face prefix and keeps its own UVs.
 extensions=[]
 for o in objs:
  if not o.get('animation_state'):continue
  if '--exact-sprite' in sys.argv:
   extensions.append(dict(object=o.name,state=o['animation_state'],original_vertices=len(o.data.vertices),original_faces=len(o.data.polygons),added_vertices=0,added_faces=0,aperture_bounds=[910-offset,984-offset],aperture_center=947-offset,lowered_sprite_bounds=[910,966],lowered_sprite_clearances=[offset,18-offset]));continue
  old=o.data;verts=[list(v.co) for v in old.vertices];faces=[list(p.vertices) for p in old.polygons];old_nv=len(verts);old_nf=len(faces);inv=o.matrix_world.inverted();lift=76 if o['animation_state']=='applied' else 0
  def box(x0,x1,z0,z1):
   k=len(verts)
   for depth in [0,1]:
    for x,z in [(x0,z0),(x1,z0),(x1,z1),(x0,z1)]:
     y=1600-(x-910)*.348+depth
     verts.append(list(inv@Vector((x,-y/SIN,(z+lift)/COS))))
   faces.extend(tuple(k+i for i in f) for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
  left,right=910-offset,984-offset
  box(left,left+2.5,100,178)
  for z in [127,170]:
   box(left+2.5,910,z,z+2.5)
  mesh=bpy.data.meshes.new(o.name+' / centered hidden continuation');mesh.from_pydata(verts,[],faces);mesh.update()
  for m in old.materials:mesh.materials.append(m)
  neutral_index=len(mesh.materials);mesh.materials.append(neutral())
  for p in mesh.polygons:p.material_index=old.polygons[p.index].material_index if p.index<old_nf else neutral_index
  for layer in old.uv_layers:
   uv=mesh.uv_layers.new(name=layer.name)
   for i,v in enumerate(layer.data):uv.data[i].uv=v.uv
  o.data=mesh;o['inferred_hidden_gate_sides']='Native pier axis and retained sprite plane imply full aperture width; neutral side bars are a hidden-depth hypothesis.'
  extensions.append(dict(object=o.name,state=o['animation_state'],original_vertices=old_nv,original_faces=old_nf,added_vertices=len(verts)-old_nv,added_faces=len(faces)-old_nf,full_width_bounds=[left,right],center=(left+right)/2))
 changed_names={r['object'] for r in records+extensions}
 assert all(fingerprint(bpy.data.objects[n])==v for n,v in before.items() if n not in changed_names)
 topology={}
 for o in objs:
  bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));topology[o.name]=dict(nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),degenerate_faces=sum(f.calc_area()<1e-8 for f in bm.faces));bm.to_mesh(o.data);bm.free()
 assert not any(any(r.values()) for r in topology.values()),topology
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
 (out/'inspection').mkdir(exist_ok=True)
 report=dict(status='construction-needs-source-visibility-review',source_model_sha256=sha(src/'model.blend'),native_depth_axis=[-35.94214,-31.6296],rear_shift_x=-30*ratio,gate_plane_offset=-17,inner_plane_offset=-6,gate_axis_displacement_x=-offset,gate_center=(910+984)/2-offset,sprite_bbox_center=938,geometry_records=records,extensions=extensions,topology=topology,front_contours='unchanged',floor='unchanged',sprite_original_geometry='unchanged',walkway='Corrected continuous body completely contains former filler slab; redundant slab removed.',limitations=['Hidden side extensions require strict source-ray occlusion proof before acceptance.','Brown right reveal belongs native375 / neighboring334; paired coverage still required.','Raised hidden side continuation has inferred76-unit lift; endpoint source sprite remains exact.'])
 if '--exact-sprite' in sys.argv:report['limitations']=['Concealed tunnel depth follows the native pier axis. Exact original endpoint meshes retained without inferred bars.','Brown right reveal requires paired native375 exterior ownership proof.']
 (out/'gate-center-report.json').write_text(json.dumps(report,indent=2)+'\n')
 if '--draft' in sys.argv:return
 modified(out)
 from restore_foreign_uv_schema import restore_foreign_uv_schema
 restore_foreign_uv_schema(out)
 from audit_stored_materials import run
 run(out,out/'inspection/stored-materials',render=True,export=False)
 report['model_sha256']=sha(out/'model.blend');(out/'gate-center-report.json').write_text(json.dumps(report,indent=2)+'\n')
 (out/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=ASSET,status='refinement-in-progress',geometry_refined=True,geometry_reviewed=False,recipe=str(Path(__file__).resolve())),indent=2)+'\n')
if __name__=='__main__':main()
