"""Audit saved user-corner vertices/edges and show terminal scene context."""
import sys,json,math,hashlib
from pathlib import Path
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload',
    '/usr/lib/python3.14/site-packages',str(Path(__file__).parent)]
import bpy
from mathutils import Vector
from PIL import Image,ImageDraw
from refinement_review import _tree
from derby_upper_west_validate_saved import main as validate_geometry

def main():
    validate_geometry()
    packet=Path(bpy.data.filepath).parent;fit=json.loads((packet/'user-constraint-fit.json').read_text())
    frozen=json.loads((packet/'user-corners.json').read_text());asset=next(a for a in frozen['assets'] if a['id']=='derby-upper-west-curtain')
    refs={(p['id'],i):target for p in asset['paths'] for i,target in enumerate(p['points'])}
    angle=math.radians(asset['source_camera_elevation']);s,c=math.sin(angle),math.cos(angle)
    results=[];by_path={}
    for row in fit['correspondences']:
        obj=bpy.data.objects[row['object']];v=obj.matrix_world@obj.data.vertices[row['vertex_index']].co
        actual=[v.x,-v.y*s-v.z*c];target=refs[(row['path_id'],row['target_index'])]
        error=math.dist(actual,target);assert error<.001,error
        value={**row,'world':list(v),'projected':actual,'error_pixels':error};results.append(value)
        by_path.setdefault(row['path_id'],[]).append(value)
    obj=bpy.data.objects[results[0]['object']];edges={tuple(sorted(e.vertices)) for e in obj.data.edges}
    segments=[]
    for path,rows in by_path.items():
        rows.sort(key=lambda r:r['target_index'])
        for a,b in zip(rows,rows[1:]):
            pair=tuple(sorted((a['vertex_index'],b['vertex_index'])))
            assert pair in edges,(path,a['target_index'],pair)
            segments.append(dict(path_id=path,start=a['target_index'],end=b['target_index'],vertices=pair,direct_saved_edge=True))
    report=dict(model_sha256=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
        source_constraints_sha256=hashlib.sha256((packet/'user-corners.json').read_bytes()).hexdigest(),
        max_error_pixels=max(r['error_pixels'] for r in results),correspondences=results,segments=segments)
    (packet/'saved-user-constraint-verification.json').write_text(json.dumps(report,indent=2))
    source=Image.open(asset['image_path']).convert('RGB');box=asset['crop'];scale=3
    art=source.crop(box).resize(((box[2]-box[0])*scale,(box[3]-box[1])*scale),Image.Resampling.NEAREST)
    overlay=art.copy();draw=ImageDraw.Draw(overlay)
    for path,rows in by_path.items():
        rows.sort(key=lambda r:r['target_index'])
        def points(key):return[((r[key][0]-box[0])*scale,(r[key][1]-box[1])*scale) for r in rows]
        draw.line(points('target'),fill=(55,255,200),width=5)
        draw.line(points('projected'),fill=(255,30,40),width=1)
    overlay.save(packet/'modified/user-vs-saved-mesh.png')
    comparison=Image.new('RGB',(art.width*2,art.height+30),'#202020');comparison.paste(art,(0,30));comparison.paste(overlay,(art.width,30))
    draw=ImageDraw.Draw(comparison);draw.text((8,8),'Untouched artwork',fill='white');draw.text((art.width+8,8),'User (wide mint) / saved mesh (thin red)',fill='white')
    comparison.save(packet/'modified/user-mesh-comparison.png')
    all_objects=[o for o in bpy.data.collections['Derby Working'].all_objects if o.type=='MESH' and not o.hide_render]
    tree,owners,_=_tree(all_objects);toward=Vector((0,-c,s));sun=Vector((-.4916794601,-.4538579920,.7431448255)).normalized()
    def srgb(value):return round(255*(12.92*value if value<=.0031308 else 1.055*value**(1/2.4)-.055))
    for name,bounds in [('upper-contact',(175,890,290,1015)),('lower-terminal',(375,1340,490,1460))]:
        left,top,right,bottom=bounds;enlarge=3;width=(right-left)*enlarge;height=(bottom-top)*enlarge
        solid=Image.new('RGB',(width,height));pix=solid.load()
        for y in range(height):
            for x in range(width):
                p=Vector((left+(x+.5)/enlarge,-(top+(y+.5)/enlarge)/s,0))
                hit,normal,index,distance=tree.ray_cast(p+toward*10000,-toward,20000)
                if hit is None:continue
                blocked=normal.dot(sun)>0 and tree.ray_cast(hit+sun*.03,sun)[0] is not None
                value=.16+(0 if blocked else .64*max(0,normal.dot(sun)));v=srgb(value);pix[x,y]=(v,v,v)
        raw=source.crop(bounds).resize((width,height),Image.Resampling.NEAREST)
        panel=Image.new('RGB',(width*2,height+30),'#202020');panel.paste(raw,(0,30));panel.paste(solid,(width,30))
        d=ImageDraw.Draw(panel);d.text((5,8),'Original artwork',fill='white');d.text((width+5,8),'Actual scene context / 48 degree sun',fill='white')
        panel.save(packet/f'modified/{name}.png')
    print(json.dumps(dict(saved_corners=len(results),direct_saved_edges=len(segments),max_error=report['max_error_pixels'])),flush=True)

if __name__=='__main__':main()
