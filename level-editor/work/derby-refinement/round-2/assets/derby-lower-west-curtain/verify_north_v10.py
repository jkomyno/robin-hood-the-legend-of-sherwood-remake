"""Read saved geometry; check preservation and labeled near/far/floor corners."""
import bpy,bmesh,json,hashlib,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path(__file__).resolve().parent;out=root/'inspection/north-corner-v10'
def collect():
 objects={o.name:o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH'}
 wall=next(o for o in objects.values() if o.get('source_node')=='building-025' and not o.hide_render)
 points=[wall.matrix_world@v.co for v in wall.data.vertices];bottom=min(p.z for p in points)
 footprint=sorted(set(tuple(round(p[i],3) for i in range(3)) for p in points if p.z<bottom+.01))
 hashes={o.name:hashlib.sha256(repr(([tuple(o.matrix_world@v.co) for v in o.data.vertices],[tuple(p.vertices) for p in o.data.polygons])).encode()).hexdigest() for o in objects.values() if o!=wall}
 return wall,points,footprint,hashes
bpy.ops.wm.open_mainfile(filepath=str(root/'inspection/complete-wall-candidate-v5/model.blend'))
old,oldpoints,before_footprint,before_hash=collect();old.data.calc_loop_triangles()
tree=BVHTree.FromPolygons(oldpoints,[tuple(t.vertices) for t in old.data.loop_triangles],all_triangles=True)
bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'))
wall,points,footprint,hashes=collect();assert footprint==before_footprint and hashes==before_hash
wall.data.calc_loop_triangles();lower=[]
for tri in wall.data.loop_triangles:
 samples=[points[i] for i in tri.vertices]
 if max(p.z for p in samples)<190.01:
  p=sum(samples,Vector())/3;nearest=tree.find_nearest(p);lower.append(nearest[3])
print('Lower wall closest-surface distances',sorted(lower,reverse=True)[:12])
bm=bmesh.new();bm.from_mesh(wall.data)
report={'status':'PASS_TOPOLOGY_AND_OUTSIDE_GEOMETRY','node':'building-025','unchanged_other_meshes':len(hashes),'identical_ground_footprint':True,'lower_wall_sample_count':len(lower),'lower_wall_max_distance':max(lower),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces),'signed_volume':bm.calc_volume(signed=True)}
assert report['nonmanifold_edges']==0 and report['degenerate_faces']==0 and report['signed_volume']>0
bm.free()
data=json.loads((out/'source-correspondences.json').read_text());sn=math.sin(math.radians(35));cs=math.cos(math.radians(35));rows=[]
for i,record in enumerate(data['fitted']):
 for role in ('near','far','floor'):
  target=Vector(record['far_world'] if role=='far' else record['near_world'])
  if role=='floor':target.z=record['floor_z']
  p=min(points,key=lambda v:(v-target).length)
  assert (p-target).length<.001
  projected=[p.x,-p.y*sn-p.z*cs]
  observed=record['near_floor' if role=='floor' else role+'_top']
  rows.append({'run':record['run'],'boundary':i+1,'role':role,'observed':observed,'saved_mesh_projection':projected,'pixel_error':math.dist(observed,projected)})
report['correspondences']=rows
report['max_corner_error_pixels']=max(r['pixel_error'] for r in rows)
report['rms_corner_error_pixels']=math.sqrt(sum(r['pixel_error']**2 for r in rows)/len(rows))
report['note']='Labeled near/far/floor correspondence, not nearest projected pixel. The manual observations have about two pixel uncertainty. These residuals validate the saved construction against those picks; inspect the unmodified-art/solid/textured triptychs independently.'
(out/'preservation-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print({k:v for k,v in report.items() if k!='correspondences'})
