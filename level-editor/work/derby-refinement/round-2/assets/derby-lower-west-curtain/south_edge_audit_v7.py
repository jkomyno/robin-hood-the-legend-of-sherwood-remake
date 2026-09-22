"""Read actual saved south wall edges and show source-trace correspondences."""
import sys,json,math
from pathlib import Path
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages']
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
out=root/'inspection/south-corner-fit-v7'
source=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
s,c=math.sin(math.radians(35)),math.cos(math.radians(35))
toward=Vector((0,-c,s))
proof=json.loads((out/'geometry.json').read_text())
def project(p):return (p.x,-p.y*s-p.z*c)
for record in proof['walls']:
    node=record['node']
    box=(320,1812,387,1978) if node=='building-023' else (390,2115,520,2245)
    original=source.crop(box).resize(((box[2]-box[0])*6,(box[3]-box[1])*6),Image.Resampling.NEAREST)
    panels=[]
    for version,path in [('before',root/'inspection/complete-wall-candidate-v5/model.blend'),('after',out/'model.blend')]:
        bpy.ops.wm.open_mainfile(filepath=str(path))
        obj=next(o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH' and o.get('source_node')==node and not o.hide_render)
        mesh=obj.data;world=[obj.matrix_world@v.co for v in mesh.vertices]
        mesh.calc_loop_triangles();tree=BVHTree.FromPolygons(world,[list(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
        adj={tuple(sorted(e.vertices)):[] for e in mesh.edges}
        for f in mesh.polygons:
            for pair in f.edge_keys:adj[tuple(sorted(pair))].append(f)
        image=original.copy();draw=ImageDraw.Draw(image)
        def pixel(q):return ((q[0]-box[0]+.5)*6,(q[1]-box[1]+.5)*6)
        for e in mesh.edges:
            a,b=[world[i] for i in e.vertices]
            if min(a.z,b.z)<190:continue
            fs=adj[tuple(sorted(e.vertices))]
            if len(fs)!=2 or abs(fs[0].normal.dot(fs[1].normal))>.9999:continue
            transform=obj.matrix_world.to_3x3().inverted().transposed()
            if not any((transform@f.normal).normalized().dot(toward)>.02 for f in fs):continue
            for i in range(12):
                p=a.lerp(b,i/12);q=a.lerp(b,(i+1)/12);mid=(p+q)/2
                hit,_,_,_=tree.ray_cast(mid+toward*1000,-toward,1001)
                if hit is not None and (hit-mid).length<.25:draw.line((pixel(project(p)),pixel(project(q))),fill=(255,40,70),width=1)
        image.save(out/f'{node}-{version}-edges.png');panels.append(image)
    observed=original.copy();draw=ImageDraw.Draw(observed)
    corners=sorted(record['correspondences'],key=lambda p:p['id'])
    draw.line([pixel(p['observed']) for p in corners],fill='cyan',width=1)
    for p in corners:
        x,y=pixel(p['observed']);draw.ellipse((x-2,y-2,x+2,y+2),fill='yellow');draw.text((x+4,y-7),str(p['id']),fill='white')
    observed.save(out/f'{node}-source-corners.png')
    original.save(out/f'{node}-source.png')
    strip=Image.new('RGB',(original.width*3,original.height+26),'black')
    for i,(name,panel) in enumerate(zip(['Unmodified source','v5 mesh edges','v7 mesh edges'],[original]+panels)):
        strip.paste(panel,(i*original.width,26));ImageDraw.Draw(strip).text((i*original.width+5,6),name,fill='white')
    strip.save(out/f'{node}-comparison.png')
