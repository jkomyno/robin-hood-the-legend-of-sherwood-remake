"""Rear cap trial: alter source-visible runs; retain occluded runs as inherited."""
import bpy,bmesh,json,math,runpy
from pathlib import Path
from mathutils import Vector,Matrix
W=Path(__file__).parent;D=W/'next-zigzag-v3'
subtract=runpy.run_path(str(W.parents[4]/'blender/derby_east_hall.py'))['_subtract']
S=math.sin(math.radians(35));C=math.cos(math.radians(35));TOP=400.5;BASE=376.0
o=next(o for o in bpy.data.collections['Derby Working'].all_objects if o.type=='MESH' and not o.hide_render and o.get('source_node')=='building-185')
world=o.matrix_world;vs=[world@v.co for v in o.data.vertices]
uv=o.data.uv_layers.active
faces=[([(vs[o.data.loops[i].vertex_index].copy(),uv.data[i].uv.copy()) for i in p.loop_indices],p.material_index) for p in o.data.polygons]
before={tuple(round(c,4) for c in p) for p in vs if p.z<BASE-.001}
a=Vector((1365.2279,-1915.7435,TOP));b=Vector((1622.5542,-2210.0918,TOP))
tangent=Vector((b.x-a.x,b.y-a.y,0)).normalized();inward=Vector((tangent.y,-tangent.x,0))
regions=[(1359,1567,[(1368,771,1378,778),(1388,785,1401,793),
                    (1411,800,1424,808),
                    (1434,815,1446,823),(1456,831,1469,838),(1482,847,1494,855),
                    (1505,862,1517,870),
                    (1527,877,1539,885),(1550,892,1562,900)])]
inferred={1411:'Hidden behind roof dormer; conservative continuation, not observed source corners',
          1505:'Hidden behind chimney; conservative continuation, not observed source corners'}
caps=[]
def add(points):faces.append(([(p,Vector((.5,.5))) for p in points],0))
for left,right,merlons in regions:
    planes=[(Vector((-1,0,0)),-left),(Vector((1,0,0)),right),
            (-inward,-inward.dot(a)+2),(inward,inward.dot(a)+25),
            (Vector((0,0,-1)),-BASE)]
    faces=[(piece,material) for polygon,material in faces for piece in subtract(polygon,planes)]
    floor=[]
    for x in [left,right]:
        p=a.lerp(b,(x-a.x)/(b.x-a.x));p.z=BASE;floor.append(p)
    offset=Vector((-6,-5/S,0))
    add([floor[0],floor[1],floor[1]+offset,floor[0]+offset])
    for x0,y0,x1,y1 in merlons:
        p=Vector((x0,(-y0-TOP*C)/S,TOP));q=Vector((x1,(-y1-TOP*C)/S,TOP))
        high=[p,q,q+offset,p+offset]
        low=[Vector((v.x,v.y,BASE)) for v in high]
        add(high)
        for i in range(4):add([low[i],low[(i+1)%4],high[(i+1)%4],high[i]])
        caps.append(dict(source=[[v.x,-v.y*S-v.z*C] for v in high],visible_top_edge=None if x0 in inferred else [[x0,y0],[x1,y1]],
                         evidence=inferred.get(x0,'Observed native-mask source top edge'),
                         depth='Cross-cap displacement [-6,+5] observed on mask boundary; far inner endpoints inferred'))
verts=[];polys=[];uvs=[];mats=[]
for poly,material in faces:
    if len(poly)<3:continue
    polys.append(list(range(len(verts),len(verts)+len(poly))))
    verts.extend(p for p,u in poly);uvs.extend(u for p,u in poly);mats.append(material)
mesh=bpy.data.meshes.new('East Hall rear observed merlons trial');mesh.from_pydata(verts,[],polys)
for material in o.data.materials:mesh.materials.append(material)
layer=mesh.uv_layers.new(name=uv.name)
for loop,value in zip(layer.data,uvs):loop.uv=value
for poly,material in zip(mesh.polygons,mats):poly.material_index=material
bm=bmesh.new();bm.from_mesh(mesh)
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
after={tuple(round(c,4) for c in v.co) for v in bm.verts if v.co.z<BASE-.001}
assert before.issubset(after),'A preserved lower vertex disappeared'
bm.to_mesh(mesh);bm.free();o.data=mesh;o.matrix_world=Matrix.Identity(4)
o['rear_parapet_trial']='Seven observed caps plus two explicitly inferred occluded caps; far turret-covered end inherited'
bpy.ops.wm.save_as_mainfile(filepath=str(D/'front-rear-trial.blend'))
(D/'rear-trial-validation.json').write_text(json.dumps(dict(caps=caps,preserved_lower_vertices=len(before),regions=[[l,r] for l,r,m in regions],state='Trial: inspect cap joins and notch floors; stair turret not corrected'),indent=2))
