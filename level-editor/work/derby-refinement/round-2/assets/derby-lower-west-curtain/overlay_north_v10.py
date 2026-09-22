"""Project visible sharp edges from saved v10 geometry onto original pixels."""
import sys,math,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages']
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image,ImageDraw
out=root/'inspection/north-corner-v10'
expected=(out/'model.blend').resolve()
assert Path(bpy.data.filepath).resolve()==expected
obj=next(o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH' and o.get('source_node')=='building-025' and not o.hide_render)
mesh=obj.data;world=[obj.matrix_world@v.co for v in mesh.vertices]
mesh.calc_loop_triangles();tree=BVHTree.FromPolygons(world,[list(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
adj={tuple(sorted(e.vertices)):[] for e in mesh.edges}
for face in mesh.polygons:
 for pair in face.edge_keys:adj[tuple(sorted(pair))].append(face)
sn,cs=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-cs,sn))
def project(p):return (p.x,-p.y*sn-p.z*cs)
transform=obj.matrix_world.to_3x3().inverted().transposed();segments=[];edge_count=0
for edge in mesh.edges:
 a,b=[world[i] for i in edge.vertices]
 if min(a.z,b.z)<189.99:continue
 faces=adj[tuple(sorted(edge.vertices))]
 if len(faces)!=2:continue
 normals=[(transform@f.normal).normalized() for f in faces]
 if normals[0].dot(normals[1])>math.cos(math.radians(4)):continue
 if not any(n.dot(toward)>.001 for n in normals):continue
 count=max(1,math.ceil(math.dist(project(a),project(b))*3));edge_count+=1
 for i in range(count):
  p=a.lerp(b,i/count);q=a.lerp(b,(i+1)/count);middle=(p+q)/2
  hit,_,_,_=tree.ray_cast(middle+toward*1000,-toward,1001)
  if hit is not None and (hit-middle).length<.03:segments.append([project(p),project(q)])
source_path=root/'reference/mission-patches/H03_Der_MK-initial.png'
source=Image.open(source_path).convert('RGB');panels=[]
for name,box in [('front',(322,1550,392,1664)),('return',(328,1640,412,1766))]:
 scale=8;image=source.crop(box).resize(((box[2]-box[0])*scale,(box[3]-box[1])*scale),Image.Resampling.NEAREST)
 draw=ImageDraw.Draw(image)
 def screen(p):return ((p[0]-box[0])*scale,(p[1]-box[1])*scale)
 for a,b in segments:draw.line((screen(a),screen(b)),fill=(255,40,70),width=1)
 image.save(out/(name+'-mesh-on-artwork.png'));panels.append((name,image))
sheet=Image.new('RGB',(sum(im.width for _,im in panels),max(im.height for _,im in panels)+30),'#222222');d=ImageDraw.Draw(sheet);left=0
for name,im in panels:
 sheet.paste(im,(left,30));d.text((left+8,8),name+' - actual saved mesh edges',fill='white');left+=im.width
sheet.save(out/'mesh-on-artwork.png')
(out/'mesh-on-artwork.json').write_text(json.dumps({'model':str(expected),'model_sha256':hashlib.sha256(expected.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),'object':obj.name,'source_node':'building-025','method':'Actual saved mesh sharp edges (>4degrees), clipped to z>=190, subdivided at <=1/3source pixel and self-visibility tested. Original35degree camera. No target-corner trace is drawn. Neighbor objects are not occluders in this wall-only audit.','sharp_edges':edge_count,'visible_edge_segments':len(segments),'segments_source_pixels':segments},indent=2)+'\n')
print('Saved v10 mesh overlays:',len(segments),'visible segments; no blend saved')
