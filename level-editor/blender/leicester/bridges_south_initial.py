"""Reconstruct the slanted raised south leaf from its measured endpoint silhouette."""
import json, math
from pathlib import Path

def rebuild(obj, native, inventory_file):
    from mathutils import Vector
    from bridges import object_mesh, world, SINE, COSINE
    from bridges_hardware import bitmap, profile
    deck=native['sight_obstacles'][390]['points']
    left,right=world(deck[2]),world(deck[3]);axis=(right-left).normalized()
    # The raised timber rests against the gate's outer attachment edge, while
    # the lowered collision deck terminates inside the stone threshold.
    raised=native['sight_obstacles'][391]['points']
    a,b=raised[2],raised[1]
    def raised_depth(x):return a['y']+(x-a['x'])*(b['y']-a['y'])/(b['x']-a['x'])
    hinge_height=deck[2]['z_top']
    left=Vector((730.,-(raised_depth(730.)+2.)/SINE,hinge_height/COSINE))
    right=Vector((806.,-(raised_depth(806.)+2.)/SINE,hinge_height/COSINE))
    axis=(right-left).normalized()
    outward=((world(deck[1])-world(deck[2]))+(world(deck[0])-world(deck[3])))/2
    outward-=axis*outward.dot(axis)
    length=outward.length;outward.normalize()
    # The painted upper-left corner is x715, compared with its measured lower-left hinge x730.
    # This determines the horizontal component of the same lowered leaf length.
    cosine=(715.-left.x)/(outward.x*length)
    if not 0<cosine<1:raise ValueError('Raised endpoint does not fit the measured hinge')
    angle=math.acos(cosine)
    direction=outward*cosine+Vector((0,0,1))*math.sin(angle)
    normal=axis.cross(direction).normalized()
    inventory_file=Path(inventory_file);inventory=json.loads(inventory_file.read_text())
    mask=next(m for m in inventory['masks'] if m['index']==458)
    path=Path(mask['png']);path=path if path.is_absolute() else inventory_file.parent/path
    w,h,pixels=bitmap(path);mx,my=mask['box_top_left'];rows=[]
    for row in range(h):
        xs=[mx+x for x in range(w) if pixels[((h-1-row)*w+x)*4]>.5]
        if xs:rows.append((my+row,min(xs),max(xs)))
    contour=profile(rows)
    down=Vector((0,-SINE,-COSINE));toward=Vector((0,-COSINE,SINE))
    front=[]
    for x,y in contour:
        origin=Vector((x,0,0))+down*y
        front.append(origin+toward*((left-origin).dot(normal)/toward.dot(normal)))
    thickness=5.25/COSINE
    # Put all reverse thickness behind the source-facing measured surface.
    if normal.dot(toward)<0:normal=-normal
    vertices=front+[p-normal*thickness for p in front];n=len(front)
    faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    replacement=object_mesh(obj.name+' slanted replacement',vertices,faces,obj,obj.users_collection[0])
    old=obj.data;obj.data=replacement.data;replacement.data=old
    import bpy
    bpy.data.objects.remove(replacement,do_unlink=True)
    obj['south_initial_slanted_leaf']=True
    return {'angle_above_horizontal_degrees':math.degrees(angle),'angle_from_vertical_degrees':90-math.degrees(angle),
        'hinge_world':[list(left),list(right)],'hinge_basis':'Raised native attachment edge plus 2-unit timber clearance; painted lower corners x730/806; applied geometry unchanged','lowered_leaf_length_world':length,
        'source_outline':contour,'native_mask':458,'thickness_world':thickness,
        'source_supported':'Measured endpoint outer silhouette and upper-left corner; hinge and physical length constrained by unchanged applied leaf.',
        'inference':'A rigid planar leaf interpolates painted edge irregularities; concealed timber thickness follows lowered slab thickness.'}
