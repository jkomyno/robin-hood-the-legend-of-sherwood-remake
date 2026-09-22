"""Verify saved, reprojected geometry against the complete-wall v5 baseline."""
import bpy,bmesh,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
out=root/'inspection/north-corner-v6'
def collect():
 objects={o.name:o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH'}
 wall=next(o for o in objects.values() if o.get('source_node')=='building-025' and not o.hide_render)
 points=[wall.matrix_world@v.co for v in wall.data.vertices];bottom=min(p.z for p in points)
 footprint=sorted(set(tuple(round(p[i],3) for i in range(3)) for p in points if p.z<bottom+.01))
 hashes={o.name:hashlib.sha256(repr(([tuple(o.matrix_world@v.co) for v in o.data.vertices],[tuple(p.vertices) for p in o.data.polygons])).encode()).hexdigest() for o in objects.values() if o!=wall}
 return wall,footprint,hashes
bpy.ops.wm.open_mainfile(filepath=str(root/'inspection/complete-wall-candidate-v5/model.blend'))
_,before_footprint,before_hash=collect()
bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'))
wall,after_footprint,after_hash=collect()
assert before_footprint==after_footprint
assert before_hash==after_hash
bm=bmesh.new();bm.from_mesh(wall.data)
report={'status':'PASS','node':'building-025','unchanged_other_meshes':len(after_hash),'identical_ground_footprint':True,'ground_vertices':len(after_footprint),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces),'signed_volume':bm.calc_volume(signed=True)}
assert report['nonmanifold_edges']==0 and report['degenerate_faces']==0 and report['signed_volume']>0
bm.free()
(out/'preservation-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
