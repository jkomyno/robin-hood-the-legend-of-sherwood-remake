"""Measured southern crenels, stair flights, and roof shells for worker copies."""
import math

TAG = 'leicester-south-structures-v1'
SINE, COSINE = math.sin(math.radians(35)), math.cos(math.radians(35))

# Source-pixel edge anchors and notch intervals, counted on the covered artwork.
# Turret corner notches may straddle an adjacent edge; their locations are not
# continued around unseen rear parapets.
CUTS = {
    110: [((862.2,1276.3),(953.8,1306.6),0,[(908,920)])],
    112: [((471.3,1148.4),(595.5,1030.5),0,[(495,501),(522,528),(548,554),(575,581)]),
          ((480.1,1195.9),(523.7,1210.2),0,[(477,485)]),
          ((523.7,1210.2),(578.3,1207.8),0,[(523,537)]),
          ((578.3,1207.8),(608.7,1192.3),0,[(580,593)]),
          ((608.7,1192.3),(702.4,1226.5),0,[(623,635),(664,676)])],
    111: [((1166.1,1384.6),(1263.3,1414.8),0,[(1193,1205),(1236,1248)]),
          ((1274.9,1429.1),(1329.1,1443.0),0,[(1276,1288),(1321,1336)]),
          ((1329.1,1443.0),(1384.8,1431.4),0,[(1378,1389)]),
          ((1402.0,1410.4),(1403.8,1381.1),1,[(1390,1400)])],
    118: [((1411.8,1364.8),(1477.6,1301.6),0,[(1415,1421),(1438,1445),(1461,1468)])],
}
STAIRS = {122: {'faces':(-2,-1),'count':12,'visible':4},
          125: {'faces':(-2,-1),'count':10,'visible':4}}
ROOFS = {114:2,151:2,152:2,153:1,154:1,155:1,156:1,157:2,159:2}


def project(p):
    return (p.x,-p.y*SINE-p.z*COSINE)


def neutral_mesh(obj, vertices, faces, name):
    import bpy
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.uv_layers.new(name='UVMap')
    material = bpy.data.materials.get('Leicester source-unknown masonry')
    if material is None:
        material = bpy.data.materials.new('Leicester source-unknown masonry')
        material.diffuse_color = (.38,.38,.38,1)
        material.use_nodes = True
        material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (.38,.38,.38,1)
    mesh.materials.append(material)
    obj.data = mesh
    return mesh


def topology(obj):
    import bmesh
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bad = sum(not e.is_manifold for e in bm.edges)
    degenerate = sum(f.calc_area() < 1e-8 for f in bm.faces)
    bm.free()
    if bad or degenerate:
        raise RuntimeError(f'{obj.name}: {bad} nonmanifold edges, {degenerate} degenerate faces')
    return {'vertices':len(obj.data.vertices),'faces':len(obj.data.polygons),
            'nonmanifold_edges':bad,'degenerate_faces':degenerate}


def cap_prism(obj, *, thickness=None, face_count=None):
    """Extrude the actual top footprint, preserving concave curtain outlines."""
    import bmesh
    from mathutils import Vector
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    high, low = max(p.z for p in points), min(p.z for p in points)
    if face_count:
        faces = list(obj.data.polygons)[-face_count:]
    else:
        faces = [f for f in obj.data.polygons if all(abs(points[i].z-high)<.2 for i in f.vertices)]
    if not faces:
        raise RuntimeError('Missing measured top surfaces: '+obj.name)
    bm = bmesh.new()
    indices = {i for face in faces for i in face.vertices}
    vertices = {i:bm.verts.new(points[i]) for i in indices}
    for face in faces:
        bm.faces.new([vertices[i] for i in face.vertices])
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.5)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-5)
    boundary = [e for e in bm.edges if e.is_boundary]
    extrusion = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces)+boundary)
    lowered = [v for v in extrusion['geom'] if isinstance(v,bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=lowered, vec=Vector((0,0,-thickness if thickness else low-high)))
    inverse = obj.matrix_world.inverted()
    for vertex in bm.verts:
        vertex.co = inverse @ vertex.co
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    mesh = neutral_mesh(obj, [], [], obj.name+' / closed surfaces')
    bm.to_mesh(mesh); bm.free()
    if not mesh.uv_layers:
        mesh.uv_layers.new(name='UVMap')
    return topology(obj)


def crenels(obj, specifications):
    import bpy
    from mathutils import Vector
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    top = max(p.z for p in points)
    top_points = [p for p in points if abs(p.z-top)<.2]
    edges = []
    for a,b,axis,intervals in specifications:
        def closest(pixel):
            result = min(top_points,key=lambda p:math.dist(project(p),pixel))
            if math.dist(project(result),pixel)>2:
                raise RuntimeError('Measured wall anchor moved: '+str(pixel))
            return result
        edges.append((closest(a),closest(b),axis,intervals))
    cap_prism(obj)
    cutters, report = [], []
    for a,b,axis,intervals in edges:
        pa,pb = project(a),project(b)
        direction = b-a
        length = Vector((direction.x,direction.y,0)).length
        if length < 1:
            raise RuntimeError('Degenerate measured wall span')
        for left,right in intervals:
            ta,tb = sorted(((left-pa[axis])/(pb[axis]-pa[axis]),(right-pa[axis])/(pb[axis]-pa[axis])))
            if not -.25 < ta < tb < 1.25:
                raise RuntimeError('Notch exceeds reviewed wall corner')
            center = a.lerp(b,(ta+tb)/2); center.z = top+20
            bpy.ops.mesh.primitive_cube_add(size=1, location=center)
            cutter = bpy.context.object; cutters.append(cutter)
            cutter.hide_render = True
            cutter.rotation_euler.z = math.atan2(direction.y,direction.x)
            cutter.dimensions = (length*(tb-ta),50,92)
            bpy.context.view_layer.update()
            bpy.context.view_layer.objects.active = obj
            modifier = obj.modifiers.new('Measured crenel','BOOLEAN')
            modifier.operation='DIFFERENCE'; modifier.solver='EXACT'; modifier.object=cutter
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            report.append({'source_axis':axis,'interval':[left,right],'notch_depth':26})
    result = topology(obj)
    for cutter in cutters:
        bpy.data.objects.remove(cutter,do_unlink=True)
    return {**result,'notches':report,'visible_notch_count':len(report)}


def stairs(obj, definition):
    import bmesh
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    faces = [list(obj.data.polygons)[i] for i in definition['faces']]
    corners = sorted({i for f in faces for i in f.vertices})
    if len(corners)!=4:
        raise RuntimeError('Expected a four-corner stair ramp')
    ordered = sorted([points[i] for i in corners],key=lambda p:p.z)
    low = sorted(ordered[:2],key=lambda p:p.x); high = ordered[2:]
    if sum((low[i]-high[i]).length_squared for i in range(2)) > sum((low[i]-high[1-i]).length_squared for i in range(2)):
        high.reverse()
    base = sum(p.z for p in low)/2; top = sum(p.z for p in high)/2
    count = definition['count']; rise = (top-base)/count
    bottom = min(p.z for p in points)
    profile = [(0,bottom)]
    for step in range(count):
        profile.extend(((step/count,base+(step+1)*rise),((step+1)/count,base+(step+1)*rise)))
    profile.append((1,bottom))
    vertices = []
    inverse = obj.matrix_world.inverted()
    for a,b in zip(low,high):
        for t,z in profile:
            p=a.lerp(b,t);p.z=z;vertices.append(inverse@p)
    n=len(profile)
    faces=[tuple(range(n)),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    mesh=neutral_mesh(obj,vertices,faces,obj.name+' / stepped support')
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    return {**topology(obj),'steps':count,'source_visible_upper_risers':definition['visible'],
            'rise':rise,'limitation':'Lower continuation concealed by adjacent roofs is inferred; verify visible phase in fixed cameras.'}


def dormer_contact(obj, main_roof):
    """Trim the imported ground-height dormer skirts to the measured roof plane."""
    import bpy
    import bmesh
    from mathutils import Vector
    roof_face = main_roof.data.polygons[-1]
    a,b,c = [main_roof.matrix_world @ main_roof.data.vertices[i].co for i in roof_face.vertices]
    normal = (b-a).cross(c-a)
    if abs(normal.z)<1:
        raise RuntimeError('Dormer support roof is not a usable height plane')
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    x0,x1=min(p.x for p in points)-10,max(p.x for p in points)+10
    y0,y1=min(p.y for p in points)-10,max(p.y for p in points)+10
    xy=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    vertices=[(x,y,-20) for x,y in xy]
    vertices.extend((x,y,a.z-(normal.x*(x-a.x)+normal.y*(y-a.y))/normal.z) for x,y in xy)
    mesh=bpy.data.meshes.new('Dormer measured roof half-space')
    mesh.from_pydata(vertices,[],[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    cutter=bpy.data.objects.new('Dormer roof contact cutter',mesh)
    bpy.context.scene.collection.objects.link(cutter);cutter.hide_render=True
    bm=bmesh.new();bm.from_mesh(obj.data)
    # Each imported dormer half is a convex wedge with duplicated face islands.
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.5)
    bmesh.ops.delete(bm,geom=list(bm.faces),context='FACES_ONLY')
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    loose=[e for e in bm.edges if not e.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context='EDGES')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
    bpy.context.view_layer.objects.active=obj
    modifier=obj.modifiers.new('Measured supporting roof','BOOLEAN')
    modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    result=topology(obj)
    bpy.data.objects.remove(cutter,do_unlink=True)
    return {**result,'support_source_node':'building-105',
            'roof_plane_source_pixels':[[939.0,1314.4],[993.1,1103.7],[1209.2,1175.3]],
            'limitation':'Concealed dormer underside closes at the measured main roof plane.'}


def refine(asset_id):
    import bpy
    collection=bpy.data.collections['Leicester Working']
    targets=[o for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')==asset_id and not o.hide_render]
    if not targets:raise RuntimeError('Missing owned asset')
    report=[]
    main_roof=next((o for o in targets if o.get('source_node')=='building-105'),None)
    # Capture targets before Boolean helper removal invalidates collection caches.
    for obj in targets:
        node=int(obj['source_node'].split('-')[-1])
        if obj.get('south_structure_refinement')==TAG:continue
        matrix=obj.matrix_world.copy()
        if node in CUTS: result=crenels(obj,CUTS[node]);kind='crenels'
        elif node in STAIRS: result=stairs(obj,STAIRS[node]);kind='stairs'
        elif node in ROOFS: result=cap_prism(obj,thickness=3,face_count=ROOFS[node]);kind='roof-shell'
        elif node in (106,107): result=dormer_contact(obj,main_roof);kind='dormer-roof-contact'
        else:continue
        if obj.matrix_world!=matrix:raise RuntimeError('Structure transform drift')
        obj['south_structure_refinement']=TAG
        report.append({'source_node':obj['source_node'],'kind':kind,'transform_drift':0,**result})
    if not report and not any(o.get('south_structure_refinement')==TAG for o in targets):
        raise RuntimeError('This asset has no authored southern structure recipe')
    return {'tag':TAG,'asset_id':asset_id,'changes':report,'reused':not report,
            'approval':'pending','lighting':'unchanged','source_back_surfaces':'neutral unknown'}
