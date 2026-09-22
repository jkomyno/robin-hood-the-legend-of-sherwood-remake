"""Source-measured annex roof overhang, closed door and slit recess."""
import json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).resolve().parent))

def apply(workspace):
 import bpy,bmesh
 from mathutils import Vector
 from refinement_workspace import _geometry,modified,initialize_working_masks
 from refine_castle_secondary import native_prism,replace_mesh,sha,write
 from refine_castle_packets import apply_masks
 config=json.loads((workspace/'workspace.json').read_text());collection=bpy.data.collections[config['collection_name']];objects=list(collection.all_objects);before={o.name:_geometry(o) for o in objects}
 roof=next(o for o in objects if o.get('asset_group')==config['asset_id'] and o.get('source_node')=='building-377' and not o.get('castle_annex_body'))
 native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][377]['points']
 s,c=math.sin(math.radians(35)),math.cos(math.radians(35));cx=sum(p['x'] for p in native)/4;cy=sum(p['y'] for p in native)/4
 native_prism(roof,native,thickness=3/c);roof['projection_component']='castle-annex-roof'
 body=bpy.data.objects.get('building-377__castle-annex-body')
 if body is None:
  body=bpy.data.objects.new('building-377__castle-annex-body',roof.data.copy());collection.objects.link(body);body.parent=roof.parent;body.matrix_parent_inverse=roof.matrix_parent_inverse.copy();body.matrix_world=roof.matrix_world.copy()
  for key in roof.keys():body[key]=roof[key]
 body['castle_annex_body']=True;body['projection_component']='castle-annex-body'
 points=[dict(p,x=cx+(p['x']-cx)*.974,y=cy+(p['y']-cy)*.974,z_top=p['z_top']-3) for p in native]
 native_prism(body,points,bottom=100)
 outlines=[('closed timber door',[(344,1292),(344,1261),(362,1242),(362,1276)]),('narrow masonry slit',[(334,1290),(334,1269),(337,1264),(337,1286)])]
 for name,outline in outlines:
  a,b=points[1],points[0];verts=[]
  for depth in [2,-4]:
   for x,sy in outline:
    y=a['y']+(x-a['x'])*(b['y']-a['y'])/(b['x']-a['x'])+depth;verts.append(Vector((x,-y/s,(y-sy)/c)))
  n=len(outline);faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
  mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);cut=bpy.data.objects.new(name,mesh);collection.objects.link(cut);replace_mesh(cut,verts,faces)
  bpy.context.view_layer.objects.active=body;mod=body.modifiers.new(name,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
 rows=[]
 for obj in [roof,body]:
  bm=bmesh.new();bm.from_mesh(obj.data);bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-8 for f in bm.faces);bm.free();assert bad==deg==0,(obj.name,bad,deg)
  obj['castle_annex_recipe']='measured-annex-v1';rows.append({'object':obj.name,'nonmanifold_edges':bad,'degenerate_faces':deg,'geometry_sha256':_geometry(obj)})
 assert all(before[o.name]==_geometry(o) for o in objects if o not in [roof,body])
 initialize_working_masks(workspace);apply_masks(workspace,WORK/'mask-review/annex-overrides-v11.json')
 write(workspace/'annex-detail-report.json',{'recipe':str(Path(__file__).resolve()),'recipe_sha256':sha(__file__),'changes':rows,'source_evidence':['castle-audit/annex-measure.png','castle-audit/annex-door-measure.png','castle-audit/annex-mask-ownership.png'],'inference':'Three-unit roof thickness, small concealed wall inset and four-unit blind recess depth are inferred; native courtyard elevation100 retained.'})
 bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));modified(workspace)

if __name__=='__main__':
 from freeze_tooling import select_tooling
 select_tooling()
 from render_slots import acquire
 acquire()
 import bpy
 w=WORK/'round-1/assets/nottingham-castle-west-annex';bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));apply(w)
