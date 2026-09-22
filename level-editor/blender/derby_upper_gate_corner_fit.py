"""Fit reviewed gate merlon side planes to explicit source pixel corners.

Source x equals model world x for this orthographic camera. Keep elevations,
receivers, covers and source ownership intact; remap only the upper cut bands.
"""
import bpy
import bmesh
import math
from mathutils import Vector

# Explicit surveyed exposed front-facing edges; no regular-spacing generator.
RUNS = {
    'rear': dict(nodes=[256,264], floor=276.2,
        old=[571,589,609,628,649,668,689,708,729,742],
        new=[577,594,612,629,646,664,681,698,715,733],
        corners=[[577,1282],[577,1303],[594,1301],[594,1279],
                 [612,1278],[612,1300],[629,1298],[629,1276],
                 [646,1275],[646,1297],[664,1295],[664,1273],
                 [681,1272],[681,1294],[698,1292],[698,1271],
                 [715,1269],[715,1292],[733,1291],[733,1268]]),
    'front': dict(nodes=[257,263], floor=270.5,
        old=[590,606,625,640,659,675,693,710],
        new=[588,608,626,644,662,679,697,713],
        corners=[[588,1353],[588,1369],[608,1368],[608,1349],
                 [626,1348],[626,1367],[644,1366],[644,1346],
                 [662,1345],[662,1365],[679,1364],[679,1343],
                 [697,1342],[697,1363],[713,1361],[713,1341]]),
    'west': dict(nodes=[250], floor=176.5,
        old=[505,520,536,552], new=[505,522,540,560],
        corners=[[505,1395],[505,1412],[522,1414],[522,1398],
                 [540,1399],[540,1417],[560,1418],[560,1402]]),
}

EAST_CORNERS=[[756.014,1394.213],[798,1385],[798,1379],[816,1374],
              [816,1388],[830,1381],[830,1368],[851,1360],[854.754,1365.425]]

def east_profile():
    obj=next(o for o in bpy.data.collections['Derby Working'].objects
             if o.type=='MESH' and not o.hide_render and o.get('source_node')=='building-251')
    pts=[obj.matrix_world@v.co for v in obj.data.vertices]
    outer=[pts[i] for i in (1,2,3)];inner=[pts[i] for i in (0,5,4)]
    def y_at(x,path):
        segment=next(((a,b) for a,b in zip(path,path[1:]) if a.x<=x<=b.x),
                     (path[0],path[1]) if x<path[0].x else (path[-2],path[-1]))
        a,b=segment;return a.y+(b.y-a.y)*(x-a.x)/(b.x-a.x)
    front=[];back=[]
    for x,sy in EAST_CORNERS:
        y=y_at(x,outer);z=(-y*math.sin(math.radians(35))-sy)/math.cos(math.radians(35))
        front.append(Vector((x,y,z)));back.append(Vector((x,y_at(x,inner),z)))
    bottom=min(p.z for p in pts)
    for row in (front,back):row.extend([Vector((row[-1].x,row[-1].y,bottom)),Vector((row[0].x,row[0].y,bottom))])
    n=len(front);verts=front+back
    faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new('East battlement / traced source corners');mesh.from_pydata(verts,[],faces)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    defects=dict(nonmanifold=sum(not e.is_manifold for e in bm.edges),degenerate=sum(f.calc_area()<1e-7 for f in bm.faces))
    if any(defects.values()):raise ValueError(defects)
    bm.to_mesh(mesh);bm.free()
    for mat in obj.data.materials:mesh.materials.append(mat)
    mesh.uv_layers.new(name='UVMap');mesh.attributes.new('reprojection_fallback_material','INT','FACE')
    obj.data=mesh
    from mathutils import Matrix
    obj.matrix_world=Matrix.Identity(4)
    obj['upper_gate_corner_fit']='east-source-profile-v1'
    return dict(object=obj.name,source_corners=EAST_CORNERS,**defects)

def interpolate(x, old, new):
    for i in range(len(old)-1):
        if old[i] <= x <= old[i+1]:
            t=(x-old[i])/(old[i+1]-old[i])
            return new[i]*(1-t)+new[i+1]*t
    return x

def refine():
    changes=[]
    for run, spec in RUNS.items():
        ids={f'building-{n:03}' for n in spec['nodes']}
        for obj in bpy.data.collections['Derby Working'].objects:
            if obj.type!='MESH' or obj.hide_render or obj.get('source_node') not in ids:
                continue
            if obj.get('reveal_component_role')=='removable-cover':
                continue
            if obj.get('upper_gate_corner_fit'):
                raise ValueError('Corner fit already applied')
            world=obj.matrix_world; inverse=world.inverted()
            points=[world@v.co for v in obj.data.vertices]
            lo=min(p.x for p in points);hi=max(p.x for p in points)
            # Fixed wall endpoints prevent changes at neighboring joins.
            pairs=[(lo,lo)]+[(a,b) for a,b in zip(spec['old'],spec['new']) if lo<a<hi]+[(hi,hi)]
            old,new=zip(*pairs); changed=0
            for vertex,p in zip(obj.data.vertices,points):
                # Smoothly join the lower masonry; upper notch side planes
                # receive the complete measured correction.
                weight=max(0,min(1,(p.z-(spec['floor']-12))/12))
                x=interpolate(p.x,old,new)
                if weight and abs(x-p.x)>1e-6:
                    p.x += (x-p.x)*weight;vertex.co=inverse@p;changed+=1
            obj.data.update()
            obj['upper_gate_corner_fit']='source-corners-v1'
            changes.append(dict(object=obj.name,run=run,changed_vertices=changed))
    return changes
