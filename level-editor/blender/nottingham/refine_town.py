"""Measured town geometry corrections with stable source ownership.

The green shop has five dark clerestory openings between two roof slopes.
Their depth and concealed backing are conservative reconstruction choices.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
TAG = 'nottingham_town_clerestory_v1'
ASSET = 'nottingham-west-green-shop'


def native_point(point, height):
    return Vector((point['x'], -point['y'] / math.sin(math.radians(35)),
                   height / math.cos(math.radians(35))))


def refine_architecture(asset_id):
    if asset_id == 'nottingham-southeast-road-props':
        return refine_platform(asset_id)
    if asset_id == 'nottingham-ramp-road-props':
        return refine_well(asset_id)
    if asset_id != ASSET:
        return {'status': 'audited-without-geometry-edit', 'objects': [],
                'limitation': 'Source silhouette reviewed; fine architectural relief remains unresolved.'}
    targets = [o for o in bpy.data.collections['nottingham Working'].all_objects
               if o.type == 'MESH' and o.get('asset_group') == asset_id
               and o.get('source_node') == 'building-083']
    if len(targets) != 1:
        raise ValueError('Expected one owned green-shop clerestory component')
    obj = targets[0]
    if obj.get(TAG):
        return json.loads(obj[TAG])
    path = ROOT / 'level-editor/work/nottingham-refinement/baseline/nottingham.rhp.json'
    native = json.loads(path.read_text())['sight_obstacles'][83]['points']
    points = [native_point(p, p['z_top']) for p in native]
    bottom = [native_point(p, p['z_bottom']) for p in native]
    a, b = points[0], points[3]
    inward = ((points[1] + points[2]) / 2 - (a + b) / 2)
    inward.z = 0
    inward.normalize()
    cuts = [0, .04, .18, .235, .375, .43, .57, .625, .765, .82, .96, 1]
    openings = {1, 3, 5, 7, 9}
    vertices, faces = [], []

    def face(coords):
        start = len(vertices)
        vertices.extend(coords)
        faces.append(tuple(range(start, len(vertices))))

    def at(u, row):
        p = a.lerp(b, u)
        p.z = (bottom[0].lerp(bottom[3], u).z if row == 0 else
               p.z - (9 + 3 * u if row == 1 else 1 + 3 * u if row == 2 else 0)
               / math.cos(math.radians(35)))
        return p

    # Complete the front with five recessed apertures, a continuous sill,
    # lintel and six timber posts. Back panels are intentionally finite-depth.
    for index, (lo, hi) in enumerate(zip(cuts, cuts[1:])):
        for row in range(3):
            quad = [at(lo, row), at(hi, row), at(hi, row + 1), at(lo, row + 1)]
            if index in openings and row == 1:
                recessed = [p + inward * 7 for p in quad]
                face(recessed)
                for j in range(4):
                    k = (j + 1) % 4
                    face([quad[j], quad[k], recessed[k], recessed[j]])
            else:
                face(quad)
    face([at(u, 3) for u in cuts] + [points[2], points[1]])
    face([at(u, 0) for u in reversed(cuts)] + [bottom[1], bottom[2]])
    face([at(0, r) for r in range(4)] + [points[1], bottom[1]])
    face([at(1, r) for r in reversed(range(4))] + [bottom[2], points[2]])
    face([bottom[1], points[1], points[2], bottom[2]])

    matrix = obj.matrix_world.copy()
    before = {'vertices': len(obj.data.vertices), 'faces': len(obj.data.polygons)}
    mesh = bpy.data.meshes.new('Green shop / five clerestory recesses')
    mesh.from_pydata([matrix.inverted() @ v for v in vertices], [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.0001)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    defects = {'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
               'degenerate_faces': sum(f.calc_area() < 1e-7 for f in bm.faces)}
    if any(defects.values()):
        raise ValueError(defects)
    bm.to_mesh(mesh)
    bm.free()
    mesh.uv_layers.new(name='UVMap')
    material = bpy.data.materials.get('Town hidden surface neutral')
    if material is None:
        material = bpy.data.materials.new('Town hidden surface neutral')
        material.diffuse_color = (.32, .32, .32, 1)
    mesh.materials.append(material)
    obj.data = mesh
    report = {'status': 'refined', 'asset_id': asset_id, 'objects': [{
        'source_node': 'building-083', 'before': before,
        'vertices': len(mesh.vertices), 'faces': len(mesh.polygons),
        'repeated_element_count': 5, 'transform_drift': 0, **defects}],
        'source_native_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_anchors': [[1163.0625, 1422.32719], [1252.1862, 1390.85649]],
        'changes': ['Five real clerestory recesses; eight-pixel aperture height with 1–4 pixel lintel offset measured along the source edge.',
                    'Replaced separated prism triangles with one closed coherent component.'],
        'inference': ['Seven world-unit recess depth and concealed backing are inferred.',
                      'No traversable attic or unseen internal room is claimed.']}
    obj[TAG] = json.dumps(report)
    obj['geometry_source_evidence'] = 'Five visible clerestory openings; measured roof edge and timber rhythm'
    return report


def refine(asset_id):
    """Repair subpixel face seams without changing canonical object ownership."""
    report = refine_architecture(asset_id)
    if asset_id in {'nottingham-east-round-house', 'nottingham-east-boarded-house',
                    'nottingham-upper-green-house', 'nottingham-northeast-timber-house'}:
        report['limitation'] = ('Coincident cover components require their measured offsets; '
                               'welding changed source-visible ownership, so geometry is retained.')
        return report
    repairs = []
    for obj in bpy.data.collections['nottingham Working'].all_objects:
        if obj.type != 'MESH' or obj.get('asset_group') != asset_id:
            continue
        tag = 'nottingham_town_seams_v1'
        if obj.get(tag):
            repairs.append(json.loads(obj[tag]))
            continue
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        before = {'vertices': len(bm.verts), 'faces': len(bm.faces),
                  'boundary_edges': sum(e.is_boundary for e in bm.edges)}
        # Imported independent face corners have subpixel offsets. Welding
        # their common positions closes visible light leaks in oblique views.
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.45)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=.00001)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        after = {'vertices': len(bm.verts), 'faces': len(bm.faces),
                 'boundary_edges': sum(e.is_boundary for e in bm.edges)}
        if before == after:
            bm.free()
            continue
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        repair = {'source_node': obj.get('source_node'), 'before': before,
                  'after': after, 'maximum_merge_distance_world': .45,
                  'transform_drift': 0,
                  'limitation': 'Open authored lower boundaries retained; no unseen caps inferred.'}
        obj[tag] = json.dumps(repair)
        repairs.append(repair)
    report['seam_repairs'] = repairs
    if repairs:
        report['status'] = 'refined'
        report.setdefault('changes', []).append(
            'Welded separated face corners within 0.45 world units to close subpixel cracks; existing open boundaries retained.')
    return report


def refine_platform(asset_id):
    """Recover the plainly visible raised timber frame and stair treads."""
    targets = {o.get('source_node'): o for o in bpy.data.collections['nottingham Working'].all_objects
               if o.type == 'MESH' and o.get('asset_group') == asset_id}
    if set(targets) != {'building-057', 'building-058'}:
        raise ValueError('Unexpected platform ownership')
    tag = 'nottingham_platform_frame_v1'
    if targets['building-058'].get(tag):
        return json.loads(targets['building-058'][tag])
    native = json.loads((ROOT / 'level-editor/work/nottingham-refinement/baseline/nottingham.rhp.json').read_text())['sight_obstacles']
    reports = []
    for node in ('building-057', 'building-058'):
        obj = targets[node]
        points = native[int(node[-3:])]['points']
        vertices, faces = [], []

        def box(coords):
            offset = len(vertices)
            vertices.extend(coords)
            faces.extend(tuple(offset+i for i in f) for f in
                         [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])

        def beam(a, b, width):
            axis = (b-a).normalized()
            side = axis.cross(Vector((0,0,1)))
            if side.length < .01:
                side = axis.cross(Vector((1,0,0)))
            side.normalize()
            up = axis.cross(side).normalized()
            ring = [side*x*width/2 + up*y*width/2 for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
            box([p+d for p in (a,b) for d in ring])

        if node == 'building-058':
            bottom = [native_point(p,p['z_bottom']) for p in points]
            top = [native_point(p,p['z_top']) for p in points]
            box(bottom+top)
            # Two tall front uprights are directly measured in the image.
            # Rear feet complete the support system but are largely concealed.
            front_left = Vector((1671.2,-1697/math.sin(math.radians(35)),0))
            front_right = Vector((1717,-1684/math.sin(math.radians(35)),0))
            beam(front_left,front_left+Vector((0,0,97/math.cos(math.radians(35)))),3.8)
            beam(front_right,front_right+Vector((0,0,90/math.cos(math.radians(35)))),3.8)
            for p in [top[0],top[3]]:
                beam(Vector((p.x,p.y,0)),p,3.6)
            for height in (61,70,79):
                a = front_left+Vector((0,0,height/math.cos(math.radians(35))))
                b = front_right+Vector((0,0,(height-6)/math.cos(math.radians(35))))
                # Individual board thickness follows visible horizontal gaps.
                d = Vector((0,0,7/math.cos(math.radians(35))))
                inset = Vector((0,2,0))
                box([a,b,b+d,a+d,a+inset,b+inset,b+d+inset,a+d+inset])
            for i,j in [(0,1),(1,2),(2,3),(3,0)]:
                beam(top[i]-Vector((0,0,3)),top[j]-Vector((0,0,3)),3)
        else:
            low = [native_point(points[i],0) for i in (0,1)]
            high = [native_point(points[i],30.001001) for i in (3,2)]
            for i in range(5):
                lo = .10 + .90*i/5
                hi = .10 + .90*(i+1)/5
                z = 30.001001*(i+1)/5/math.cos(math.radians(35))
                quad = [low[0].lerp(high[0],lo),low[1].lerp(high[1],lo),
                        low[1].lerp(high[1],hi),low[0].lerp(high[0],hi)]
                for p in quad:p.z=z
                box([p-Vector((0,0,2.0)) for p in quad]+quad)
            for a,b in zip(low,high):beam(a,b-Vector((0,0,2.5)),2.8)
        mesh = bpy.data.meshes.new(node+' / timber structure')
        inverse = obj.matrix_world.inverted()
        mesh.from_pydata([inverse@p for p in vertices],[],faces)
        mesh.update()
        bm = bmesh.new();bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        defects = {'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
                   'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
        if any(defects.values()):raise ValueError(defects)
        bm.to_mesh(mesh);bm.free()
        mesh.uv_layers.new(name='UVMap')
        for material in obj.data.materials:mesh.materials.append(material)
        obj.data=mesh
        reports.append({'source_node':node,'vertices':len(mesh.vertices),'faces':len(mesh.polygons),
                        'transform_drift':0,**defects})
    report={'status':'refined','asset_id':asset_id,'objects':reports,
            'changes':['Added two source-visible tall frame posts, three separated crossboards, platform support feet and perimeter framing.',
                       'Replaced the stair ramp with five separate wooden treads and two supporting stringers.'],
            'inference':['Rear support feet and timber depth are conservative hidden-structure inferences.',
                         'Stair tread spacing follows five visible broad tread bands; individual plank irregularities remain source texture.']}
    targets['building-058'][tag]=json.dumps(report)
    return report


def refine_well(asset_id):
    targets = {o.get('source_node'): o for o in bpy.data.collections['nottingham Working'].all_objects
               if o.type == 'MESH' and o.get('asset_group') == asset_id}
    if set(targets) != {'building-102','building-103','building-104'}:
        raise ValueError('Unexpected covered-well ownership')
    obj=targets['building-102']
    tag='nottingham_covered_well_v1'
    if obj.get(tag):return json.loads(obj[tag])
    native=json.loads((ROOT/'level-editor/work/nottingham-refinement/baseline/nottingham.rhp.json').read_text())['sight_obstacles']
    outer=[native_point(p,p['z_top']) for p in native[102]['points']]
    center=sum(outer,Vector())/len(outer)
    inner=[p+(center-p).normalized()*3.5 for p in outer]
    vertices=[];faces=[]
    def face(points):
        n=len(vertices);vertices.extend(points);faces.append(tuple(range(n,len(vertices))))
    for i in range(len(outer)):
        j=(i+1)%len(outer);a,b=outer[i],outer[j];c,d=inner[i],inner[j]
        aa,bb=Vector((a.x,a.y,0)),Vector((b.x,b.y,0))
        cc,dd=Vector((c.x,c.y,1)),Vector((d.x,d.y,1))
        face([a,b,d,c]);face([aa,bb,b,a]);face([c,d,dd,cc]);face([aa,cc,dd,bb])
    def beam(a,b,width):
        axis=(b-a).normalized();side=axis.cross(Vector((0,0,1)))
        if side.length<.01:side=axis.cross(Vector((1,0,0)))
        side.normalize();up=axis.cross(side).normalized()
        ring=[side*x*width/2+up*y*width/2 for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        q=[p+d for p in (a,b) for d in ring]
        for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:face([q[i] for i in f])
    posts=[]
    for p in native[103]['points'][2:]:
        low=native_point(p,15);high=native_point(p,53)
        beam(low,high,2.8);posts.append(native_point(p,38))
    beam(*posts,2.1)
    midpoint=(posts[0]+posts[1])/2
    beam(midpoint,Vector((midpoint.x,midpoint.y,3)),.55)
    mesh=bpy.data.meshes.new('Ramp well / open curb and canopy supports')
    inverse=obj.matrix_world.inverted();mesh.from_pydata([inverse@p for p in vertices],[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces))
    defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
    if any(defects.values()):raise ValueError(defects)
    bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='UVMap')
    for material in obj.data.materials:mesh.materials.append(material)
    obj.data=mesh
    report={'status':'refined','asset_id':asset_id,'objects':[{'source_node':'building-102',
            'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'transform_drift':0,**defects}],
            'changes':['Opened the stone well curb and added two canopy uprights, a transverse axle and descending rope.'],
            'inference':['Concealed inner shaft depth, 3.5-world-unit curb thickness and timber cross-sections are conservative inferences.',
                         'Canopy ridge endpoints constrain support alignment; existing roof outline retained.']}
    obj[tag]=json.dumps(report);return report
