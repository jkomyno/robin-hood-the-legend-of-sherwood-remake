"""Measured rear crenellation and front corbel profile for the southern gate."""
from pathlib import Path
import hashlib
import json
import math

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
AUDIT=WORK/'fortifications-audit/south-arch-user-revision'
# Near/front cap edge, not the farther brown cap silhouette. Source-pixel
# uncertainty is two pixels; obscured ends are explicitly unscored inference.
CROWN=[(1245.1923,2020.0,'hidden end',False),(1266,2021,'visible cap',True),
 (1294,2022,'notch shoulder',True),(1294,2032,'notch floor',True),
 (1309,2033,'notch floor',True),(1309,2022.5,'notch shoulder',True),
 (1337,2023.5,'notch shoulder',True),(1337,2033.5,'notch floor',True),
 (1350,2034,'notch floor',True),(1350,2024,'notch shoulder',True),
 (1379,2025,'notch shoulder',True),(1379,2035,'notch floor',True),
 (1394,2035.5,'notch floor',True),(1394,2025.5,'notch shoulder',True),
 (1418,2026,'visible cap',True),(1432.4999,2026.5,'hidden end',False)]
# This lower row is three projecting white corbels, not another battlement run.
# The cap shoulders are observed separately rather than imposed periodically.
CORBELS=[(1286.8634,2069,'hidden start',False),(1292,2069,'cap foot',True),
 (1292,2059,'cap back shoulder',True),(1300,2059,'cap step',True),
 (1300,2064,'cap step',True),(1305,2064,'cap front shoulder',True),
 (1305,2069,'cap foot',True),(1335,2070,'cap foot',True),
 (1335,2060,'cap back shoulder',True),(1345,2060,'cap step',True),
 (1345,2065,'cap step',True),(1348,2065,'cap front shoulder',True),
 (1348,2070,'cap foot',True),(1378,2072,'cap foot',True),
 (1378,2062,'cap back shoulder',True),(1383.2523,2062,'ownership boundary',False)]

def source_evidence():
    from PIL import Image,ImageDraw
    AUDIT.mkdir(parents=True,exist_ok=True)
    source=WORK/'source-states/covered.png';image=Image.open(source).convert('RGB')
    records=[]
    for node,run,corners,box,scale in [(205,'rear battlement near cap edge',CROWN,(1238,2003,1440,2050),5),
            (213,'front white corbel cap outline',CORBELS,(1278,2048,1395,2093),7)]:
        raw=image.crop(box);raw.save(AUDIT/f'{node}-source.png')
        v=raw.resize((raw.width*scale,raw.height*scale),Image.Resampling.NEAREST);draw=ImageDraw.Draw(v)
        pts=[((x-box[0])*scale,(y-box[1])*scale)for x,y,_,_ in corners]
        draw.line(pts,fill='cyan',width=2)
        for i,((x,y),(_,_,role,visible)) in enumerate(zip(pts,corners)):
            draw.ellipse((x-3,y-3,x+3,y+3),fill='yellow'if visible else'orange')
            draw.text((x+3,y-14 if i%2 else y+5),str(i),fill='white')
        canvas=Image.new('RGB',(v.width,v.height*2+30),'#242424');canvas.paste(raw.resize(v.size,Image.Resampling.NEAREST));canvas.paste(v,(0,v.height+30));ImageDraw.Draw(canvas).text((5,v.height+5),f'{node}: numbered measured near edge; orange hidden/unscored',fill='white');canvas.save(AUDIT/f'{node}-numbered-source.png')
        records.append(dict(source_node=f'building-{node:03}',run=run,crop_origin=box[:2],
            corners=[dict(index=i,source_pixel=[x,y],role=role,confidence='measured ±2 native pixels'if vis else'inferred boundary',visible=vis)for i,(x,y,role,vis)in enumerate(corners)]))
    payload=dict(version=1,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),runs=records,
        measured_rear_notches=3,measured_front_corbels=3,
        limitation='The third front corbel continues into adjacent masonry outside source213. Its owned portion terminates at the canonical boundary; no neighboring mesh is edited.')
    (AUDIT/'numbered-corners.json').write_text(json.dumps(payload,indent=2)+'\n')
    return payload

def refine():
    import bpy,bmesh
    from mathutils import Vector
    native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles']
    objects={o.get('source_node'):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'}
    anchors=json.loads((WORK/'fortifications-audit/measurements.json').read_text())['south_arch']['inner_arch_anchors_source']
    reports=[]
    for node,corners in [(205,CROWN),(213,CORBELS)]:
        obj=objects[f'building-{node:03}'];points=native[node]['points'];yfront=max(p['y']for p in points);yback=min(p['y']for p in points)
        top=[(x,yfront-y)for x,y,_,_ in corners]
        if node==205:
            bottom=[(top[0][0],points[0]['z_bottom']),(top[-1][0],points[0]['z_bottom'])]
        else:
            # Preserve the previously measured eleven-point arch aperture.
            bottom=[(top[0][0],yfront-anchors[0][1])]+[(x,yfront-y)for x,y in anchors if top[0][0]<x<top[-1][0]]+[(top[-1][0],yfront-anchors[-1][1])]
        profile=top+list(reversed(bottom));count=len(profile)
        world=[Vector((x,-y/math.sin(math.radians(35)),z/math.cos(math.radians(35))))for y in[yback,yfront]for x,z in profile]
        faces=[tuple(reversed(range(count))),tuple(range(count,2*count))]+[(i,(i+1)%count,(i+1)%count+count,i+count)for i in range(count)]
        mesh=bpy.data.meshes.new(obj.name+' / measured crown');inverse=obj.matrix_world.inverted();mesh.from_pydata([inverse@v for v in world],[],faces);mesh.update()
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-7 for f in bm.faces)
        if bad or deg:raise ValueError((node,bad,deg))
        volume=bm.calc_volume(signed=True);bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='UVMap')
        for material in obj.data.materials:mesh.materials.append(material)
        obj.data=mesh;obj['source_projection_current']=False
        actual=[]
        for i,(x,y,role,visible)in enumerate(corners):
            v=world[count+i];source=[v.x,-v.y*math.sin(math.radians(35))-v.z*math.cos(math.radians(35))]
            actual.append(dict(index=i,source_pixel=source,target=[x,y],visible=visible,error=math.dist(source,[x,y])))
        reports.append(dict(source_node=f'building-{node:03}',vertices=len(mesh.vertices),faces=len(mesh.polygons),nonmanifold_edges=bad,degenerate_faces=deg,signed_volume=volume,front_corner_projection=actual))
    report=dict(version=1,recipe='measured-south-gate-arch-v1',changed_nodes=['building-205','building-213'],unchanged_arch_walkway='building-214',
        measured_rear_notches=3,front_corbel_count=3,objects=reports,world_transform_drift=0,
        changes=['Fit three rear crown openings to numbered source shoulders and notch floors; preserve measured nonuniform widths and slight height slope.',
                 'Replace false front crenels with the three source white corbel cap profiles while preserving the pointed arch aperture.'],
        limitations=['Hidden rear cap edge follows the native10.886-unit wall thickness; hidden terminal crown portions continue adjacent measured cap slopes.',
                     'Front corbel caps use the native8.6642-unit depth as a conservative solid hypothesis; the third cap continues outside the owned boundary.',
                     'Corner residuals are construction checks against the chosen artwork targets, not independent proof of those targets.'])
    return report

if __name__=='__main__':
    print(json.dumps(source_evidence()))
