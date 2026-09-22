"""Actual saved cap/shoulder/floor edges; no model-derived source landmarks."""
import sys,json,math
from pathlib import Path
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages']
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent;out=root/'inspection/south-cap-fit-v9'
source=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s))
def project(p):return (p.x,-p.y*s-p.z*c)
for node,box in [('building-023',(320,1812,388,1978)),('building-042',(390,2118,531,2246))]:
    raw=source.crop(box).resize(((box[2]-box[0])*6,(box[3]-box[1])*6),Image.Resampling.NEAREST)
    panels=[]
    for version,path in [('v7',root/'inspection/south-corner-fit-v7/model.blend'),('v9',out/'model.blend')]:
        bpy.ops.wm.open_mainfile(filepath=str(path))
        obj=next(o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH' and o.get('source_node')==node and not o.hide_render)
        mesh=obj.data;points=[obj.matrix_world@v.co for v in mesh.vertices];mesh.calc_loop_triangles()
        tree=BVHTree.FromPolygons(points,[list(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
        adj={tuple(sorted(e.vertices)):[] for e in mesh.edges}
        for f in mesh.polygons:
            for pair in f.edge_keys:adj[tuple(sorted(pair))].append(f)
        image=raw.copy();draw=ImageDraw.Draw(image)
        def pixel(q):return ((q[0]-box[0]+.5)*6,(q[1]-box[1]+.5)*6)
        for edge in mesh.edges:
            a,b=[points[i] for i in edge.vertices]
            if min(a.z,b.z)<195:continue
            fs=adj[tuple(sorted(edge.vertices))]
            if len(fs)!=2 or abs(fs[0].normal.dot(fs[1].normal))>.9999:continue
            for i in range(16):
                p=a.lerp(b,i/16);q=a.lerp(b,(i+1)/16);mid=(p+q)/2
                hit,_,_,_=tree.ray_cast(mid+toward*1000,-toward,1001)
                if hit is not None and (hit-mid).length<.3:draw.line((pixel(project(p)),pixel(project(q))),fill=(255,40,70),width=1)
        image.save(out/f'{node}-{version}-edges.png');panels.append(image)
    strip=Image.new('RGB',(raw.width*3,raw.height+28),'black')
    for i,(name,panel) in enumerate(zip(['Unmodified source','Rejected v7 edges','Rebuilt v9 edges'],[raw]+panels)):
        strip.paste(panel,(i*raw.width,28));ImageDraw.Draw(strip).text((i*raw.width+5,6),name,fill='white')
    strip.save(out/f'{node}-comparison.png')
