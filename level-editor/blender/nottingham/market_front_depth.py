"""Read-only source-camera first-hit audit of the market facade and foreground props."""
import sys,json,math,hashlib,argparse
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[3];W=R/'level-editor/work/nottingham-refinement';sys.path[:0]=[str(W/'tooling/315d227e98d52a78'),str(R/'level-editor/blender/nottingham')]
from render_slots import acquire
acquire()
parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);blend='baseline.blend' if args.baseline else 'model.blend';suffix='-baseline' if args.baseline else '';p=W/'round-1/assets/nottingham-market-terrace';bpy.ops.wm.open_mainfile(filepath=str(p/blend));bpy.context.view_layer.update();objs=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and not o.hide_render];v=[];tri=[];owners=[]
for o in objs:
 off=len(v);v.extend(o.matrix_world@x.co for x in o.data.vertices);o.data.calc_loop_triangles()
 for t in o.data.loop_triangles:tri.append(tuple(off+i for i in t.vertices));owners.append(o.get('source_node',o.name))
tree=BVHTree.FromPolygons(v,tri,all_triangles=True);ang=math.radians(35);toward=Vector((0,-math.cos(ang),math.sin(ang)));depth=max(x.dot(toward)for x in v)+10
samples=[]
for y in range(1450,1671,2):
 for x in range(1490,2041,2):
  pt=Vector((x,-y/math.sin(ang),0));hit,n,idx,d=tree.ray_cast(pt+toward*(depth-pt.dot(toward)),-toward)
  owner=owners[idx]if idx is not None else None
  if owner in {f'building-{i:03}'for i in range(23)}:samples.append({'xy':[x,y],'first_hit':owner,'world':list(hit),'height_native':hit.z*math.cos(ang)})
(W/f'town-audit/market-front-depth{suffix}.json').write_text(json.dumps({'model_sha256':hashlib.sha256((p/blend).read_bytes()).hexdigest(),'samples':samples},indent=2)+'\n');print('Samples',len(samples))
