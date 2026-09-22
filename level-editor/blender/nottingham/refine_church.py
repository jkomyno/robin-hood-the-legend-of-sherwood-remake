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
    mesh.uv_layers.new(name='UnprojectedSurfaceUV')
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
    # Reconstruct closed measured primitives; the imported quad surfaces have
    # independently rounded edges and incomplete concealed caps.
    for number, obj in objects.items():
        points = native[number]['points']
        top = [p['z_top'] for p in points]
        bottom = [min(p['z_bottom'], z-.2) for p,z in zip(points,top)]
        prism(obj, [(p['x'],p['y']) for p in points], bottom, top)
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
    # Complete concealed roof pitches rather than leaving source-facing skins
    # as open roofs. Their unsupported source projection remains neutral.
    completions=[
        (412,'church-tower-hidden-roof-east',[(2066.1785,938.1908,376.5),
             (1980.8197,885.02826,376.5),(1976.71,929.30,460.7)]),
        (412,'church-tower-hidden-roof-west',[(1980.8197,885.02826,376.5),
             (1895.0814,930.7485,376.5),(1976.71,929.30,460.7)]),
        (410,'church-apse-hidden-roof',[(2105.6714,851.6938,288.731),(2194.671,814.0004,205),
             (2106.6245,811.1242,205)])]
    # Subdivide the bent rear eave into ruled pitches. A single nonplanar
    # polygon permits a flat eave-to-eave diagonal, leaving a false wedge.
    ridge_a = Vector((1755.438,1043.9984,294.368))
    ridge_b = Vector((2105.6714,851.6938,288.731))
    eaves = [(1686.4951,994.6734,205),(1898.3978,876.7911,205),
             (2003.6245,835.62415,205),(2106.6245,811.1242,205)]
    direction = ridge_b-ridge_a
    def ridge_for(eave, index):
        t = max(0,min(1,((eave[0]-ridge_a.x)*direction.x+
                         (eave[1]-ridge_a.y)*direction.y)/
                        (direction.x**2+direction.y**2)))
        if index == 0: t = 0
        if index == len(eaves)-1: t = 1
        return tuple(ridge_a+direction*t)
    for i in range(len(eaves)-1):
        a,b=eaves[i:i+2];ra,rb=ridge_for(a,i),ridge_for(b,i+1)
        for side,triangle in enumerate([(a,b,rb),(a,rb,ra)]):
            completions.append((406,f'church-nave-hidden-roof-{i}-{side}',triangle))
    for number,component,points in completions:
        obj=copy_component(objects[number],component)
        prism(obj,[(x,y) for x,y,z in points],[z-2 for x,y,z in points],[z for x,y,z in points])
        label(obj,component)['reveal_state']='both'
        obj['inferred_surface_note']='Concealed roof completion between measured ridge and wall eaves; unsupported color remains neutral.'
    for index,points in enumerate([
        [(1931.08,895.55,116.1),(2031.98,839.20,116.3),(1982.82,866.65,190.3)],
        [(1839.19,841.85,116.1),(1940.10,785.50,116.3),(1890.94,812.95,190.3)]]):
        component=f'church-annex-gable-{index}'
        obj=copy_component(objects[403],component)
        vertices=points+[(x-2.6,y-1.5,z) for x,y,z in points]
        replace_native(obj,vertices,[(0,2,1),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)])
        label(obj,component)['reveal_state']='both'
        obj['inferred_surface_note']='Concealed triangular gable closure between measured side-annex roof pitches.'
    # End gables close the side-room roof above its lower masonry datum.
    # They disappear together with the room roof in the revealed state.
    for index,points in enumerate([
        [(2039.9,1196.6,123.5),(2099.0,1162.7,205.0),
         (2151.3,1132.7,146.4),(2151.3,1132.7,123.5)],
        [(1867.1,1097.7,123.5),(1926.2,1063.8,205.0),
         (1978.4,1033.8,146.4),(1978.4,1033.8,123.5)]]):
        obj=copy_component(objects[389],f'church-side-room-gable-{index}')
        vertices=points+[(x-2.6,y-1.5,z) for x,y,z in points]
        replace_native(obj,vertices,[(0,2,1),(0,3,2),(4,5,6),(4,6,7),
                                    (0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
        label(obj,'church-removable-cover')['reveal_state']='covered'
        obj['inferred_surface_note']='Thin gable closure between measured side-room roof ends and wall datum123.5.'
        # One selector identifies one canonical removable roof component.
        # Combine its disconnected closed gable shell into that same mesh.
        target=objects[389]
        vertices=[tuple(v.co) for v in target.data.vertices]
        faces=[tuple(f.vertices) for f in target.data.polygons]
        offset=len(vertices)
        vertices.extend(tuple(v.co) for v in obj.data.vertices)
        faces.extend(tuple(offset+i for i in f.vertices) for f in obj.data.polygons)
        target.data.clear_geometry();target.data.from_pydata(vertices,[],faces);target.data.update()
        if not target.data.uv_layers: target.data.uv_layers.new(name='UnprojectedSurfaceUV')
        if not target.data.materials: target.data.materials.append(neutral())
        bpy.data.objects.remove(obj,do_unlink=True)
        target['inferred_surface_note']='Two concealed side-room end gables close roof-to-wall contacts; thickness inferred.'
    # Four square corner pinnacles are supported by the tower source outline.
    for index,point in enumerate(native[411]['points']):
        x,y=point['x'],point['y'];u=(4.2,2.5);v=(-4.2,2.5)
        square=[(x-u[0]-v[0],y-u[1]-v[1]),(x+u[0]-v[0],y+u[1]-v[1]),
                (x+u[0]+v[0],y+u[1]+v[1]),(x-u[0]+v[0],y-u[1]+v[1])]
        obj=copy_component(objects[411],f'church-tower-pinnacle-{index}')
        vertices=[(a,b,z) for z in [374,398] for a,b in square]+[(x,y,412)]
        faces=[(0,3,2,1)]+[(i,(i+1)%4,(i+1)%4+4,i+4) for i in range(4)]+[(i+4,(i+1)%4+4,8) for i in range(4)]
        replace_native(obj,vertices,faces);label(obj,f'church-tower-pinnacle-{index}')['reveal_state']='both'
        obj['inferred_surface_note']='Four source-visible corner pinnacles; square hidden depth and simplified pointed caps.'
    a,b=(1747,1039),(1808,1074)
    for index,(depth,height) in enumerate([(16,2),(8,4)]):
        polygon=[a,b,(b[0]-depth,b[1]+depth*.58),(a[0]-depth,a[1]+depth*.58)]
        obj=copy_component(objects[380],f'church-entrance-step-{index}')
        prism(obj,polygon,0,height);label(obj,f'church-entrance-step-{index}')['reveal_state']='both'
        obj['inferred_surface_note']='Two visible threshold steps; small rise/depth inferred from source silhouette.'
    for component,x0,x1,z0,z1 in [('church-gable-cross-upright',1753.5,1756.5,297,319),
                                 ('church-gable-cross-arm',1748,1762,310,313)]:
        obj=copy_component(objects[380],component)
        prism(obj,[(x0,1042),(x1,1042),(x1,1045),(x0,1045)],z0,z1)
        label(obj,component)['reveal_state']='both'
        obj['inferred_surface_note']='Small stone gable cross; concealed thickness inferred.'
    bpy.context.view_layer.update()
    changed = [o for o in collection.all_objects if o.type == 'MESH' and o.get('asset_group') == asset_id]
    nonmanifold, degenerate = {}, {}
    for obj in changed:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-6)
        boundary = [edge for edge in bm.edges if edge.is_boundary]
        if boundary:
            bmesh.ops.holes_fill(bm, edges=boundary)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        degenerate[obj.name] = sum(f.calc_area() < 1e-8 for f in bm.faces)
        nonmanifold[obj.name] = sum(not e.is_manifold for e in bm.edges)
        bm.to_mesh(obj.data)
        bm.free()
    drift = [n for n, digest in outside.items() if fingerprint(bpy.data.objects[n]) != digest]
    if drift or any(degenerate.values()) or any(nonmanifold.values()):
        raise ValueError(f'Validation failed outside={drift}, degenerate={degenerate}, nonmanifold={nonmanifold}')
    return {'recipe': TAG, 'asset_id': asset_id, 'source_nodes': sorted(objects),
            'before_hashes': before, 'after_hashes': {o.name: fingerprint(o) for o in changed},
            'source_pixel_cut_lines': cut_lines, 'outside_object_changes': drift,
            'degenerate_faces': degenerate, 'nonmanifold_edges': nonmanifold,
            'new_floor_receivers': ['building-385/church-nave-floor', 'building-414/church-side-room-floor'],
            'roof_completions': [c for n,c,p in completions],
            'repeated_elements':{'tower_corner_pinnacles':4,'entrance_steps':2,'gable_cross':1},
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
