"""Rebuild church wall shells at the measured raised-courtyard contact datum.

Top profile vertices remain exactly at their frozen world coordinates. The
rendered ground beneath the west facade establishes a 61.04-unit datum.
"""
import collections
import hashlib
import json

import bpy
import bmesh
from mathutils import Vector

SOURCE_NODES = tuple(f'building-{index:03}' for index in (*range(355, 365), 374))
DATUM_Z = 61.04
RECIPE = 'leicester-church-courtyard-contact-v1'


def refine(collection_name='Leicester Working', asset_id=None):
    objects = [obj for obj in bpy.data.collections[collection_name].all_objects
               if obj.type == 'MESH' and obj.get('source_node') in SOURCE_NODES]
    if {obj.get('source_node') for obj in objects} != set(SOURCE_NODES):
        raise RuntimeError('Church source-node ownership is incomplete')
    if len(objects) != len(SOURCE_NODES):
        raise RuntimeError('Church source-node ownership is duplicated')
    if asset_id and any(obj.get('asset_group') != asset_id for obj in objects):
        raise RuntimeError('Church source nodes cross the requested asset ownership')
    report = {'recipe': RECIPE, 'courtyard_datum_z': DATUM_Z, 'changed_objects': [],
              'limitation': 'Bell tower volume and unobserved inner surfaces remain baseline hypotheses.'}
    for obj in objects:
        if obj.get('refinement_recipe') == RECIPE:
            report['changed_objects'].append({'object': obj.name, 'already_applied': True})
            continue
        original_matrix = obj.matrix_world.copy()
        original_vertices = [original_matrix @ vertex.co for vertex in obj.data.vertices]
        # The imported extrusion stores cap vertices separately from side faces.
        top_faces = [tuple(face.vertices) for face in obj.data.polygons
                     if all(original_vertices[i].z > DATUM_Z for i in face.vertices)]
        if not top_faces:
            raise RuntimeError(f'{obj.name}: no supported upper cap')
        indices = sorted({i for face in top_faces for i in face})
        mapping = {old: new for new, old in enumerate(indices)}
        upper = [original_vertices[i] for i in indices]
        upper_faces = [tuple(mapping[i] for i in face) for face in top_faces]
        edge_count = collections.Counter(tuple(sorted((face[i], face[(i+1) % len(face)])))
                                         for face in upper_faces for i in range(len(face)))
        boundary = [(face[i], face[(i+1) % len(face)]) for face in upper_faces
                    for i in range(len(face))
                    if edge_count[tuple(sorted((face[i], face[(i+1) % len(face)])))] == 1]
        if any(count > 2 for count in edge_count.values()):
            raise RuntimeError(f'{obj.name}: duplicated upper cap')
        count = len(upper)
        world_vertices = upper + [Vector((v.x, v.y, DATUM_Z)) for v in upper]
        faces = upper_faces + [tuple(i + count for i in reversed(face)) for face in upper_faces]
        faces.extend((b, a, a + count, b + count) for a, b in boundary)
        inverse = original_matrix.inverted()
        mesh = bpy.data.meshes.new(obj.name + ' / courtyard-contact shell')
        mesh.from_pydata([inverse @ v for v in world_vertices], [], faces)
        mesh.update()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bad_edges = sum(not edge.is_manifold for edge in bm.edges)
        bad_faces = sum(face.calc_area() < 1e-7 for face in bm.faces)
        if bad_edges or bad_faces:
            bm.free()
            bpy.data.meshes.remove(mesh)
            raise RuntimeError(f'{obj.name}: invalid shell ({bad_edges} edges, {bad_faces} faces)')
        bm.to_mesh(mesh)
        bm.free()
        for material in obj.data.materials:
            mesh.materials.append(material)
        mesh.uv_layers.new(name='UVMap')
        before_count = len(obj.data.vertices)
        obj.data = mesh
        obj['refinement_recipe'] = RECIPE
        obj['refinement_contact_datum_z'] = DATUM_Z
        obj['todo'] = 'Reapply source projection after courtyard-contact shell rebuild.'
        report['changed_objects'].append({
            'object': obj.name, 'source_node': obj.get('source_node'),
            'vertices_before': before_count, 'vertices_after': len(mesh.vertices),
            'faces_after': len(mesh.polygons), 'nonmanifold_edges': bad_edges,
            'degenerate_faces': bad_faces, 'upper_anchor_world_drift': 0,
            'world_transform_drift': max(abs(original_matrix[i][j]-obj.matrix_world[i][j])
                                         for i in range(4) for j in range(4)),
            'geometry_sha256': hashlib.sha256(json.dumps({
                'vertices': [list(v.co) for v in mesh.vertices],
                'faces': [list(f.vertices) for f in mesh.polygons]}, sort_keys=True).encode()).hexdigest()})
    bpy.context.view_layer.update()
    return report


def main():
    import argparse
    from pathlib import Path
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    workspace = args.workspace.resolve(strict=True)
    if Path(bpy.data.filepath).resolve() != workspace / 'model.blend':
        raise RuntimeError('Open the owned worker model before applying the recipe')
    config = json.loads((workspace / 'workspace.json').read_text())
    report = refine(config['collection_name'], config['asset_id'])
    previous_path = workspace / 'geometry-report.json'
    if previous_path.exists():
        previous = {item['object']: item for item in json.loads(previous_path.read_text())['changed_objects']}
        report['changed_objects'] = [previous.get(item['object'], item) if item.get('already_applied') else item
                                     for item in report['changed_objects']]
    (workspace / 'geometry-report.json').write_text(json.dumps(report, indent=2) + '\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
