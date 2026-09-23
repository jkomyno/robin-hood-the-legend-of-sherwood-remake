"""Per-opening original pixels, picked corners and independently read mesh edges."""
import sys,json,math
from pathlib import Path
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages']
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent;out=root/'inspection/south-vertical-v12'
(out/'openings').mkdir(parents=True,exist_ok=True)
observations=json.loads((root/'south_cap_source_v12.json').read_text())
(out/'source-correspondences.json').write_text(json.dumps(observations,indent=2)+'\n')
source=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s))
def project(p):return (p.x,-p.y*s-p.z*c)
report=['# Every source-visible south opening\n',
'Each row shows untouched source pixels, the manually picked near/far/floor constraints, and actual edges read from the saved model in the original camera. Yellow = near crown, cyan = far crown, red = floor constraint. Right-side floors are often hidden and inferred from the visible depth; source picks are approximate by about2px. The final panel contains no landmark dots.\n']
for node,rows in observations['corners'].items():
    obj=next(o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH' and o.get('source_node')==node and not o.hide_render)
    mesh=obj.data;points=[obj.matrix_world@v.co for v in mesh.vertices];mesh.calc_loop_triangles()
    tree=BVHTree.FromPolygons(points,[list(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
    adj={tuple(sorted(e.vertices)):[] for e in mesh.edges}
    for f in mesh.polygons:
        for pair in f.edge_keys:adj[tuple(sorted(pair))].append(f)
    segments=[]
    for edge in mesh.edges:
        a,b=[points[i] for i in edge.vertices]
        if min(a.z,b.z)<195:continue
        fs=adj[tuple(sorted(edge.vertices))]
        if len(fs)!=2 or abs(fs[0].normal.dot(fs[1].normal))>.9999:continue
        for j in range(24):
            p=a.lerp(b,j/24);q=a.lerp(b,(j+1)/24);mid=(p+q)/2
            hit,_,_,_=tree.ray_cast(mid+toward*1000,-toward,1001)
            if hit is not None and (hit-mid).length<.3:segments.append([project(p),project(q)])
    for i in range(0,len(rows),2):
        pts=[p for row in rows[i:i+2] for p in row]
        box=(min(p[0] for p in pts)-7,min(p[1] for p in pts)-7,max(p[0] for p in pts)+8,max(p[1] for p in pts)+8)
        scale=8;raw=source.crop(box).resize(((box[2]-box[0])*scale,(box[3]-box[1])*scale),Image.Resampling.NEAREST)
        picked=raw.copy();actual=raw.copy();dp=ImageDraw.Draw(picked);da=ImageDraw.Draw(actual)
        def xy(p):return ((p[0]-box[0]+.5)*scale,(p[1]-box[1]+.5)*scale)
        for j,row in enumerate(rows[i:i+2]):
            dp.line((xy(row[0]),xy(row[1])),fill='cyan',width=1);dp.line((xy(row[0]),xy(row[2])),fill='yellow',width=1)
            for k,(p,color) in enumerate(zip(row,['yellow','cyan','red'])):
                x,y=xy(p);dp.ellipse((x-2,y-2,x+2,y+2),fill=color);dp.text((x+3,y-10),f'{j+1}.{k+1}',fill='white')
        for a,b in segments:da.line((xy(a),xy(b)),fill=(255,40,70),width=1)
        strip=Image.new('RGB',(raw.width*3,raw.height+28),'black');d=ImageDraw.Draw(strip)
        for k,(name,panel) in enumerate(zip(['Original pixels','Picked landmarks','Saved mesh edges'],[raw,picked,actual])):
            strip.paste(panel,(k*raw.width,28));d.text((k*raw.width+5,6),name,fill='white')
        name=f'{node}-opening-{i//2+1:02d}.png';strip.save(out/'openings'/name)
        report += [f'## {node}, opening {i//2+1}\n',f'![Source, landmarks, actual mesh](openings/{name})\n']
    box=(320,1812,388,1978) if node=='building-023' else (390,2118,531,2246)
    scale=6;raw=source.crop(box).resize(((box[2]-box[0])*scale,(box[3]-box[1])*scale),Image.Resampling.NEAREST)
    overlay=raw.copy();draw=ImageDraw.Draw(overlay)
    def xy(p):return ((p[0]-box[0]+.5)*scale,(p[1]-box[1]+.5)*scale)
    for a,b in segments:draw.line((xy(a),xy(b)),fill=(255,40,70),width=1)
    raw.save(out/f'{node}-source.png');overlay.save(out/f'{node}-actual-overlay.png')
    (out/f'{node}-actual-segments.json').write_text(json.dumps(segments)+'\n')
(out/'opening-audit.md').write_text('\n'.join(report))
