"""Authored church roof shells, reveal partitions and floor receivers.

The source camera defines two measured cutaway edges. Hidden floor extents and
two-unit roof thickness are explicit inferences. Reproject every modified mesh.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

ROOT = Path(__file__).resolve().parents[2]
TAG = 'nottingham-church-reveal-v1'
SIN, COS = math.sin(math.radians(35)), math.cos(math.radians(35))


def fingerprint(obj):
    value = {'v': [list(v.co) for v in obj.data.vertices],
             'f': [list(f.vertices) for f in obj.data.polygons],
             'm': [list(r) for r in obj.matrix_world],
             'uv': {u.name: [list(v.uv) for v in u.data] for u in obj.data.uv_layers}}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def native_point(point):
    x, y, z = point
    return Vector((x, -y/SIN, z/COS))


def replace_native(obj, vertices, faces):
    inverse = obj.matrix_world.inverted()
    mesh = bpy.data.meshes.new(obj.name + ' / authored')
    mesh.from_pydata([inverse @ native_point(p) for p in vertices], [], faces)
    mesh.materials.append(neutral())
    mesh.update()
    obj.data = mesh
    return obj


def neutral():
    material = bpy.data.materials.get('Nottingham / unprojected state geometry')
    if material is None:
        material = bpy.data.materials.new('Nottingham / unprojected state geometry')
        material.diffuse_color = (.5, .5, .5, 1)
    return material


def copy_component(obj, label):
    new = obj.copy()
    new.data = obj.data.copy()
    new.name = obj['source_node'] + ' / ' + label
    for collection in obj.users_collection:
        collection.objects.link(new)
    new['projection_component'] = label
    return new


def label(obj, value):
    obj['projection_component'] = value
    obj['church_refinement'] = TAG
    obj['reveal_patch_ids'] = ['patch-000']
    obj['reveal_component_patch_id'] = 'patch-000'
    obj['reveal_component_role'] = 'removable-cover' if value == 'church-removable-cover' else 'retained'
    obj['geometry_approval'] = 'pending'
    return obj


def prism(obj, points, bottom, top):
    n = len(points)
    vertices = [(p[0], p[1], bottom if isinstance(bottom, (int, float)) else bottom[i]) for i, p in enumerate(points)]
    vertices += [(p[0], p[1], top if isinstance(top, (int, float)) else top[i]) for i, p in enumerate(points)]
    faces = [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    for start in [0, n]:
        vectors = [Vector(p) for p in vertices[start:start+n]]
        for tri in tessellate_polygon([vectors]):
            ids = [start+(v if isinstance(v, int) else min(range(n), key=lambda i: (vectors[i]-v).length_squared)) for v in tri]
            faces.append(tuple(reversed(ids)) if start == 0 else tuple(ids))
    return replace_native(obj, vertices, faces)


def split_plane(obj, normal, distance, retained_label='church-retained', cover_label='church-removable-cover'):
    """Split a closed mesh at a measured world plane, retaining its transforms."""
    cover = copy_component(obj, cover_label)
    world_normal = Vector(normal).normalized()
    world_point = Vector(normal) * (distance / Vector(normal).length_squared)
    inverse = obj.matrix_world.inverted()
    local_point = inverse @ world_point
    local_normal = obj.matrix_world.to_3x3().transposed() @ world_normal
    for target, remove_positive, component in [(obj, True, retained_label), (cover, False, cover_label)]:
        bm = bmesh.new()
        bm.from_mesh(target.data)
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                              plane_co=local_point, plane_no=local_normal, dist=1e-5,
                              clear_outer=remove_positive, clear_inner=not remove_positive)
        boundary = [e for e in bm.edges if e.is_boundary]
        if boundary:
            bmesh.ops.holes_fill(bm, edges=boundary)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(target.data)
        bm.free()
        label(target, component)
        target['reveal_state'] = 'both' if remove_positive else 'covered'
    return obj, cover


def refine(asset_id='nottingham-church'):
    collection = bpy.data.collections['nottingham Working']
    meshes = [o for o in collection.all_objects if o.type == 'MESH']
    objects = {int(o['source_node'].split('-')[-1]): o for o in meshes
               if o.get('asset_group') == asset_id and o.get('source_node', '').startswith('building-')}
    if set(objects) != set(range(380, 430)):
        raise ValueError(f'Church must own exactly nodes380..429; got {sorted(objects)}')
    if any(o.get('church_refinement') == TAG for o in objects.values()):
        raise ValueError('Recipe already applied; restart from the frozen worker baseline')
    outside = {o.name: fingerprint(o) for o in meshes if o not in objects.values()}
    before = {o.name: fingerprint(o) for o in objects.values()}
    native = json.loads((ROOT/'work/nottingham-refinement/source-states/level.json').read_text())['sight_obstacles']
    # Remove collision-volume skirts underneath thin roof planes, retaining all
    # measured top vertices. These skirts otherwise fill the revealed rooms.
    roof_nodes = [389, 390, 397, 398, 399, 404, 405, 406, 409, 410, 412, 413]
    for number in roof_nodes:
        points = native[number]['points']
        tops = [p['z_top'] for p in points]
        prism(objects[number], [(p['x'], p['y']) for p in points], [z-2 for z in tops], tops)
        label(objects[number], 'church-roof')
    # The south room roofs and intermediate canopy disappear completely.
    for number in [389, 390, 397]:
        label(objects[number], 'church-removable-cover')['reveal_state'] = 'covered'
    # These lines join source-image cover boundary landmarks, in full-map pixels.
    cut_lines = {406: (.4144, 1, 1625.4), 408: (.4144, 1, 1625.4),
                 398: (-1.333333, 1, -2092.0), 399: (-1.333333, 1, -2092.0)}
    for number, (a, b, c) in cut_lines.items():
        split_plane(objects[number], (a, -b*SIN, -b*COS), c)
    # Remaining wall bases are directly visible in the cutaway source. The
    # level heights are inferred from neighboring native posts and floor edges.
    for number, height in [(383, 56), (384, 28), (385, 28), (387, 56),
                           (394, 100), (395, 100), (396, 100)]:
        split_plane(objects[number], (0, 0, 1), height/COS)
    for number in [388, 392]:
        label(objects[number], 'church-removable-cover')['reveal_state'] = 'covered'
    for number in [386,393,400,401,414]:
        label(objects[number], 'church-retained')
    # Two separate rooms share native floor datum0. The inferred concealed
    # extents remain clipped by authored source ownership during projection.
    nave = [(1764,1039),(1802,1061),(1856,1092),(1892,1071),(1969,1028),
            (2004,1048),(2109,987),(2155,1014),(2242,965),(2164,928),
            (2203,860),(2155,829),(2104,819),(2013,841),(1906,881),(1694,999)]
    side = [(1885,1088),(2039,1176),(2073,1169),(2133,1132),(2062,1091),
            (2044,1080),(1972,1039),(1935,1060),(1903,1077)]
    for number, polygon, component in [(385, nave, 'church-nave-floor'), (414, side, 'church-side-room-floor')]:
        floor = copy_component(objects[number], component)
        prism(floor, polygon, -1, 0)
        label(floor, component)['reveal_state'] = 'revealed'
        floor['inferred_surface_note'] = 'Native floor datum0; hidden boundary extent inferred behind authored room walls.'
    for number in range(418, 430):
        label(objects[number], 'church-interior')['reveal_state'] = 'revealed'
    for number in [416, 417]:
        label(objects[number], 'church-closed-door')['reveal_state'] = 'covered'
    bpy.context.view_layer.update()
    changed = [o for o in collection.all_objects if o.type == 'MESH' and o.get('asset_group') == asset_id]
    nonmanifold, degenerate = {}, {}
    for obj in changed:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        degenerate[obj.name] = sum(f.calc_area() < 1e-8 for f in bm.faces)
        nonmanifold[obj.name] = sum(not e.is_manifold for e in bm.edges)
        bm.free()
    drift = [n for n, digest in outside.items() if fingerprint(bpy.data.objects[n]) != digest]
    if drift or any(degenerate.values()):
        raise ValueError(f'Validation failed outside={drift}, degenerate={degenerate}')
    return {'recipe': TAG, 'asset_id': asset_id, 'source_nodes': sorted(objects),
            'before_hashes': before, 'after_hashes': {o.name: fingerprint(o) for o in changed},
            'source_pixel_cut_lines': cut_lines, 'outside_object_changes': drift,
            'degenerate_faces': degenerate, 'nonmanifold_edges': nonmanifold,
            'new_floor_receivers': ['building-385/church-nave-floor', 'building-414/church-side-room-floor'],
            'approval': 'pending', 'texture_generation': 'not-started',
            'limitations': ['Cutaway wall heights28/56/100 and hidden floor extents are inferred.',
                           'Two-unit roof thickness is inferred; concealed surfaces require neutral projection.',
                           'Source edge lines approximate irregular painted cut boundaries and require camera review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    result = refine()
    args.output.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output/'model.blend'))
    (args.output/'geometry-report.json').write_text(json.dumps(result, indent=2)+'\n')
