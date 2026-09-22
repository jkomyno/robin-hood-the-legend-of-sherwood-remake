"""Source-measured secondary rural corrections; regenerate projection after use.

The western bridge receives its missing arch/deck; the handcart gains an open
bed and two wheels; visibly round barrels/pails replace box proxies. Concealed
surfaces are conservative continuations, never newly claimed source pixels.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[3]
SIN=math.sin(math.radians(35)); COS=math.cos(math.radians(35))
TAG='nottingham_village_secondary_v3'
PRIMARY={'nottingham-village-stone-bridge','nottingham-village-low-barn','nottingham-village-dovecote'}
ROUND={247:'pail',248:'barrel',312:'barrel',314:'pail',317:'barrel',318:'horizontal barrel'}


def mill_mound(obj, number):
    """Round the two observed hay-mound halves without moving their anchors."""
    pts=native(number)
    # Both native volumes run from the low outer edge to their shared crest.
    low=(3,2) if number==239 else (0,1)
    high=(0,1) if number==239 else (3,2)
    vertices=[];faces=[];count=12
    for k in range(count+1):
        t=k/count
        for side in range(2):
            a=pts[low[side]];b=pts[high[side]]
            p=point(a,0).lerp(point(b,0),t)
            h=a['z_top']+(b['z_top']-a['z_top'])*math.sin(t*math.pi/2)
            vertices.extend([p,p+Vector((0,0,h/COS))])
    for k in range(count):
        a=4*k;b=a+4
        faces.extend([(a,b,b+2,a+2),(a+1,a+3,b+3,b+1),
                      (a,a+1,b+1,b),(a+2,b+2,b+3,a+3)])
    faces.extend([(0,2,3,1),(4*count,4*count+1,4*count+3,4*count+2)])
    report=replace(obj,vertices,faces,'Mill hay mound / rounded crest')
    report.update({'recipe':'mill-hay-rounded-profile','profile_segments':count,
        'evidence':'village-secondary-audit/mill-measure.png',
        'inference':['The source-visible mound is rounded; intermediate curvature is interpolated between the existing ground footprint and crest anchors.','The mound is hay in front of the arched doorway, not a solid triangular masonry buttress.']})
    return report


def middle_roof(obj, number):
    pts=native(number);p=[point(x,x['z_top']) for x in pts]
    # Rear roof continuation mirrors each measured front eave across its ridge.
    # The three panels share corresponding ridge/eave endpoints.
    rear2=p[2]*2-p[1];rear3=p[3]*2-p[0]
    rear2.z=p[1].z;rear3.z=p[0].z
    ring=[p[0],p[1],rear2,rear3]
    vertices=ring+[Vector((v.x,v.y,0)) for v in ring]+[p[2],p[3]]
    faces=[(0,1,8,9),(9,8,2,3),(0,9,3,7,4),(1,5,6,2,8),
           (0,4,5,1),(3,2,6,7),(4,7,6,5)]
    report=replace(obj,vertices,faces,'Middle cottage / complete two-slope roof and walls')
    report.update({'recipe':'middle-cottage-rear-roof','evidence':'village-audit/nottingham-village-middle-cottage-context.png',
        'inference':['The hidden rear roof mirrors the measured front slope across the ridge; no rear windows or doors are invented.','Rear wall height follows its corresponding observed front eave.']})
    return report


def digest(obj):
    return hashlib.sha256(json.dumps({'v':[list(v.co) for v in obj.data.vertices],
                                     'f':[list(f.vertices) for f in obj.data.polygons]},sort_keys=True).encode()).hexdigest()


def native(number):
    return json.loads((ROOT/'level-editor/work/nottingham-refinement/baseline/nottingham.rhp.json').read_text())['sight_obstacles'][number]['points']


def point(p,height):return Vector((p['x'],-p['y']/SIN,height/COS))


def mesh_for(obj,vertices,faces,label):
    matrix=obj.matrix_world.copy();inverse=matrix.inverted()
    mesh=bpy.data.meshes.new(label);mesh.from_pydata([inverse@Vector(v) for v in vertices],[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces))
    validation={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)}
    if any(validation.values()):raise ValueError((label,validation))
    bm.to_mesh(mesh);bm.free();mesh.update()
    uv=mesh.uv_layers.new(name='Source projection')
    for loop in mesh.loops:
        p=matrix@mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv=(p.x/2304,1-(-p.y*SIN-p.z*COS)/3520)
    material=bpy.data.materials.get('Nottingham rural unobserved neutral')
    if material is None:
        material=bpy.data.materials.new('Nottingham rural unobserved neutral');material.diffuse_color=(.45,.45,.45,1)
    mesh.materials.append(material)
    return mesh,validation


def replace(obj,vertices,faces,label):
    before=digest(obj);mesh,valid=mesh_for(obj,vertices,faces,label);obj.data=mesh
    return {'source_node':obj['source_node'],'component':obj.name,'before_sha256':before,'after_sha256':digest(obj),
            'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'validation':valid,'transform_drift':0}


def closed_envelope(obj,number):
    """Supply missing backs and bottoms at the measured volume anchors."""
    pts=native(number);count=len(pts)
    verts=[point(p,p['z_bottom']) for p in pts]+[point(p,p['z_top']) for p in pts]
    faces=[tuple(reversed(range(count))),tuple(range(count,2*count))]
    faces.extend((j,(j+1)%count,(j+1)%count+count,j+count) for j in range(count))
    report=replace(obj,verts,faces,'Rural measured volume / closed envelope')
    report.update({'recipe':'measured-volume-closure','evidence':f'inventory/crops/building-{number}.png',
        'inference':['Hidden backs, ends and undersides close the measured footprint and height anchors.','The footprint and top profile remain the source-measured volume; masonry courses, woven fence gaps and vegetation detail remain texture-scale evidence.']})
    return report


def rounded(obj,number):
    pts=native(number);base=[point(p,p['z_bottom']) for p in pts]
    center=sum(base,Vector())/4;u=(base[1]-base[0])/2;v=(base[3]-base[0])/2
    bottom=min(p['z_bottom'] for p in pts)/COS;top=max(p['z_top'] for p in pts)/COS
    verts=[];faces=[];count=20
    if number==318:
        axis=v.normalized();side=u.normalized();length=v.length*2
        for f,r in [(0,.84),(.12,.96),(.5,1),(.88,.96),(1,.84)]:
            c=center+axis*((f-.5)*length);c.z=(bottom+top)/2
            for j in range(count):
                a=j*math.tau/count;verts.append(c+side*(math.cos(a)*u.length*r)+Vector((0,0,math.sin(a)*(top-bottom)/2*r)))
    else:
        for f,r in [(0,.86),(.12,.96),(.5,1),(.88,.96),(1,.86)]:
            for j in range(count):
                a=j*math.tau/count;p=center+u*math.cos(a)*r+v*math.sin(a)*r;p.z=bottom+(top-bottom)*f;verts.append(p)
    for k in range(4):
        for j in range(count):a=k*count+j;b=k*count+(j+1)%count;faces.append((a,b,b+count,a+count))
    faces.append(tuple(reversed(range(count))))
    if ROUND[number]=='pail':
        for z in (top,bottom+min(2,(top-bottom)*.15)):
            for j in range(count):
                a=j*math.tau/count;p=center+u*math.cos(a)*.72+v*math.sin(a)*.72;p.z=z;verts.append(p)
        for j in range(count):
            k=(j+1)%count
            faces.extend([(4*count+j,4*count+k,5*count+k,5*count+j),
                          (5*count+j,5*count+k,6*count+k,6*count+j)])
        faces.append(tuple(range(6*count,7*count)))
    else:faces.append(tuple(range(4*count,5*count)))
    report=replace(obj,verts,faces,'Rural '+ROUND[number]+' / curved shell')
    report.update({'recipe':'round-visible-container','radial_segments':count,'evidence':f'inventory/crops/building-{number}.png',
                   'inference':['Concealed rear follows the visible curved wooden body.','Barrel end/bottom closure and intermediate bulge are structural interpolation; no unseen contents are claimed.']})
    return report


def trough(obj, number):
    pts=native(number);bottom=[point(p,p['z_bottom']) for p in pts];top=[point(p,p['z_top']) for p in pts]
    center=sum(bottom,Vector())/4
    inner=[]
    for p in top:
        q=p.copy();q.x=center.x+(p.x-center.x)*.82;q.y=center.y+(p.y-center.y)*.82;inner.append(q)
    floor=[Vector((p.x,p.y,2/COS)) for p in inner]
    verts=bottom+top+inner+floor;faces=[(0,3,2,1),(12,13,14,15)]
    for j in range(4):
        k=(j+1)%4;faces.extend([(j,k,4+k,4+j),(4+j,4+k,8+k,8+j),(8+j,8+k,12+k,12+j)])
    report=replace(obj,verts,faces,'Stone trough / open cavity')
    report.update({'recipe':'open-stone-trough','evidence':f'inventory/crops/building-{number}.png',
                   'inference':['Rim thickness and basin depth are inferred; the visible source shows an open trough.','No water surface or contents are invented.']})
    return report


def haypile(obj):
    pts=native(260);base=[point(p,0) for p in pts];center=sum(base,Vector())/4
    u=(base[1]-base[0])/2;v=(base[3]-base[0])/2
    height=max(p['z_top'] for p in pts)/COS;count=24;verts=[];faces=[]
    for h,r in ((0,.92),(.12,1),(.45,.91),(.73,.67),(.9,.34)):
        for j in range(count):
            a=j*math.tau/count;p=center+u*(math.cos(a)*r)+v*(math.sin(a)*r);p.z=height*h;verts.append(p)
    apex=len(verts);verts.append(center+Vector((0,0,height)))
    faces.append(tuple(reversed(range(count))))
    for k in range(4):
        for j in range(count):n=(j+1)%count;faces.append((k*count+j,k*count+n,(k+1)*count+n,(k+1)*count+j))
    for j in range(count):faces.append((4*count+j,4*count+(j+1)%count,apex))
    report=replace(obj,verts,faces,'Courtyard straw pile / rounded mound')
    report.update({'recipe':'courtyard-straw-mound','evidence':'village-audit/nottingham-village-courtyard-well-context.png',
        'inference':['The asset name is historical; the source depicts straw inside the courtyard rather than a well.','Hidden rear mound profile interpolates the visible rounded heap; individual straw strands remain texture detail.']})
    return report


def boundary_fence(sources):
    """Place observed posts on the measured cliff, preserving their source pixels."""
    from mathutils.bvhtree import BVHTree
    surface_vertices=[];surface_faces=[]
    for obj in sources.values():
        start=len(surface_vertices)
        surface_vertices.extend(obj.matrix_world@v.co for v in obj.data.vertices)
        surface_faces.extend(tuple(start+i for i in f.vertices) for f in obj.data.polygons)
    tree=BVHTree.FromPolygons(surface_vertices,surface_faces)
    # (foot x, foot y, top y), measured in the full-resolution covered artwork.
    rows=[[(2080,3245,3214),(2129,3230,3194),(2186,3220,3189),
           (2235.5,3199,3164),(2285,3173,3140)],
          [(2066.5,3280,3254.5),(2116.5,3293.5,3265),
           (2173.5,3304.5,3280),(2205.5,3330,3305)]]
    verts=[];faces=[];hits=[]
    def beam(a,b,radius):
        axis=(b-a).normalized();u=axis.cross(Vector((0,0,1)))
        if u.length<.001:u=Vector((1,0,0))
        u.normalize();v=axis.cross(u);start=len(verts);count=6
        for p in (a,b):
            for j in range(count):
                angle=math.tau*j/count;verts.append(p+(u*math.cos(angle)+v*math.sin(angle))*radius)
        faces.extend([tuple(start+j for j in reversed(range(count))),tuple(start+count+j for j in range(count))])
        for j in range(count):k=(j+1)%count;faces.append((start+j,start+k,start+count+k,start+count+j))
    for row in rows:
        posts=[]
        for x,y,top_y in row:
            height=1000;origin=Vector((x,(-y-height*COS)/SIN,height))
            hit=tree.ray_cast(origin,Vector((0,COS,-SIN)))
            if hit[0] is None:raise ValueError(f'Fence post has no supporting cliff surface at {(x,y)}')
            foot=hit[0];top=foot+Vector((0,0,(y-top_y)/COS))
            posts.append((foot,top));beam(foot,top,2.1);hits.append({'source_foot':[x,y],'source_top':[x,top_y],'world_foot':list(foot)})
        for first,second in zip(posts,posts[1:]):
            for t in (.32,.78):beam(first[0].lerp(first[1],t),second[0].lerp(second[1],t),1.2)
    source=sources['building-308'];obj=bpy.data.objects.new('Eastern cliff / observed wooden fence',bpy.data.meshes.new('Fence construction placeholder'))
    source.users_collection[0].objects.link(obj)
    for key in source.keys():obj[key]=source[key]
    obj.parent=source.parent;obj.matrix_world=source.matrix_world.copy()
    mesh,valid=mesh_for(obj,verts,faces,obj.name);obj.data=mesh
    obj['projection_component']=obj.name
    return {'source_node':'building-308','component':obj.name,'recipe':'east-cliff-posts-and-rails','posts':len(hits),
        'validation':valid,'transform_drift':0,'geometry_sha256':digest(obj),'source_post_landmarks':hits,
        'evidence':'village-secondary-audit/east-fence-measure.png',
        'inference':['Post feet use first-hit depth on the measured cliff envelope; annotated tops and feet preserve source-camera pixels.','Six-sided post sections, rail thickness and vegetation-concealed front post feet are structural interpolation.','The cliff volume remains present; ownership masks currently validate fence pixels only.']}


def bridge(sources):
    source=sources['building-280']
    # Native front parapet line supplies depth, annotated image supplies arch.
    a=Vector((425.27533,-3046.347/SIN,0));b=Vector((682.6511,-2934.8538/SIN,0))
    def wy(x):return a.y+(b.y-a.y)*(x-a.x)/(b.x-a.x)
    def pixel(x,y):return Vector((x,wy(x),(-y-SIN*wy(x))/COS))
    arch=[(605,2994),(606,2980),(613,2972),(622,2967),(631,2965),(638,2967),(641,2976),(641,2989)]
    lower=[pixel(570,3030),pixel(601,3030)]+[pixel(*p) for p in arch]+[pixel(645,3021),pixel(665,3012)]
    outline=[Vector((570,wy(570),0)),Vector((665,wy(665),0))]+list(reversed(lower));n=len(outline)
    depth=Vector((-31,85,0));verts=outline+[p+depth for p in outline]
    faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    obj=bpy.data.objects.new('Western stream bridge / arch masonry and deck',bpy.data.meshes.new('Bridge construction placeholder'));source.users_collection[0].objects.link(obj)
    for k in source.keys():obj[k]=source[k]
    obj.parent=source.parent;obj.matrix_world=source.matrix_world.copy()
    mesh,valid=mesh_for(obj,verts,faces,obj.name);obj.data=mesh
    obj['projection_component']='Western stream bridge / arch masonry and deck';obj[TAG]='bridge-component'
    return {'source_node':'building-280','component':obj.name,'recipe':'western-stream-bridge-arch','arches':1,'vertices':len(mesh.vertices),'faces':len(mesh.polygons),
            'validation':valid,'transform_drift':0,'arch_landmarks_source_pixels':arch,'geometry_sha256':digest(obj),
            'evidence':'village-secondary-audit/western-bridge-landmarks.png',
            'inference':['Hidden rear arch follows the observed front opening.','Parapet separation sets approximate deck depth; pier bottoms stop near visible masonry above vegetation.','Existing canonical native mask controls projection; unsupported deck pixels stay neutral.']}


def cart(obj):
    pts=native(289);lo=[point(p,p['z_bottom']) for p in pts];hi=[point(p,p['z_top']) for p in pts]
    center=sum(lo,Vector())/4;verts=[];faces=[]
    def solid(poly,offset):
        s=len(verts);n=len(poly);verts.extend(poly+[p+offset for p in poly]);faces.extend([tuple(s+i for i in reversed(range(n))),tuple(s+n+i for i in range(n))]);faces.extend([(s+i,s+(i+1)%n,s+(i+1)%n+n,s+i+n) for i in range(n)])
    solid(lo,Vector((0,0,2)))
    for i in range(4):
        j=(i+1)%4;inward=center-(lo[i]+lo[j])/2;inward.z=0;inward.normalize()
        solid([lo[i]+Vector((0,0,2)),lo[j]+Vector((0,0,2)),hi[j],hi[i]],inward*2)
    longaxis=(lo[3]-lo[0]).normalized();shortaxis=(lo[1]-lo[0]).normalized()
    wheelcenter=center.copy();wheelcenter.z=11/COS;radius=11/COS
    axle_width=(lo[1]-lo[0]).length+6;count=20
    for side in (-1,1):
        c=wheelcenter+shortaxis*side*axle_width/2;ring=[]
        for r in (radius,radius-2.2):
            for j in range(count):a=j*math.tau/count;ring.append(c+longaxis*math.cos(a)*r+Vector((0,0,math.sin(a)*r)))
        start=len(verts);verts.extend(ring+[p+shortaxis*2 for p in ring])
        for j in range(count):
            k=(j+1)%count
            for face in [(j,k,count+k,count+j),(2*count+j,3*count+j,3*count+k,2*count+k),
                         (j,2*count+j,2*count+k,k),(count+j,count+k,3*count+k,3*count+j)]:
                faces.append(tuple(start+i for i in face))
        # Four visible radial beams form eight spokes; hub thickness is inferred.
        for j in range(4):
            a=j*math.pi/4;direction=longaxis*math.cos(a)+Vector((0,0,math.sin(a)));cross=longaxis*(-math.sin(a))+Vector((0,0,math.cos(a)))
            solid([c-direction*radius+cross*.65,c+direction*radius+cross*.65,c+direction*radius-cross*.65,c-direction*radius-cross*.65],shortaxis*2)
    report=replace(obj,verts,faces,'Wooden handcart / open bed and paired wheels')
    report.update({'recipe':'handcart-open-bed-and-wheels','wheels':2,'inference':['Concealed opposite wheel and inner plank thickness follow the visible cart structure.','Eight-spoke rhythm and wheel radius interpolate the low-resolution source; no axle animation is claimed.'],
                   'evidence':'inventory/crops/building-289.png'})
    return report


def refine(asset_id):
    if not asset_id.startswith('nottingham-village-') or asset_id in PRIMARY:raise ValueError('Asset outside secondary village ownership')
    sources={o.get('source_node'):o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==asset_id and not o.hide_render and not o.get('projection_component')}
    if not sources:raise ValueError('Missing secondary village source parts')
    existing=[o for o in sources.values() if o.get(TAG)]
    if existing:
        if asset_id=='nottingham-village-east-boundary' and not any(o.get('projection_component')=='Eastern cliff / observed wooden fence' for o in bpy.context.scene.objects):
            return {'status':'extended','asset_id':asset_id,'objects':[boundary_fence(sources)]}
        return {'status':'existing','asset_id':asset_id,'objects':[json.loads(o[TAG]) for o in existing]}
    reports=[]
    if asset_id=='nottingham-village-stream-wall':
        existing_bridge=next((o for o in bpy.context.scene.objects if o.get('asset_group')==asset_id and o.get('projection_component')=='Western stream bridge / arch masonry and deck'),None)
        if existing_bridge:
            reports.append({'source_node':'building-280','component':existing_bridge.name,'recipe':'western-stream-bridge-arch','status':'existing','geometry_sha256':digest(existing_bridge)})
        else:reports.append(bridge(sources))
    for node,obj in sources.items():
        number=int(node.removeprefix('building-'))
        if number in ROUND:reports.append(rounded(obj,number))
        elif number==289:reports.append(cart(obj))
        elif number in (239,240):reports.append(mill_mound(obj,number))
        elif number in (254,255,256):reports.append(middle_roof(obj,number))
        elif number in (235,320):reports.append(trough(obj,number))
        elif number==260:reports.append(haypile(obj))
        else:reports.append(closed_envelope(obj,number))
    if asset_id=='nottingham-village-east-boundary':reports.append(boundary_fence(sources))
    result={'status':'refined' if reports else 'reviewed-without-geometry-edit','asset_id':asset_id,'objects':reports,'transform_drift':0,
            'projection_status':'stale: rerun modified packet' if reports else 'current; geometry unchanged'}
    if reports:next(iter(sources.values()))[TAG]=json.dumps(result)
    return result
