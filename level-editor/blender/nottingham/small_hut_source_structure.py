"""Measured forge supports and symmetric flared hood for renewed geometry review."""
import math
from mathutils import Vector
from refine_village_secondary import replace,mesh_for,digest
S=math.sin(math.radians(35)); C=math.cos(math.radians(35))

def repair(objects):
    import bpy
    a=objects['building-282']; b=objects['building-283']; body=objects['building-281']; chimney=objects['building-284']
    reports=[]
    body_vertices=[body.matrix_world@v.co for v in body.data.vertices]
    for p in body_vertices:
        if p.z<1:p.z-=2.5
        if p.x>441.9:p.x+=.75
    body_before=digest(body);body.data=body.data.copy();inverse=body.matrix_world.inverted()
    for vertex,point in zip(body.data.vertices,body_vertices):vertex.co=inverse@point
    body.data.update()
    reports.append(dict(object=body.name,before_sha256=body_before,after_sha256=digest(body),change='Lower source-visible masonry base 2.5 and extend right outline .75; preserve inherited topology exactly.'))
    # End elevations follow the three visible feet, rather than forcing the
    # sloping local ground to the map's global zero plane.
    anchors=[('front left',357.0,-5027.366211,2847,2889.5,3.5),
             ('front right',409.5,-5058.05127,2862,2905,3.5),
             ('rear right',450.0,-4977.524414,2817,2861.5,3.5)]
    u=Vector((.883,-.469,0));v=Vector((.469,.883,0));verts=[];faces=[]
    def box_ring(center,lo,hi,r):
        start=len(verts)
        for z in [lo,hi]:
            for du,dv in [(-1,-1),(1,-1),(1,1),(-1,1)]:
                p=center+u*r*du+v*r*dv;p.z=z;verts.append(p)
        faces.extend([tuple(start+i for i in [3,2,1,0]),tuple(start+i for i in [4,5,6,7])])
        for i in range(4):j=(i+1)%4;faces.append((start+i,start+j,start+j+4,start+i+4))
    landmarks=[]
    for name,x,y,top,foot,r in anchors:
        lo=(-foot-y*S)/C;hi=(-top-y*S)/C
        box_ring(Vector((x,y,0)),lo,hi,r)
        landmarks.append(dict(name=name,source_top=[x,top],source_foot=[x,foot],section_half_width=r,world_base=lo))
    # Front left eave beam runs between the visible left post and front roof
    # break. Its concealed square section follows the observed timber depth.
    p=Vector((355.5,-5027.366211,42));q=Vector((381.8,-5041.104,39.5))
    axis=(q-p).normalized();side=Vector((-axis.y,axis.x,0))*3.5
    start=len(verts)
    for z in [-3.5,3.5]:
        verts.extend([p-side+Vector((0,0,z)),q-side+Vector((0,0,z)),q+side+Vector((0,0,z)),p+side+Vector((0,0,z))])
    faces.extend([tuple(start+i for i in [3,2,1,0]),tuple(start+i for i in [4,5,6,7])])
    for i in range(4):j=(i+1)%4;faces.append((start+i,start+j,start+j+4,start+i+4))
    obj=bpy.data.objects.new('Forge / source-visible support posts and eave beam',bpy.data.meshes.new('Forge supports placeholder'))
    body.users_collection[0].objects.link(obj)
    for key in body.keys():obj[key]=body[key]
    obj.parent=body.parent;obj.matrix_world=body.matrix_world.copy();obj['projection_component']='source-visible supports'
    obj.data,valid=mesh_for(obj,verts,faces,obj.name)
    reports.append(dict(component=obj.name,source_node=obj['source_node'],validation=valid,landmarks=landmarks,geometry_sha256=digest(obj),inference=['Square timber sections and hidden beam backs are inferred; top and foot elevations follow visible artwork.','Feet follow the local sloping ground and may lie below the global zero plane.']))
    # Add a symmetric lower flare beneath the chimney shaft. The opening remains hollow; the shaft and rim widen symmetrically
    # to cover their measured source silhouette.
    cv=[chimney.matrix_world@v.co for v in chimney.data.vertices]
    center=sum(cv[4:8],Vector())/4
    lower=[]
    for p in cv[4:8]:
        n=center+(p-center)*1.85;n.z=75;lower.append(n)
    upper=[center+(p-center)*1.3 for p in cv[4:8]]
    topcenter=sum(cv[8:12],Vector())/4
    top=[topcenter+(p-topcenter)*1.08 for p in cv[8:12]]
    rings=[cv[:4],lower,upper,top,cv[12:16],cv[16:20]]
    new=[p for ring in rings for p in ring];ff=[(3,2,1,0)]
    for k in range(5):
        for i in range(4):j=(i+1)%4;ff.append((k*4+i,k*4+j,(k+1)*4+j,(k+1)*4+i))
    ff.append((20,21,22,23))
    report=replace(chimney,new,ff,'Forge chimney / symmetric source-fitted lower hood')
    report['inference']=['Symmetric lower hood flare interpolates the visible outline; the shaft and outer rim widen symmetrically, while the hollow inner opening retains its approved coordinates.']
    reports.append(report)
    return reports
