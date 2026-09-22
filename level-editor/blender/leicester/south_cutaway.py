"""Split the gatehouse cover using its native camera-space patch boundary."""
import json
import math
from pathlib import Path

PATCH = 'patch-004'
COVER_NODES = (139, 140, 142, 143, 144, 145)
INTERIOR_NODES = (141, 147)
TAG = 'gatehouse-native-cutaway-v2'


def _area(poly):
    return sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(poly, poly[1:]+poly[:1]))/2


def _simplify(points, tolerance=0.8):
    a, b = points[0], points[-1]
    dx, dy = b[0]-a[0], b[1]-a[1]
    norm = math.hypot(dx, dy)
    distances = [abs(dx*(p[1]-a[1])-dy*(p[0]-a[0]))/norm if norm else
                 math.hypot(p[0]-a[0], p[1]-a[1]) for p in points]
    index = max(range(len(points)), key=distances.__getitem__)
    if distances[index] <= tolerance:
        return [a, b]
    return _simplify(points[:index+1], tolerance)[:-1]+_simplify(points[index:], tolerance)


def boundary(path, offset):
    from PIL import Image
    image = Image.open(path).convert('L')
    w, h = image.size
    pixels = image.load()
    edges = {}
    def occupied(x, y):
        return 0 <= x < w and 0 <= y < h and pixels[x, y] > 0
    for y in range(h):
        for x in range(w):
            if not occupied(x, y):
                continue
            for dx, dy, a, b in ((0,-1,(x,y),(x+1,y)),(1,0,(x+1,y),(x+1,y+1)),
                                  (0,1,(x+1,y+1),(x,y+1)),(-1,0,(x,y+1),(x,y))):
                if not occupied(x+dx, y+dy):
                    edges.setdefault(a, []).append(b)
    loops = []
    while edges:
        start = next(iter(edges)); point = start; loop = []
        while True:
            loop.append(point)
            choices = edges[point]
            following = choices.pop()
            if not choices:
                del edges[point]
            point = following
            if point == start:
                break
        loops.append(loop)
    loops.sort(key=lambda p: abs(_area(p)), reverse=True)
    if not loops or any(abs(_area(p)) > 4 for p in loops[1:]):
        raise ValueError('Expected one connected gatehouse cover without holes')
    poly = loops[0]
    split = max(range(len(poly)), key=lambda i: math.dist(poly[0], poly[i]))
    poly = _simplify(poly[:split+1])[:-1]+_simplify(poly[split:]+[poly[0]])[:-1]
    if _area(poly) < 0:
        poly.reverse()
    return [(x+offset[0], y+offset[1]) for x, y in poly]


def _clip(poly, a, b, inside=True):
    def value(p):
        result = (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
        return result if inside else -result
    if not poly:
        return []
    result = []
    previous = poly[-1]; pv = value(previous)
    for point in poly:
        cv = value(point)
        if (pv >= 0) != (cv >= 0):
            t = pv/(pv-cv)
            result.append([x+(y-x)*t for x, y in zip(previous, point)])
        if cv >= 0:
            result.append(point)
        previous, pv = point, cv
    return result


def partition(poly, triangles):
    retained, covered = [poly], []
    for triangle in triangles:
        next_retained = []
        for fragment in retained:
            remainder = fragment
            for a, b in zip(triangle, triangle[1:]+triangle[:1]):
                outside = _clip(remainder, a, b, False)
                if len(outside) >= 3 and abs(_area(outside)) > 1e-6:
                    next_retained.append(outside)
                remainder = _clip(remainder, a, b)
                if len(remainder) < 3:
                    break
            if len(remainder) >= 3 and abs(_area(remainder)) > 1e-6:
                covered.append(remainder)
        retained = next_retained
    return retained, covered


def refine(workspace):
    import bpy
    import bmesh
    from mathutils import Vector
    from mathutils.geometry import tessellate_polygon
    from refinement_workspace import initialize_working_projection
    workspace = Path(workspace)
    path = Path(initialize_working_projection(workspace))
    manifest = json.loads(path.read_text())
    patch = next(p for p in manifest['patches'] if p['id'] == PATCH)
    contour = boundary(Path(patch['graphic']['alpha']), patch['graphic']['bbox'][:2])
    collection = bpy.data.collections['Leicester Working']
    def remove_object(obj):
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        bpy.data.objects.remove(obj, do_unlink=True)
    previous = [o for o in collection.all_objects if o is not None and o.get('south_cutaway') and not o.hide_render]
    if previous and all(o.get('south_cutaway') == TAG for o in previous):
        return {'tag': TAG, 'reused': True, 'components': len(previous)}
    if previous:
        raise RuntimeError('Restore the preserved input worker before replacing an earlier cutaway recipe')
    report, covers, interiors, retained_selectors = [], [], [], []
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    vertices = []
    for depth in (-10000.0, 10000.0):
        vertices.extend((x, -y/sine-depth*cosine, depth*sine) for x,y in contour)
    count = len(contour)
    faces = [tuple(reversed(range(count))), tuple(range(count,2*count))]
    faces.extend((i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count))
    cutter_mesh = bpy.data.meshes.new('Gatehouse native cover cutter')
    cutter_mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new(); bm.from_mesh(cutter_mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(cutter_mesh); bm.free()
    cutter = bpy.data.objects.new('Gatehouse native cover cutter', cutter_mesh)
    collection.objects.link(cutter); cutter.hide_render = True
    for node in COVER_NODES+INTERIOR_NODES:
        source_node = f'building-{node:03}'
        sources = [o for o in collection.all_objects if o is not None and o.type == 'MESH' and
                   o.get('source_node') == source_node and not o.hide_render]
        if len(sources) != 1:
            raise RuntimeError('Expected exactly one unsplit component: '+source_node)
        source = sources[0]
        source.data = source.data.copy()
        bm = bmesh.new(); bm.from_mesh(source.data)
        before_vertices = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.5)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-5)
        if node in (141,142,143,144,145,147):
            # Hip wedges and straight chamber wall slabs are convex. Their
            # measured corners define the hull; hidden closures stay neutral.
            bmesh.ops.delete(bm, geom=list(bm.faces), context='FACES_ONLY')
            bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
            loose = [e for e in bm.edges if not e.link_faces]
            if loose: bmesh.ops.delete(bm, geom=loose, context='EDGES')
            loose = [v for v in bm.verts if not v.link_edges]
            if loose: bmesh.ops.delete(bm, geom=loose, context='VERTS')
        duplicates, seen = [], set()
        bm.verts.index_update()
        for face in bm.faces:
            key = tuple(sorted(v.index for v in face.verts))
            if key in seen: duplicates.append(face)
            else: seen.add(key)
        if duplicates: bmesh.ops.delete(bm, geom=duplicates, context='FACES_ONLY')
        boundaries = [e for e in bm.edges if e.is_boundary]
        caps = bmesh.ops.holes_fill(bm, edges=boundaries, sides=0)['faces'] if boundaries else []
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bad = sum(not e.is_manifold for e in bm.edges)
        if bad:
            raise RuntimeError(f'{source_node} remains nonmanifold before Boolean: {bad}')
        cleanup = {'vertices_before':before_vertices,'vertices_after':len(bm.verts),
                   'weld_tolerance':0.5,'inferred_closure_faces':len(caps),'nonmanifold_edges':bad}
        bm.to_mesh(source.data); bm.free()
        names = ('retained-shell', 'removable-cover' if node in COVER_NODES else 'interior-wall')
        counts = []
        for index, operation in enumerate(('DIFFERENCE', 'INTERSECT')):
            obj = source.copy(); obj.data = source.data.copy()
            obj.name = source.name+' / '+names[index]
            collection.objects.link(obj)
            modifier = obj.modifiers.new('Native patch camera prism', 'BOOLEAN')
            modifier.operation = operation; modifier.solver = 'EXACT'; modifier.object = cutter
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            obj.select_set(False)
            mesh = obj.data
            if not mesh.polygons:
                raise RuntimeError('Expected a nonempty native gatehouse cutaway component')
            bm = bmesh.new(); bm.from_mesh(mesh)
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-3)
            bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-6)
            boundary_edges = sum(e.is_boundary for e in bm.edges)
            nonmanifold = sum(not e.is_manifold for e in bm.edges)
            degenerate = sum(f.calc_area() < 1e-8 for f in bm.faces)
            bm.to_mesh(mesh); bm.free()
            if degenerate or nonmanifold:
                raise RuntimeError(f'{source_node}/{names[index]} Boolean topology invalid: {degenerate}, {nonmanifold}')
            if not mesh.uv_layers:
                mesh.uv_layers.new(name='UVMap')
            obj['projection_component'] = names[index]
            obj['reveal_component_role'] = names[index]
            obj['reveal_component_patch_id'] = PATCH
            obj['south_cutaway'] = TAG
            selector = {'source_node':source_node,'projection_component':names[index],'patch_id':PATCH}
            if index == 1:
                (covers if node in COVER_NODES else interiors).append(selector)
            else:
                retained_selectors.append(selector)
            counts.append({'component':names[index], 'vertices':len(mesh.vertices),
                           'faces':len(mesh.polygons),'boundary_edges':boundary_edges,
                           'nonmanifold_edges':nonmanifold})
        source.hide_render = True; source.hide_set(True)
        source['south_cutaway_baseline'] = TAG
        report.append({'source_node':source_node,'components':counts,'source_closure':cleanup})
    remove_object(cutter)
    review = manifest['projection_reviews'][PATCH]
    review['partial_cover_nodes'] = sorted({c['source_node'] for c in covers})
    review['exclude_occluder_components'] = covers
    review['receiver_nodes'] = sorted((set(review['receiver_nodes'])-{'building-148'}) |
                                    {c['source_node'] for c in interiors})
    def receivers(selectors):
        result = []
        for node in sorted({c['source_node'] for c in selectors}):
            result.append({'source_node':node,'projection_components':
                           [c['projection_component'] for c in selectors if c['source_node']==node],
                           'patch_id':PATCH})
        return result
    review['receiver_components'] = {
        'exterior':receivers(covers+retained_selectors),
        'interior-'+PATCH:receivers(interiors)}
    review['evidence'] = ('Native patch004 alpha contour, simplified within 0.8 source pixels, '
                          'splits front/right masonry and four hips into removable cover; '
                          'rear and left chamber walls retain authored interior receivers. '
                          'See worker geometry-report.json and paired state sheets.')
    review['render_visibility']['revealed']['hidden_components'] = covers
    review['render_visibility']['covered']['hidden_components'] = interiors
    review['render_visibility']['covered']['hidden_nodes'] = [
        n for n in review['render_visibility']['covered']['hidden_nodes'] if n != 'building-148']
    review['covered_hidden_nodes'] = list(review['render_visibility']['covered']['hidden_nodes'])
    review['render_visibility']['evidence'] = review['evidence']
    review['render_visibility']['limitations'] = ['Source-camera Boolean prism determines inferred cut depth; caps are neutral where unsupported.']
    review['geometry_ready'] = False
    review['limitations'] = 'Candidate native-mask cutaway requires paired-view inspection before readiness.'
    path.write_text(json.dumps(manifest, indent=2)+'\n')
    bpy.context.view_layer.update()
    return {'tag':TAG,'native_contour':contour,'contour_tolerance_px':0.8,
            'source_components':report,'cover_selectors':covers,'interior_selectors':interiors,
            'transform_drift':0,'status':'candidate awaiting paired state inspection'}
