"""Saved mesh topology, vertical full wall and outside-geometry preservation."""
import bpy,bmesh,json,hashlib,math
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parent;out=root/'inspection/north-corner-v13'
def collect():
 meshes=[o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH']
 wall=next(o for o in meshes if o.get('source_node')=='building-025' and not o.hide_render)
 hashes={o.name:hashlib.sha256(repr(([tuple(o.matrix_world@v.co) for v in o.data.vertices],[tuple(p.vertices) for p in o.data.polygons])).encode()).hexdigest() for o in meshes if o!=wall}
 return wall,hashes
bpy.ops.wm.open_mainfile(filepath=str(root/'inspection/complete-wall-candidate-v5/model.blend'))
old,old_hashes=collect()
old_ground=[old.matrix_world@v.co for v in old.data.vertices if (old.matrix_world@v.co).z<.01]
bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'))
wall,hashes=collect();assert hashes==old_hashes
world=[wall.matrix_world@v.co for v in wall.data.vertices]
bm=bmesh.new();bm.from_mesh(wall.data)
report={'status':'PASS_MESH_AND_OUTSIDE_PRESERVATION','outside_meshes_unchanged':len(hashes),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces),'signed_volume':bm.calc_volume(signed=True),'footprint_changed':True,'complete_wall_to_ground':abs(min(p.z for p in world))<.001,'ground_vertex_count':sum(p.z<.01 for p in world)}
assert report['nonmanifold_edges']==report['degenerate_faces']==0 and report['signed_volume']>0 and report['complete_wall_to_ground']
bm.free()
body=[p for p in wall.data.polygons if min(world[i].z for i in p.vertices)<.01 and max(world[i].z for i in p.vertices)>180]
report['body_triangle_count']=len(body);report['max_body_normal_z']=max(abs(p.normal.z) for p in body)
assert report['max_body_normal_z']<.0001
sn,cs=math.sin(math.radians(35)),math.cos(math.radians(35));records=[]
for row in json.loads((out/'source-correspondences.json').read_text())['fitted']:
 for role in ('near','far','floor'):
  target=Vector(row['far_world'] if role=='far' else row['near_world'])
  if role=='floor':target.z=row['floor_z']
  p=min(world,key=lambda v:(v-target).length);assert(p-target).length<.001
  observed=row['near_floor' if role=='floor' else role+'_top'];actual=[p.x,-p.y*sn-p.z*cs]
  records.append({'run':row['run'],'boundary':row['boundary'],'role':role,'observed':observed,'actual_saved_mesh_pixel':actual,'error_px':math.dist(observed,actual)})
report['correspondences']=records;report['rms_px']=math.sqrt(sum(r['error_px']**2 for r in records)/len(records));report['max_px']=max(r['error_px'] for r in records)
report['warning']='Pixel residuals measure the manually selected observations, not independent source annotation accuracy. Inspect per-opening raw art and saved-mesh overlay. The narrowed full wall footprint intentionally differs from v5/v10.'
(out/'preservation-validation.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='correspondences'})
