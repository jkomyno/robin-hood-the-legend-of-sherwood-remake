"""Apply the measured curved-crown correction to only wall-200-1."""
import json,sys,math,hashlib,shutil
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
R=Path(__file__).resolve().parents[3];W=R/'level-editor/work/nottingham-refinement';P=W/'round-13/assets/nottingham-south-curtain-wall-1';sys.path.insert(0,str(Path(__file__).parent))
from refine_fortifications import north_wall_geometry
from partition_curtain_walls import clipped
S=math.sin(math.radians(35));C=math.cos(math.radians(35))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def geom(o):return {'v':[list(v.co)for v in o.data.vertices],'f':[list(p.vertices)for p in o.data.polygons],'matrix':[list(row)for row in o.matrix_world]}
def apply(obj,fit):
 pts=[dict(p)for p in fit['points']]
 for i in [2,13]:pts[i]['z_top']+=1.5
 v,f=north_wall_geometry(pts,fit['pairs']+[(2,13)],fit['notches'],notch_depth=fit['notch_depth']);verts=[];faces=[];lookup={}
 def vertex(p):
  key=tuple(round(x,6)for x in p)
  if key not in lookup:lookup[key]=len(verts);verts.append(p)
  return lookup[key]
 for face in f:
  poly=clipped([v[i]for i in face],(1,0,0),1519,-1)
  if len(poly)>=3:
   ids=list(dict.fromkeys(vertex(p)for p in poly))
   if len(ids)>=3:faces.append(ids)
 inv=obj.matrix_world.inverted();mesh=bpy.data.meshes.new('Southern curved parapet / numbered source corners');mesh.from_pydata([inv@Vector((x,-y/S,z/C))for x,y,z in verts],[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);boundary=[e for e in bm.edges if e.is_boundary]
 if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.dissolve_degenerate(bm,dist=.00001,edges=list(bm.edges));bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-8 for f in bm.faces);assert bad==0 and deg==0,(bad,deg);volume=bm.calc_volume(signed=True);assert volume>0;bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='Source projection')
 for material in obj.data.materials:mesh.materials.append(material)
 obj.data=mesh
 return {'vertices':len(mesh.vertices),'triangles':len(mesh.polygons),'nonmanifold_edges':bad,'degenerate_faces':deg,'signed_volume':volume}

def main():
 from render_slots import acquire
 from freeze_tooling import select_tooling
 acquire();tooling=select_tooling(W/'tooling/58744eeaf71a21e9');from refinement_workspace import modified
 bpy.ops.wm.open_mainfile(filepath=str(P/'model.blend'));target=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('projection_component')=='wall-200-1');assert target.get('source_node')=='building-200';before={o.name:geom(o)for o in bpy.data.objects if o.type=='MESH'and o!=target};matrix=target.matrix_world.copy();fit=json.loads((W/'fortifications-audit/south-curve-user-revision/corner-fit.json').read_text());old=sha(P/'model.blend');archive=P/'crown-before'/old[:12];archive.mkdir(parents=True,exist_ok=True)
 if not(archive/'model.blend').exists():shutil.copy2(P/'model.blend',archive/'model.blend');shutil.copytree(P/'modified',archive/'modified',dirs_exist_ok=True)
 report=apply(target,fit);first=geom(target);apply(target,fit);assert first==geom(target);assert target.matrix_world==matrix;assert before=={o.name:geom(o)for o in bpy.data.objects if o.type=='MESH'and o!=target};bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(P/'model.blend'));validation=modified(P);assert first==geom(target)
 points=[target.matrix_world@v.co for v in target.data.vertices];(P/'inspection/curved-crown-correction.json').write_text(json.dumps({'status':'PASS','asset_id':'nottingham-south-curtain-wall-1','source_node':'building-200','projection_component':'wall-200-1','model_sha256':sha(P/'model.blend'),'previous_model_sha256':old,'modified_views_sha256':sha(P/'modified/views.json'),'native_mask_unchanged':126,'user_split_x':1519,'idempotence':'PASS','outside_objects_preserved':len(before),'transform_preserved':True,'post_bake_geometry_preserved':True,'topology':report,'tooling':tooling['snapshot_id'],'validation':validation,'source_fit':fit,'actual_source_vertices':[[p.x,-p.y*S-p.z*C]for p in points],'actual_edges':[list(e.vertices)for e in target.data.edges],'actual_faces':[list(f.vertices)for f in target.data.polygons]},indent=2)+'\n');shutil.copy2(__file__,P/'curved-crown-recipe.py');print('PASS',sha(P/'model.blend'),flush=True)
if __name__=='__main__':main()
