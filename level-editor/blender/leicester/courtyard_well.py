"""Rebuild the courtyard well at its visible terrace contact.

Retain the measured octagonal footprint. Two posts and a crossbeam follow the
source silhouette; concealed cavity depth and timber thickness are inferred.
Run on the prepared well worker, then regenerate its modified packet.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

TAG = 'leicester-courtyard-well-v1'
ASSET = 'leicester-courtyard-well'
FLOOR = 61.04


def component(template, collection, label, vertices, faces):
    mesh = bpy.data.meshes.new(label)
    mesh.from_pydata([template.matrix_world.inverted() @ Vector(p) for p in vertices], [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bad = sum(not edge.is_manifold for edge in bm.edges)
    degenerate = sum(face.calc_area() < 1e-8 for face in bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    if bad or degenerate:
        raise ValueError(f'{label}: {bad} nonmanifold edges, {degenerate} degenerate faces')
    for material in template.data.materials:
        mesh.materials.append(material)
    mesh.uv_layers.new(name='Unprojected neutral surface')
    obj = bpy.data.objects.new('Courtyard Well / ' + label, mesh)
    collection.objects.link(obj)
    obj.parent = template.parent
    obj.matrix_world = template.matrix_world.copy()
    for key in template.keys():
        obj[key] = template[key]
    obj['projection_component'] = label
    obj['refinement_recipe'] = TAG
    return obj


def beam(template, collection, label, start, end, width, depth):
    start, end = Vector(start), Vector(end)
    axis = (end - start).normalized()
    side = axis.cross(Vector((0, 0, 1)))
    if side.length < .01:
        side = Vector((1, 0, 0))
    side.normalize()
    up = axis.cross(side).normalized()
    vertices = [tuple(p + side * x * width / 2 + up * y * depth / 2)
                for p in (start, end) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    return component(template, collection, label, vertices,
        [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])


def finial(template, collection, config):
    masks_path = Path(config['source_mask_manifest'])
    masks = json.loads(masks_path.read_text())
    inventory_path = (masks_path.parent / masks['mask_inventory']).resolve()
    record = next(r for r in json.loads(inventory_path.read_text())['masks'] if r['index'] == 211)
    image = bpy.data.images.load(str(inventory_path.parent / record['png']), check_existing=False)
    try:
        width, height = image.size
        pixels = list(image.pixels)
        left, top = record['box_top_left']
        edges = set()
        for sy in range(997, 1018):
            for sx in range(1224, 1243):
                x, y = sx-left, sy-top
                if not (0 <= x < width and 0 <= y < height):
                    continue
                if pixels[((height-1-y)*width+x)*4] <= .5:
                    continue
                corners = [(sx, sy), (sx+1, sy), (sx+1, sy+1), (sx, sy+1)]
                for a, b in zip(corners, corners[1:]+corners[:1]):
                    if (b, a) in edges:
                        edges.remove((b, a))
                    else:
                        edges.add((a, b))
        loops = []
        while edges:
            a, b = min(edges)
            edges.remove((a, b))
            loop = [a, b]
            while loop[-1] != loop[0]:
                following = sorted(edge for edge in edges if edge[0] == loop[-1])
                if len(following) != 1:
                    raise ValueError('Finial silhouette boundary is ambiguous')
                edge = following[0]
                edges.remove(edge)
                loop.append(edge[1])
            loops.append(loop[:-1])
        if not loops:
            raise ValueError('No finial source silhouette')
        loop = max(loops, key=len)
        simplified = []
        for i, b in enumerate(loop):
            a, c = loop[i-1], loop[(i+1)%len(loop)]
            if (b[0]-a[0])*(c[1]-b[1]) != (b[1]-a[1])*(c[0]-b[0]):
                simplified.append(b)
        sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
        vertices = [(x, y, (-sy-y*sine)/cosine)
                    for y in (-1962.8, -1961.2) for x, sy in simplified]
        n = len(simplified)
        faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
        faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
        component(template, collection, 'source-silhouette-finial', vertices, faces)
        return {'outline_vertices': n, 'source_mask': 211, 'source_crop': [1224, 997, 1243, 1018],
                'inferred_depth': 1.6}
    finally:
        bpy.data.images.remove(image)


def refine(workspace):
    config = json.loads((workspace / 'workspace.json').read_text())
    if config['asset_id'] != ASSET or Path(bpy.data.filepath).resolve() != workspace / 'model.blend':
        raise ValueError('Open the prepared courtyard well model')
    collection = bpy.data.collections[config['collection_name']]
    owned = [o for o in collection.all_objects if o.type == 'MESH' and o.get('asset_group') == ASSET]
    if any(o.get('refinement_recipe') == TAG for o in owned):
        return {'status': 'already-refined', 'recipe': TAG}
    if len(owned) != 1 or owned[0]['source_node'] != 'building-377':
        raise ValueError('Expected one courtyard well source mesh')
    original = owned[0]
    # The cap supplies the exact eight footprint anchors, independent of the
    # duplicated side vertices used for separate texture islands.
    points = [original.matrix_world @ v.co for v in original.data.vertices]
    top = max(p.z for p in points)
    outline = [p for p in points if abs(p.z - top) < .001]
    if len(outline) != 8:
        raise ValueError('Expected eight cap anchors')
    center = sum(outline, Vector()) / 8
    outline.sort(key=lambda p: math.atan2(p.y-center.y, p.x-center.x))
    levels = [(FLOOR, 1.05), (FLOOR+3, 1.05), (FLOOR+3, 1),
              (top, 1), (top, .77), (FLOOR+10, .77)]
    vertices = [(center.x+(p.x-center.x)*scale, center.y+(p.y-center.y)*scale, z)
                for z, scale in levels for p in outline]
    faces = [(ring*8+i, ring*8+(i+1)%8, (ring+1)*8+(i+1)%8, (ring+1)*8+i)
             for ring in range(5) for i in range(8)]
    faces += [tuple(reversed(range(8))), tuple(range(40, 48))]
    shaft = component(original, collection, 'masonry-rim-and-cavity', vertices, faces)
    beam(original, collection, 'west-post', (1217, -1974, FLOOR), (1217, -1974, 138), 5, 5)
    beam(original, collection, 'east-post', (1254, -1950, FLOOR), (1254, -1950, 138), 5, 5)
    beam(original, collection, 'crossbeam', (1213, -1976.6, 137), (1258, -1947.4, 137), 7, 6)
    beam(original, collection, 'hanging-rod', (1235.5, -1962, FLOOR+14), (1235.5, -1962, 133), 1.2, 1.2)
    finial_report = finial(original, collection, config)
    bpy.data.objects.remove(original, do_unlink=True)
    return {'status': 'refined', 'recipe': TAG, 'source_nodes': ['building-377'],
            'terrace_datum_z': FLOOR, 'posts': 2, 'rim_corners': 8,
            'finial': finial_report,
            'limitations': ['Concealed cavity depth, post cross-section and rod depth are inferred.',
                           'Finial depth is inferred from its native silhouette; pulley head remains unresolved.'],
            'projection_status': 'stale', 'geometry_approval': 'pending'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    workspace = args.workspace.resolve(strict=True)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from refinement_workspace import validate
    validate(workspace)
    report = refine(workspace)
    validate(workspace)
    (workspace / 'geometry-report.json').write_text(json.dumps(report, indent=2) + '\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    print(json.dumps(report))
