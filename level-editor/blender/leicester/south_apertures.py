"""Source-camera openings for the south gatehouse candidate.

Call ``refine()`` after the native cover partition, save/reload the worker,
then regenerate projection and all covered/revealed review cameras. This helper
does not render, save, change transforms, or grant geometry approval.
"""
import hashlib
import json
import math

TAG = 'leicester-south-apertures-v1'
GROUP = 'leicester-south-gatehouse'
ELEVATION = 35.0

# Pixel coordinates refer to the full 3136 x 1984 covered Day artwork.
# Recess silhouettes include the dark opening; bright surrounding masonry is
# retained. Subpixel depth behind these visible contours is inferred.
WINDOWS = (
    ('front-west', 139, ((713, 1183), (727.5, 1188), (727.5, 1195.5), (713, 1200))),
    ('front-middle', 139, ((761.5, 1199), (776, 1203.5), (776, 1212.5), (761.5, 1216))),
    ('front-east', 139, ((809.5, 1215.5), (824, 1220), (824, 1228.5), (809.5, 1232))),
    ('right-upper', 140, ((886, 1203), (893, 1197), (893, 1211), (886, 1218))),
)


def portal_contour():
    """Round arch in its wall plane, with the screen-space wall slope kept."""
    left, right = 740.0, 803.0
    spring_left, spring_right = 1340.0, 1361.0
    rise = 31.0
    result = [(left, 1391.0), (right, 1412.0), (right, spring_right)]
    for step in range(1, 25):
        theta = math.pi * step / 24
        x = (left + right) / 2 + (right - left) / 2 * math.cos(theta)
        y = spring_left + (spring_right - spring_left) * (x-left)/(right-left)
        result.append((x, y-rise*math.sin(theta)))
    return result


def _signature(obj):
    data = {
        'vertices': [list(v.co) for v in obj.data.vertices],
        'faces': [list(p.vertices) for p in obj.data.polygons],
        'matrix': [list(row) for row in obj.matrix_world],
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def _clean(obj, allow_convex=False):
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        before = (len(bm.verts), len(bm.faces))
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.5 if allow_convex else 1e-4)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-6)
        bm.verts.index_update()
        seen, duplicates = set(), []
        for face in bm.faces:
            key = tuple(sorted(v.index for v in face.verts))
            if key in seen:
                duplicates.append(face)
            seen.add(key)
        if duplicates:
            bmesh.ops.delete(bm, geom=duplicates, context='FACES_ONLY')
        convex = False
        if any(not edge.is_manifold for edge in bm.edges) and allow_convex:
            # These two lower pier receivers are convex slabs. Closing their
            # imported face islands does not introduce a new visible outline.
            bmesh.ops.delete(bm, geom=list(bm.faces), context='FACES_ONLY')
            bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
            loose = [e for e in bm.edges if not e.link_faces]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context='EDGES')
            loose = [v for v in bm.verts if not v.link_edges]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context='VERTS')
            convex = True
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bad = sum(not e.is_manifold for e in bm.edges)
        degenerate = sum(f.calc_area() < 1e-8 for f in bm.faces)
        if bad or degenerate or not bm.faces:
            raise RuntimeError(f'{obj.name}: invalid aperture topology {bad=}, {degenerate=}')
        report = {'vertices_before': before[0], 'faces_before': before[1],
                  'vertices': len(bm.verts), 'faces': len(bm.faces),
                  'convex_pier_closure': convex, 'nonmanifold_edges': bad,
                  'degenerate_faces': degenerate}
        bm.to_mesh(obj.data)
        return report
    finally:
        bm.free()


def _prism(collection, name, contour):
    import bpy
    import bmesh
    sine, cosine = math.sin(math.radians(ELEVATION)), math.cos(math.radians(ELEVATION))
    vertices = [(x, -y/sine-depth*cosine, depth*sine)
                for depth in (-10000.0, 10000.0) for x, y in contour]
    n = len(contour)
    faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    faces += [(i, (i+1) % n, (i+1) % n+n, i+n) for i in range(n)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.hide_render = True
    return obj


def refine():
    import bpy
    collection = bpy.data.collections.get('Leicester Working')
    if collection is None:
        raise RuntimeError('Missing Leicester Working collection')
    all_meshes = [o for o in collection.all_objects if o.type == 'MESH']
    source_nodes = {f'building-{n:03}' for n in (137, 139, 140, 146)}
    targets = [o for o in all_meshes if not o.hide_render and
               o.get('asset_group') == GROUP and o.get('source_node') in source_nodes]
    if {o.get('source_node') for o in targets} != source_nodes:
        raise RuntimeError('Expected current front/right walls and both lower gate piers')
    if all(o.get('south_apertures') == TAG for o in targets):
        return {'tag': TAG, 'reused': True, 'objects': len(targets)}
    if any(o.get('south_apertures') for o in targets):
        raise RuntimeError('Mixed aperture revisions; restart from the pre-aperture worker')
    if not any(o.get('projection_component') == 'removable-cover' for o in targets):
        raise RuntimeError('Run the gatehouse cover partition before apertures')
    outside = {o.name: _signature(o) for o in all_meshes if o not in targets}
    originals = {o: o.data for o in targets}
    matrices = {o: o.matrix_world.copy() for o in targets}
    before = {o: _signature(o) for o in targets}
    cutters, report, affected = [], [], {}
    try:
        for obj in targets:
            obj.data = obj.data.copy()
            _clean(obj, allow_convex=obj.get('source_node') in ('building-137', 'building-146'))
        plans = [(name, {f'building-{node:03}'}, list(contour))
                 for name, node, contour in WINDOWS]
        plans.append(('round-arched-portal', {'building-137', 'building-139', 'building-146'}, portal_contour()))
        for label, nodes, contour in plans:
            cutter = _prism(collection, 'Gatehouse aperture / '+label, contour)
            cutters.append(cutter)
            changed = []
            for obj in targets:
                if obj.get('source_node') not in nodes:
                    continue
                old = _signature(obj)
                modifier = obj.modifiers.new('Source aperture '+label, 'BOOLEAN')
                modifier.operation = 'DIFFERENCE'
                modifier.solver = 'EXACT'
                modifier.object = cutter
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.modifier_apply(modifier=modifier.name)
                obj.select_set(False)
                _clean(obj)
                if _signature(obj) != old:
                    changed.append({'source_node': obj.get('source_node'),
                                    'component': obj.get('projection_component', 'whole')})
            if not changed:
                raise RuntimeError('Source aperture misses all selected wall components: '+label)
            affected[label] = changed
        for obj in targets:
            if obj.matrix_world != matrices[obj]:
                raise RuntimeError('Aperture recipe changed object transform')
            topology = _clean(obj)
            if not obj.data.uv_layers:
                obj.data.uv_layers.new(name='UVMap')
            report.append({'source_node': obj.get('source_node'),
                           'component': obj.get('projection_component', 'whole'),
                           'geometry_before': before[obj], 'geometry_after': _signature(obj),
                           'topology': topology, 'transform_drift': 0})
        for obj in all_meshes:
            if obj.name in outside and _signature(obj) != outside[obj.name]:
                raise RuntimeError('Outside geometry changed: '+obj.name)
        for obj in targets:
            obj['south_apertures'] = TAG
            obj['south_apertures_projection'] = 'stale; regenerate fixed-camera packet'
    except Exception:
        for obj, mesh in originals.items():
            obj.data = mesh
        raise
    finally:
        for cutter in cutters:
            mesh = cutter.data
            bpy.data.objects.remove(cutter, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
    return {'tag': TAG, 'reused': False, 'objects': report, 'affected': affected,
            'outside_objects_preserved': len(outside), 'transform_drift': 0,
            'measured_windows': [{'name': n, 'source_node': f'building-{s:03}', 'contour': list(c)}
                                 for n, s, c in WINDOWS],
            'portal_contour': portal_contour(), 'portal_arc_segments': 24,
            'counts': {'front_upper_apertures': 3, 'right_upper_apertures': 1, 'portal': 1},
            'source_evidence': 'Covered Day artwork; gatehouse crop [650,1050,940,1500]; native patch004 separates removable upper shell and native patch010 owns the moving bridge.',
            'limitations': ['Camera-ray depth and inner reveal thickness are inferred; inspect reverse views.',
                            'Small aperture contours and portal spring positions require source-camera overlay inspection before readiness.',
                            'The statue niche and two narrow flanking slots are not changed by this helper.',
                            'Save/reload before projection to discard stale collection references after Boolean cutters.'],
            'geometry_approval': 'pending', 'projection_status': 'stale'}
