"""Fit the revealed floor perimeter to the source tile and cut-stone boundary."""
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
TRACE=WORK/'castle-audit/v15-floor-independent/front-floor/complete-floor-trace.json'

def apply():
 import bpy,bmesh
 from mathutils import Vector
 source=json.loads(TRACE.read_text());new=[(x,y+420.001) for x,y in source['polygon']]
 points=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][501]['points']
 old=[(p['x'],p['y']) for p in points];old=old[5:]+old[:5]
 def area(p):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))
 if area(old)*area(new)<0:new=[new[0]]+list(reversed(new[1:]))
 def lengths(p):
  out=[0.]
  for a,b in zip(p,p[1:]+p[:1]):out.append(out[-1]+math.dist(a,b))
  return [x/out[-1] for x in out]
 ol,nl=lengths(old),lengths(new);fractions=sorted(set(ol[:-1]+nl[:-1]))
 def sample(p,l,t):
  j=next(j for j in range(len(p)) if l[j]<=t<l[j+1]);f=(t-l[j])/(l[j+1]-l[j]);a,b=p[j],p[(j+1)%len(p)];return (a[0]+f*(b[0]-a[0]),a[1]+f*(b[1]-a[1]))
 low=[sample(old,ol,t) for t in fractions];high=[sample(new,nl,t) for t in fractions]
 s,c=math.sin(math.radians(35)),math.cos(math.radians(35));rows=[]
 for component,rings in [('castle-hall-floor',[(high,418),(high,420.001)]),('castle-hall-floor-support',[(low,0),(low,350),(high,380),(high,418)])]:
  obj=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.get('source_node')=='building-501' and o.get('projection_component')==component)
  inv=obj.matrix_world.inverted();verts=[inv@Vector((x,-y/s,z/c)) for outline,z in rings for x,y in outline];n=len(high);faces=[tuple(reversed(range(n))),tuple(range((len(rings)-1)*n,len(rings)*n))]
  for r in range(len(rings)-1):
   faces.extend((r*n+i,r*n+(i+1)%n,(r+1)*n+(i+1)%n,(r+1)*n+i) for i in range(n))
  mesh=bpy.data.meshes.new(obj.name+' source floor boundary');mesh.from_pydata(verts,[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-8 for f in bm.faces);volume=bm.calc_volume();assert bad==deg==0 and volume>0,(bad,deg,volume);bm.to_mesh(mesh);bm.free()
  for mat in obj.data.materials:mesh.materials.append(mat)
  for name in ([u.name for u in obj.data.uv_layers] or ['Source projection']):
   uv=mesh.uv_layers.new(name=name)
   for loop in mesh.loops:
    v=obj.matrix_world@mesh.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(v.x/2304,1-(-v.y*s-v.z*c)/3520)
  obj.data=mesh;obj['hall_floor_source_boundary']='outer-floor-v1';rows.append(dict(object=obj.name,vertices=len(mesh.vertices),faces=len(mesh.polygons),volume=volume,nonmanifold_edges=bad,degenerate_faces=deg))
 return dict(status='GEOMETRY-PROTOTYPE',changed=rows,source_trace=source,floor_native_height=420.001,original_foundation_preserved_below=350,vertical_upper_support_bottom=380,hidden_transition_inference='The original foundation transitions between native350 and380 to the measured upper cut outline; concealed transition is inferred.')

if __name__=='__main__':
 import sys,hashlib
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 from freeze_tooling import select_tooling
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 source=WORK/'round-41/assets/nottingham-castle-main-hall/model.blend';out=WORK/'castle-audit/v15-floor-independent/front-floor/prototype';out.mkdir(exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(source));report=apply();bpy.context.view_layer.update();bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));report['model_sha256']=hashlib.sha256((out/'model.blend').read_bytes()).hexdigest();(out/'geometry.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
