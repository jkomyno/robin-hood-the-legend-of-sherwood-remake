"""Per-opening original pixels, picked corners and independently read mesh edges."""
import sys,json,math
from pathlib import Path
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages']
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent;out=root/'inspection/south-vertical-v13'
(out/'openings').mkdir(parents=True,exist_ok=True)
observations=json.loads((root/'south_cap_source_v13.json').read_text())
labels={}
for node,rows in observations['corners'].items():
    labels[node]=['Source-visible traced opening']*(len(rows)//2)
def add(node,a,b,label):
    observations['corners'][node].extend([a,b]);labels[node].append(label)
# These continuation stations fill the spans formerly omitted from the recipe.
# Occluded positions are marked as continuation estimates, not visible picks.
for lo,hi in [(1960,1970),(1979,1989),(1998,2008),(2017,2027),(2036,2046),(2055,2065)]:
    def row(y):
        x=359.849+(y-1918.514)*(375.132-359.849)/(2065.522-1918.514)
        return [[round(x),y],[round(x+9),y-2],[round(x),y+20]]
    add('building-023',row(lo),row(hi),'Continuous repeat; roof occludes some cap edges')
for a,b in [
    ([[295,1810],[296,1798],[295,1830]],[[310,1811],[310,1799],[310,1831]]),
    ([[265,1800],[275,1795],[265,1820]],[[274,1806],[284,1801],[274,1826]]),
    ([[267,1762],[275,1770],[267,1782]],[[280,1753],[288,1761],[280,1773]]),
    ([[305,1747],[305,1757],[305,1767]],[[319,1749],[319,1759],[319,1769]])]:
    add('building-023',a,b,'Existing turret-end opening retained')
for lo,hi in [(2074,2084),(2094,2104),(2112,2122)]:
    def row(y):
        x=375.135+(y-2065.626)*(386.408-375.135)/(2118.758-2065.626) if y<=2118.758 else 386.408+(y-2118.758)*125/98.234
        return [[round(x),y],[round(x+9),y-5],[round(x),y+20]]
    add('building-042',row(lo),row(hi),'Incoming bend opening; continuous visible parapet')
(out/'source-correspondences.json').write_text(json.dumps(observations,indent=2)+'\n')
source=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s))
def project(p):return (p.x,-p.y*s-p.z*c)
report=['# Every opening across both complete south runs\n',
'Each row shows untouched source pixels, the opening stations, and actual edges read from the saved model in the original camera. Yellow = near crown, cyan = far crown, red = floor. The original seven/six traced openings use source-picked constraints; continuation and retained turret-end openings are explicitly labeled below and use approximate inventory stations. Roof-covered corners are inferred from the continuous repeat, not visible landmarks. The final panel contains actual mesh edges and no landmark dots.\n']
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
        report += [f'## {node}, opening {i//2+1}\n',labels[node][i//2]+'\n',f'![Source, landmarks, actual mesh](openings/{name})\n']
    box=(245,1735,425,2085) if node=='building-023' else (365,2045,540,2250)
    scale=6;raw=source.crop(box).resize(((box[2]-box[0])*scale,(box[3]-box[1])*scale),Image.Resampling.NEAREST)
    overlay=raw.copy();draw=ImageDraw.Draw(overlay)
    def xy(p):return ((p[0]-box[0]+.5)*scale,(p[1]-box[1]+.5)*scale)
    for a,b in segments:draw.line((xy(a),xy(b)),fill=(255,40,70),width=1)
    raw.save(out/f'{node}-source.png');overlay.save(out/f'{node}-actual-overlay.png')
    numbered=raw.copy();nd=ImageDraw.Draw(numbered)
    for i in range(0,len(rows),2):
        a,b=rows[i][0],rows[i+1][0];p=((a[0]+b[0])/2,(a[1]+b[1])/2)
        x,y=xy(p);nd.line((xy(a),xy(b)),fill='cyan',width=2)
        nd.ellipse((x-4,y-4,x+4,y+4),fill='yellow');nd.text((x+8,y-6),str(i//2+1),fill='yellow',stroke_width=1,stroke_fill='black')
    numbered.save(out/f'{node}-numbered-openings.png')
    (out/f'{node}-actual-segments.json').write_text(json.dumps(segments)+'\n')
(out/'opening-audit.md').write_text('\n'.join(report))
