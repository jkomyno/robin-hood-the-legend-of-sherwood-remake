"""Check the saved wall/stair partition and render their actual material composition."""
import sys,json,math,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy,bmesh
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from audit_stored_materials import run
wall=WORK/'round-35/assets/nottingham-southwest-curtain-wall-north';stair=WORK/'round-33/assets/nottingham-southwest-wall-stair';out=wall/'inspection/composite-final';out.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(stair/'model.blend'));obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==stair.name and not o.hide_render);name=obj.name;matrix=obj.matrix_world.copy()
bpy.ops.wm.open_mainfile(filepath=str(wall/'model.blend'));target=bpy.data.objects[name]
with bpy.data.libraries.load(str(stair/'model.blend'),link=False) as (source,dest):dest.objects=[name]
loaded=dest.objects[0];target.data=loaded.data.copy();target.matrix_world=matrix;target['asset_group']=wall.name;bpy.data.objects.remove(loaded,do_unlink=True);bpy.context.view_layer.update()
topology=[]
for o in bpy.context.scene.objects:
 if o.type=='MESH' and o.get('asset_group')==wall.name and not o.hide_render:
  bm=bmesh.new();bm.from_mesh(o.data);topology.append(dict(object=o.name,signed_volume=bm.calc_volume(signed=True),nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),degenerate_faces=sum(f.calc_area()<1e-8 for f in bm.faces)));bm.free()
assert all(t['signed_volume']>0 and t['nonmanifold_edges']==0 and t['degenerate_faces']==0 for t in topology),topology
names=[o.name for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group') in [wall.name,stair.name] and not o.hide_render]
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
cfg=json.loads((wall/'workspace.json').read_text());(out/'workspace.json').write_text(json.dumps(cfg,indent=2)+'\n')
result=run(out,out/'actual',render=True,export=False,frame_manifest=wall/'modified/views.json',render_object_names=names);assert result['status']=='STRUCTURAL-PASS',result['problems']
bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'))
def tree(asset):
 vertices=[];faces=[]
 for o in bpy.context.scene.objects:
  if o.type=='MESH' and ((o.name==name) if asset==stair.name else (o.get('asset_group')==wall.name and o.name!=name)) and not o.hide_render:
   n=len(vertices);vertices.extend(o.matrix_world@v.co for v in o.data.vertices);faces.extend([n+i for i in f.vertices] for f in o.data.polygons)
 return BVHTree.FromPolygons(vertices,faces)
a,b=tree(wall.name),tree(stair.name);s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));old=json.loads((WORK/'round-13/assets'/wall.name/'inspection/source-domain-audit/domains.json').read_text());rows=[]
for x,y in old['domains']['rejected:visible']:
 if not (690<x<735 and 1510<y<1580):continue
 origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;ha=a.ray_cast(origin,-toward);hb=b.ray_cast(origin,-toward);rows.append(dict(pixel=[x,y],wall_distance=ha[3],stair_distance=hb[3],stair_strictly_front=hb[3] is not None and (ha[3] is None or hb[3]<ha[3])))
report=dict(wall_topology=topology,status='REVIEW-REQUIRED',wall_model_sha256=sha(wall/'model.blend'),stair_model_sha256=sha(stair/'model.blend'),composite_model_sha256=sha(out/'model.blend'),samples=len(rows),stair_strictly_front=sum(r['stair_strictly_front'] for r in rows),missing_stair_hits=sum(r['stair_distance'] is None for r in rows),coplanar_competing_hits=sum(r['wall_distance'] is not None and r['stair_distance'] is not None and abs(r['wall_distance']-r['stair_distance'])<.01 for r in rows),rows=rows)
(out/'source-rays.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='rows'})
