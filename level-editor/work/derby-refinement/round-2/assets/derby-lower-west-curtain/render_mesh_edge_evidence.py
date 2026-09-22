"""Rasterize actual mesh crown edges over untouched source-camera crops."""
import sys,json,math
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages']
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image,ImageDraw
label='baseline-mesh-edge-audit' if Path(bpy.data.filepath).name=='baseline.blend' else 'mesh-edge-audit'
out=root/'inspection/complete-wall-candidate-v5'/label;out.mkdir(parents=True,exist_ok=True)
source=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
observations=json.loads((root/'inspection/complete-wall-candidate/corners/points.json').read_text())['records']
sin,cos=math.sin(math.radians(35)),math.cos(math.radians(35))
toward=Vector((0,-cos,sin))
def project(p):return (p.x,-p.y*sin-p.z*cos)
all_reports=[]
for node,box in [('building-025',(310,1525,412,1770)),('building-023',(315,1795,393,1985)),('building-042',(385,2110,527,2250))]:
 obj=next(o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH' and o.get('source_node')==node and not o.hide_render)
 mesh=obj.data;world=[obj.matrix_world@v.co for v in mesh.vertices]
 mesh.calc_loop_triangles();tree=BVHTree.FromPolygons(world,[list(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
 adj={tuple(sorted(e.vertices)):[] for e in mesh.edges}
 for f in mesh.polygons:
  for pair in f.edge_keys:adj[tuple(sorted(pair))].append(f)
 coords=[];segments=[]
 for e in mesh.edges:
  a,b=[world[i] for i in e.vertices]
  if min(a.z,b.z)<190:continue
  fs=adj[tuple(sorted(e.vertices))]
  if len(fs)!=2:continue
  if abs(fs[0].normal.dot(fs[1].normal))>.9999:continue
  transform=obj.matrix_world.to_3x3().inverted().transposed()
  normals=[(transform@f.normal).normalized() for f in fs]
  if not any(n.dot(toward)>.02 and abs(n.z)<.1 for n in normals):continue
  for j in range(8):
   p=a.lerp(b,j/8);q=a.lerp(b,(j+1)/8);mid=(p+q)/2
   hit,normal,face,distance=tree.ray_cast(mid+toward*1000,-toward,1001)
   if hit is None or (hit-mid).length>.2:continue
   segments.append([project(p),project(q)])
  for p in (a,b):
   hit,_,_,_=tree.ray_cast(p+toward*1000,-toward,1001)
   if hit is not None and (hit-p).length<.3:coords.append(project(p))
 coords=sorted(set((round(x,4),round(y,4)) for x,y in coords))
 im=source.crop(box).resize(((box[2]-box[0])*5,(box[3]-box[1])*5),Image.Resampling.NEAREST)
 d=ImageDraw.Draw(im)
 def screen(p):return ((p[0]-box[0]+.5)*5,(p[1]-box[1]+.5)*5)
 for a,b in segments:d.line((screen(a),screen(b)),fill=(255,40,70),width=1)
 rows=[]
 selected=[r for r in observations if ('023' in r['id'] and node.endswith('023')) or ('042-six' in r['id'] and node.endswith('042')) or ('025' in r['id'] and 'first-two' not in r['id'] and node.endswith('025'))]
 for r in selected:
  for i,p in enumerate(r['points']):
   nearest=min(coords,key=lambda q:(p[0]-q[0])**2+(p[1]-q[1])**2)
   error=math.dist(p,nearest);rows.append({'run':r['id'],'corner':i+1,'observed':p,'nearest_mesh_corner':nearest,'distance_pixels':error})
   x,y=screen(p);d.ellipse((x-2,y-2,x+2,y+2),fill='cyan');d.line((screen(p),screen(nearest)),fill='yellow',width=1)
 im.save(out/(node+'-edges.png'))
 source.crop(box).resize(im.size,Image.Resampling.NEAREST).save(out/(node+'-source.png'))
 report={'node':node,'visible_sharp_edge_segments':len(segments),'visible_candidate_vertices':coords,'corner_comparison':rows,'rms_nearest_vertex':math.sqrt(sum(r['distance_pixels']**2 for r in rows)/len(rows))}
 all_reports.append(report)
(out/'edge-residuals.json').write_text(json.dumps({'method':'Actual saved mesh edges projected through original35degree orthographic camera; visibility tested against same wall. Neighbor occluders not included. Nearest corner association is diagnostic, not unique semantic correspondence.','reports':all_reports},indent=2)+'\n')
(out/'review.md').write_text('''# Independent saved-mesh crown-edge audit

Red lines are edges read from the actual saved mesh and visibility-tested against
the wall. Cyan points are the independently picked source corners. Yellow lines
join the closest visible mesh corner. Source views are untouched alongside each
overlay. This is independent of the analytic crown-height fit, but nearest-vertex
associations can select a different corner; neighboring roofs are not occluders
in this wall-only audit. Read visible mismatches, not only aggregate errors.

## North025

![Source](building-025-source.png)

![Mesh edges and source corners](building-025-edges.png)

## South023 — difficult bend

![Source](building-023-source.png)

![Mesh edges and source corners](building-023-edges.png)

## South042

![Source](building-042-source.png)

![Mesh edges and source corners](building-042-edges.png)
''')
print([(r['node'],r['rms_nearest_vertex']) for r in all_reports])
