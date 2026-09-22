"""Check that preserved lower facade surface samples still lie on the candidate."""
import bpy,json,sys
from pathlib import Path
from mathutils.bvhtree import BVHTree
W=Path(__file__).parent;D=W/'next-zigzag-v3'
nodes={f'building-{n}' for n in [183,184,185,189,191,192,194,198]}
bpy.ops.wm.open_mainfile(filepath=str(W/'next-casement/model.blend'))
samples={}
for o in bpy.data.collections['Derby Working'].all_objects:
 if o.type!='MESH' or o.hide_render or o.get('source_node') not in nodes:continue
 vs=[o.matrix_world@v.co for v in o.data.vertices];o.data.calc_loop_triangles();points=[]
 for tri in o.data.loop_triangles:
  a,b,c=[vs[i] for i in tri.vertices]
  if max(a.z,b.z,c.z)>=364.99:continue
  points.extend([(a+b+c)/3,(a+b)/2,(b+c)/2,(c+a)/2])
 samples[o.get('source_node')]=points
candidate=Path(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else D/'band-candidate.blend'
bpy.ops.wm.open_mainfile(filepath=str(candidate.resolve()));result={}
for o in bpy.data.collections['Derby Working'].all_objects:
 if o.type!='MESH' or o.hide_render or o.get('source_node') not in samples:continue
 tree=BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons])
 distances=[tree.find_nearest(p)[3] for p in samples[o.get('source_node')]]
 # Nonplanar n-gons can choose slightly different triangle diagonals after
 # the upper boundary changes. A tenth of a world unit is below a source
 # pixel here; retain the measured distance instead of claiming identity.
 result[o.get('source_node')]=dict(samples=len(distances),maximum_world_distance=max(distances,default=0),tolerance_world=.1,missing=sum(d>.1 for d in distances))
(D/'lower-surface-validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
assert not any(r['missing'] for r in result.values()),'Lower facade surface changed'
