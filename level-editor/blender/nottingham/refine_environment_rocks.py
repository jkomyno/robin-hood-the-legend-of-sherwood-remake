"""Measured rock cap and ledge profiles; concealed depth stays conservative.

Call refine(asset_id), then regenerate the complete source-projection packet.
Pixel coordinates use the frozen 2304 by 3520 covered artwork. Heights are
projected vertical pixels, following the receiver coordinate convention.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
ASSETS = {
    'nottingham-castle-west-rocks': [478, 479, 480, 481, 484],
    'nottingham-forest-rock-outcrop': [546],
}
TAG = 'nottingham_measured_rock_profile_v1'
SINE = math.sin(math.radians(35))
COSINE = math.cos(math.radians(35))


def _hash(obj):
    data = [[list(v.co) for v in obj.data.vertices],
            [list(p.vertices) for p in obj.data.polygons]]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def _world(x, screen_y, height):
    return Vector((x, -(screen_y + height) / SINE, height / COSINE))


def _build(points, node):
    """Closed faceted receiver, retaining the native basal ring."""
    bottom = [(p['x'], p['y'], p['z_bottom']) for p in points]
    top = [(p['x'], p['y'] - p['z_top'], p['z_top']) for p in points]
    evidence = []
    if node == 546:
        # The upper ring follows the cap and right shoulder; the intermediate
        # ring follows the clearly visible horizontal seam at y=130..160.
        top = [(1141, 130, 41), (1125, 122, 46), (1107, 128, 44),
               (1096, 103, 54), (1077, 91, 56), (1047, 85, 56),
               (1023, 96, 54), (1019, 115, 48), (1027, 133, 40),
               (1061, 145, 37), (1069, 192, 29), (1143, 192, 29)]
        # Reorder the native ring to match the clockwise traced source contour.
        bottom = [(1144.8943, 170.92383, 0), (1124.7358, 167.13895, 0),
                  (1106.3148, 174.1111, 0), (1098.6832, 148.01537, 0),
                  (1073, 144.3, 0), (1046.578, 140.56293, 0),
                  (1019.999, 150.40582, 0), (1021.84, 170.2, 0),
                  (1023.6832, 190.04745, 0), (1061.0516, 195.02756, 0),
                  (1068.1569, 221.71231, 0), (1144.8943, 221.71231, 0)]
        evidence.append({'feature': 'upper cap and right shoulder contour',
                         'source_pixels': [[x, y] for x, y, h in top],
                         'confidence': 'high exposed cap; medium vegetation-covered lower right'})
    # Native rings have deliberately zero-height corners. A narrow bevel ring
    # adds sloping rock shoulders without moving their ground contacts.
    world_bottom = [_world(x, y-h, h) for x, y, h in bottom]
    world_top = [_world(*p) for p in top]
    n = len(top)
    if len(bottom) != n:
        raise ValueError('Rock ring correspondence mismatch')
    center = sum(world_top, Vector()) / n
    shoulder = [p.lerp(q, .72) for p, q in zip(world_bottom, world_top)]
    cap = [p.lerp(center, .08 if node != 546 else .025) for p in world_top]
    if node == 480:
        # Long exposed upper-left crest: replace the ruler-straight segment
        # between native corner 3 and corner 0 with three measured breaks.
        anchors = [(110, 2048), (139, 2026), (157, 2018)]
        for x, screen_y in anchors:
            t = (x - points[3]['x']) / (points[0]['x'] - points[3]['x'])
            ground_y = points[3]['y']*(1-t) + points[0]['y']*t
            b = _world(x, ground_y, 0)
            p = _world(x, screen_y, ground_y-screen_y)
            world_bottom.append(b)
            shoulder.append(b.lerp(p, .72))
            cap.append(p)
        n += 3
        evidence.append({'feature': 'exposed upper-left cliff crest breaks',
                         'source_pixels': [list(p) for p in anchors], 'confidence': 'medium; adjoining foliage excluded'})
    if node in (478, 479, 481, 484):
        evidence.append({'feature': 'faceted shoulder below retained native crest',
                         'confidence': 'visible sloping faces; exact depth inferred',
                         'retained_native_crest_pixels': [[x,y] for x,y,h in top]})
    vertices = world_bottom + shoulder + cap
    faces = [tuple(reversed(range(n)))]
    for offset in (0, n):
        faces.extend((offset+i, offset+(i+1)%n, offset+n+(i+1)%n, offset+n+i)
                     for i in range(n))
    # The forest cap is concave. Blender triangulation retains its shoulder
    # notch instead of bridging it with an invented apex.
    faces.append(tuple(range(2*n, 3*n)))
    return vertices, faces, evidence


def refine(asset_id):
    if asset_id not in ASSETS:
        raise ValueError(f'Unsupported rock asset {asset_id}')
    native = json.loads((ROOT/'level-editor/work/nottingham-refinement/baseline/nottingham.rhp.json').read_text())
    expected = {f'building-{i:03}' for i in ASSETS[asset_id]}
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH'
               and o.get('source_node') in expected and not o.hide_render and not o.hide_get()]
    if len(objects) != len(expected) or {o['source_node'] for o in objects} != expected:
        raise ValueError(f'Missing or duplicate visible rock receivers: {asset_id}')
    outside = {o.name: (_hash(o), tuple(tuple(r) for r in o.matrix_world))
               for o in bpy.context.scene.objects if o.type == 'MESH' and o not in objects}
    reports = []
    for obj in objects:
        if obj.get(TAG):
            report = json.loads(obj[TAG])
            if _hash(obj) != report['geometry_sha256']:
                raise ValueError(f'Refined rock geometry changed after recipe: {obj.name}')
            reports.append(report)
            continue
        node = int(obj['source_node'].split('-')[-1])
        matrix = obj.matrix_world.copy()
        before = _hash(obj)
        vertices, faces, evidence = _build(native['sight_obstacles'][node]['points'], node)
        mesh = bpy.data.meshes.new(obj.name+' / faceted rock ledges')
        mesh.from_pydata([matrix.inverted() @ v for v in vertices], [], faces)
        mesh.update()
        bm = bmesh.new(); bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-6)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        defects = {'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
                   'degenerate_faces':sum(f.calc_area() < 1e-8 for f in bm.faces)}
        if any(defects.values()):
            raise ValueError(f'Invalid faceted rock {node}: {defects}')
        bm.to_mesh(mesh); bm.free()
        for material in obj.data.materials: mesh.materials.append(material)
        uv = mesh.uv_layers.new(name='Source projection')
        for loop in mesh.loops:
            p = matrix @ mesh.vertices[loop.vertex_index].co
            uv.data[loop.index].uv = (p.x/2304, 1-(-p.y*SINE-p.z*COSINE)/3520)
        obj.data = mesh
        if obj.matrix_world != matrix:
            raise ValueError('Rock transform drift')
        report = {'object':obj.name, 'source_node':obj['source_node'],
                  'before_geometry_sha256':before, 'geometry_sha256':_hash(obj),
                  'vertices':len(mesh.vertices), 'faces':len(mesh.polygons),
                  'transform_drift':0, 'validation':defects, 'measurements':evidence}
        obj[TAG] = json.dumps(report, sort_keys=True)
        reports.append(report)
    for name, snapshot in outside.items():
        obj = bpy.data.objects[name]
        if (_hash(obj), tuple(tuple(r) for r in obj.matrix_world)) != snapshot:
            raise ValueError(f'Outside object changed: {name}')
    return {'asset_id':asset_id, 'status':'refined-rock-caps-and-shoulders',
            'recipe':'measured-rock-cap-and-faceted-shoulders-v1',
            'objects':reports, 'outside_objects_unchanged':True,
            'geometry_approval':'pending', 'projection_status':'stale; regenerate packet',
            'inference':['Concealed cap depth and shoulder bevel are conservative geometric estimates.',
                         'Castle foliage-covered crests retain the native silhouette; no vegetation is modeled.',
                         'Forest intermediate ledges are simplified; painted fissures remain unmodeled.',
                         'Rock undersides close at the native ground contacts.'],
            'texture_generation':'not started'}
