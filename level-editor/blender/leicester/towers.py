"""Measured conical roof shells and explicit tower cutaway components.

World source anchors are retained; hidden shell thickness and radial curvature
remain documented hypotheses. Every component preserves its canonical owner.
"""
import argparse, json, math, sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from refinement_workspace import validate
TAG='leicester-tower-shells-v1'
SPECS={
 'leicester-northwest-tower':dict(patch='patch-007',roofs=list(range(334,344)),walls=[331,350],floors=[332,333],center_y=-815,cut_z=474),
 'leicester-east-moat-tower':dict(patch='patch-003',roofs=list(range(169,179)),walls=[162,163,165,166,168,182,190],floors=[164,167,179,180,184],center_y=-1694,cut_z=602),
 'leicester-church-side-tower':dict(patch='patch-003',roofs=list(range(200,210)),walls=[199,220],floors=[198,210],center_y=-1494,cut_z=444),
 'leicester-west-moat-tower':dict(patch='patch-013',roofs=list(range(259,269)),walls=[249,258,276,277],floors=[248,250,253,255,256,257],center_y=-1847,cut_z=456),
}
def sn(n):return f'building-{n:03}'
def write_mesh(obj,verts,faces,name):
 mesh=bpy.data.meshes.new(name);inv=obj.matrix_world.inverted();mesh.from_pydata([inv@Vector(v) for v in verts],[],faces);mesh.update()
 for material in obj.data.materials:mesh.materials.append(material)
 mesh.uv_layers.new(name='UVMap');obj.data=mesh

def split_mesh(verts,faces,axis,value,positive):
 bm=bmesh.new();vs=[bm.verts.new(v) for v in verts];bm.verts.ensure_lookup_table()
 for face in faces:
  try:bm.faces.new([vs[i] for i in face])
  except ValueError:pass
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.15)
 co=[0,0,0];co[axis]=value;normal=[0,0,0];normal[axis]=1
 result=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.00001,plane_co=co,plane_no=normal,clear_inner=positive,clear_outer=not positive)
 cut=[e for e in result['geom_cut'] if isinstance(e,bmesh.types.BMEdge) and e.is_boundary]
 if cut:bmesh.ops.holes_fill(bm,edges=cut,sides=0)
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.verts.ensure_lookup_table();bm.verts.index_update()
 out=([list(v.co) for v in bm.verts],[tuple(v.index for v in f.verts) for f in bm.faces]);bm.free();return out

def combine(*pieces):
 vertices=[];faces=[]
 for v,f in pieces:
  offset=len(vertices);vertices.extend(v);faces.extend(tuple(i+offset for i in face) for face in f)
 return vertices,faces

def roof_geometry(obj):
 world=[obj.matrix_world@v.co for v in obj.data.vertices];low=min(v.z for v in world);high=max(v.z for v in world)
 eaves=[v for v in world if v.z<low+2.0];a,b=max(((a,b) for a in eaves for b in eaves),key=lambda pair:(pair[0]-pair[1]).length)
 apex=sum((v for v in world if v.z>high-1.5),Vector())/sum(v.z>high-1.5 for v in world)
 theta1=math.atan2(a.y-apex.y,a.x-apex.x);theta2=math.atan2(b.y-apex.y,b.x-apex.x);delta=(theta2-theta1+math.pi)%(2*math.pi)-math.pi
 if abs(delta)>math.pi*.65:raise ValueError('Ambiguous roof sector '+obj.name)
 r1=(Vector((a.x,a.y))-Vector((apex.x,apex.y))).length;r2=(Vector((b.x,b.y))-Vector((apex.x,apex.y))).length
 # Six radial samples describe the visible slightly flared roof profile.
 ts=[0,.24,.45,.65,.82,1];verts=[];faces=[];angular=4
 for t in ts:
  for j in range(angular+1):
   f=j/angular;theta=theta1+delta*f;r=(r1*(1-f)+r2*f)*t;z=high-(high-low)*t**.90
   verts.append((apex.x+math.cos(theta)*r,apex.y+math.sin(theta)*r,z))
 for i in range(len(ts)-1):
  for j in range(angular):
   u=i*(angular+1)+j;faces.append((u,u+1,u+angular+2,u+angular+1))
 bm=bmesh.new();vs=[bm.verts.new(v) for v in verts]
 for f in faces:
  try:bm.faces.new([vs[i] for i in f])
  except ValueError:pass
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.001)
 boundary=[e for e in bm.edges if e.is_boundary]
 bm.verts.ensure_lookup_table();bm.verts.index_update();top=[list(v.co) for v in bm.verts];polys=[tuple(v.index for v in f.verts) for f in bm.faces];edges=[tuple(v.index for v in e.verts) for e in boundary];bm.free()
 count=len(top);verts=top+[(x,y,z-3) for x,y,z in top];faces=polys+[tuple(i+count for i in reversed(f)) for f in polys]+[(a,b,b+count,a+count) for a,b in edges]
 return verts,faces

def horizontal_shell(obj,thickness=None):
 world=[obj.matrix_world@v.co for v in obj.data.vertices];high=max(v.z for v in world);low=min(v.z for v in world) if thickness is None else high-thickness
 topfaces=[tuple(f.vertices) for f in obj.data.polygons if all(world[i].z>high-2 for i in f.vertices)]
 if not topfaces:raise ValueError('No horizontal source cap: '+obj.name)
 bm=bmesh.new();vs=[bm.verts.new((v.x,v.y,high)) for v in world]
 for f in topfaces:
  try:bm.faces.new([vs[i] for i in f])
  except ValueError:pass
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.6);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.001)
 loose=[v for v in bm.verts if not v.link_faces];bmesh.ops.delete(bm,geom=loose,context='VERTS')
 bm.verts.ensure_lookup_table();bm.verts.index_update();verts=[list(v.co) for v in bm.verts];faces=[tuple(v.index for v in f.verts) for f in bm.faces];edges=[tuple(v.index for v in e.verts) for e in bm.edges if e.is_boundary];bm.free()
 n=len(verts);return verts+[(x,y,low) for x,y,z in verts],faces+[tuple(i+n for i in reversed(f)) for f in faces]+[(a,b,b+n,a+n) for a,b in edges]

def native_shell(obj):
 n=int(obj['source_node'][9:]);path=Path(__file__).resolve().parents[3]/'datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.json'
 points=json.loads(path.read_text())['sight_obstacles'][n]['points'];sine=math.sin(math.radians(35));cosine=math.cos(math.radians(35));count=len(points)
 verts=[(p['x'],-p['y']/sine,p[key]/cosine) for key in ['z_top','z_bottom'] for p in points]
 faces=[tuple(range(count)),tuple(reversed(range(count,2*count)))]+[(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
 bm=bmesh.new();vs=[bm.verts.new(v) for v in verts]
 for face in faces:bm.faces.new([vs[i] for i in face])
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.001)
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.verts.ensure_lookup_table();bm.verts.index_update()
 out=([list(v.co) for v in bm.verts],[tuple(v.index for v in f.verts) for f in bm.faces]);bm.free();return out

def diagnostics(obj):
 bm=bmesh.new();bm.from_mesh(obj.data);result=dict(vertices=len(bm.verts),faces=len(bm.faces),nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),degenerate_faces=sum(f.calc_area()<1e-7 for f in bm.faces));bm.free();return result

def refine(workspace):
 config=json.loads((workspace/'workspace.json').read_text());spec=SPECS[config['asset_id']];patch=spec['patch'];validate(workspace)
 collection=bpy.data.collections[config['collection_name']];targets=[o for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']]
 if any(o.get('tower_recipe')==TAG for o in targets):raise ValueError('Recipe already applied; reopen baseline to revise')
 from refinement_workspace import _absolute_manifest_images
 frozen=workspace/'reference/layers.json';fresh=_absolute_manifest_images(json.loads(frozen.read_text()),frozen.parent);Path(config['projection_manifest']).write_text(json.dumps(fresh,indent=2)+'\n')
 selected=set(spec['roofs']+spec['walls']+spec['floors']);report=[];covers=[];retained=[];cover_only=[];retained_only=[]
 for obj in targets:
  n=int(obj['source_node'][9:])
  if config['asset_id']=='leicester-west-moat-tower' and n in [249,277]:continue
  if n in [181,185,211,252,254]:
   from towers_interior import refine_ladder
   report.append(refine_ladder(obj));obj['tower_recipe']=TAG
   continue
  if n in [274,275]:
   from towers_interior import refine_hatch_frame
   report.append(refine_hatch_frame(obj));obj['tower_recipe']=TAG
   continue
  if n not in selected:continue
  before=diagnostics(obj);matrix=obj.matrix_world.copy();world=[list(matrix@v.co) for v in obj.data.vertices];faces=[tuple(f.vertices) for f in obj.data.polygons]
  isroof=n in spec['roofs']
  if n in spec['floors']:
   world,faces=horizontal_shell(obj,8);write_mesh(obj,world,faces,obj.name+' hatch floor slab');obj['tower_recipe']=TAG
   report.append(dict(source_node=obj['source_node'],before=before,after=diagnostics(obj),floor_rebuilt=True,world_transform_drift=0));continue
  if isroof:world,faces=roof_geometry(obj)
  else:world,faces=native_shell(obj)
  if n in [162,163]:
   from towers_doorway import cut_east_doorway
   write_mesh(obj,world,faces,obj.name+' closed wall before doorway')
   (workspace/'inspection').mkdir(exist_ok=True)
   world,faces=cut_east_doorway(obj,workspace)
  back=split_mesh(world,faces,1,spec['center_y'],True);front=split_mesh(world,faces,1,spec['center_y'],False)
  if isroof:
   cap=split_mesh(*front,2,spec['cut_z'],True);cover=split_mesh(*front,2,spec['cut_z'],False);keep=combine(back,cap)
  else:keep,cover=back,front
  if not keep[1] or not cover[1]:
   piece=keep if keep[1] else cover
   write_mesh(obj,*piece,obj.name+' refined');obj['tower_recipe']=TAG
   component='tower-retained' if keep[1] else 'tower-cover'
   obj['projection_component']=component;obj['reveal_component_patch_id']=patch;obj['reveal_component_role']='retained-shell' if keep[1] else 'removable-cover'
   if keep[1]:retained_only.append(obj['source_node'])
   else:
    cover_only.append(obj['source_node']);covers.append({'source_node':obj['source_node'],'projection_component':component,'patch_id':patch})
   report.append(dict(source_node=obj['source_node'],before=before,after=diagnostics(obj),split=False));continue
  duplicate=obj.copy();duplicate.data=obj.data.copy();collection.objects.link(duplicate);duplicate.name=obj.name+' removable front';duplicate.matrix_world=matrix
  for ob,piece,component in [(obj,keep,'tower-retained'),(duplicate,cover,'tower-cover')]:
   write_mesh(ob,*piece,ob.name+' authored shell');ob['projection_component']=component;ob['reveal_component_patch_id']=patch;ob['tower_recipe']=TAG;ob['reveal_component_role']='removable-cover' if component=='tower-cover' else 'retained-shell'
  selector={'source_node':obj['source_node'],'projection_component':'tower-cover','patch_id':patch};covers.append(selector);retained.append(obj['source_node'])
  report.append(dict(source_node=obj['source_node'],before=before,after=diagnostics(obj),cover=diagnostics(duplicate),split=True,world_transform_drift=0))
 path=Path(config['projection_manifest']);manifest=json.loads(path.read_text());review=manifest['projection_reviews'][patch]
 review['exclude_occluder_components']+=covers
 for node in retained:
  if node not in review['receiver_nodes']:review['receiver_nodes'].append(node)
  review['receiver_components'].setdefault('exterior',[]).append({'source_node':node,'projection_components':['tower-cover'],'patch_id':patch})
  review['receiver_components'].setdefault('interior-'+patch,[]).append({'source_node':node,'projection_components':['tower-retained'],'patch_id':patch})
 review['render_visibility']['revealed']['hidden_components']+=covers
 for node in cover_only:review['receiver_components'].setdefault('exterior',[]).append({'source_node':node,'projection_components':['tower-cover'],'patch_id':patch})
 for node in retained_only:
  if node not in review['receiver_nodes']:review['receiver_nodes'].append(node)
  review['receiver_components'].setdefault('interior-'+patch,[]).append({'source_node':node,'projection_components':['tower-retained'],'patch_id':patch})
 review['render_visibility']['limitations']=['Authored roof front and front wall cuts expose existing measured floors. Hidden thickness and roof curvature require owner review.']
 review['geometry_ready']=True;review['state_visibility_review']['cutaway_complete']=True
 review['evidence']+='; Tower recipe splits front shells at measured ring center; roof tip cap retained; per-component geometry report records hypotheses.'
 if config['asset_id']=='leicester-west-moat-tower':
  from towers_west import refine_shells
  report.extend(refine_shells(collection,config['asset_id'],manifest))
 path.write_text(json.dumps(manifest,indent=2)+'\n')
 (workspace/'inspection').mkdir(exist_ok=True)
 result=dict(recipe=TAG,asset_id=config['asset_id'],objects=report,roof_thickness=3,roof_curvature_exponent=.90,front_split_y=spec['center_y'],roof_cap_z=spec['cut_z'],limitations=['Roof radial curvature and hidden 3-unit thickness are inferred from source silhouette; exact underside is unknown.','Existing floor/hatch and ladder geometry retained pending detailed step review.','Cutaway reveals front half; precise painted diagonal edges need final source comparison.'],approval_status='refinement in progress')
 (workspace/'inspection/tower-geometry.json').write_text(json.dumps(result,indent=2)+'\n');validate(workspace);bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);print(json.dumps(refine(a.workspace.resolve()),indent=2))
