"""Replace the roadside fence receiver with separated stakes and three rails.

Measured visible stake positions are in source-image x coordinates. Native
receiver endpoints anchor the ground line; hidden depth and concealed end
stakes remain documented hypotheses. Projection must be refreshed afterwards.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

VERSION = 'leicester-roadside-fence-v1'
NODE = 'building-033'
# Trace of visible upright centers in the 3136 by 1984 covered artwork.
# The first source-visible post lies just inside the modeled receiver; the
# final modeled section disappears behind foreground foliage.
VISIBLE_STAKE_X = [2367.5, 2377.5, 2392.5, 2406.5, 2418.5, 2430.5,
                   2442.5, 2454.5, 2466.5, 2477.5, 2486.0, 2495.0,
                   2505.0, 2515.5, 2524.5, 2535.0, 2545.0, 2553.0]
CENTERLINE = [(2364.8, -2419.7), (2455.5, -2266.5), (2580.6, -2119.1)]


def signature(obj):
    return hashlib.sha256(json.dumps({'vertices': [list(v.co) for v in obj.data.vertices],
        'faces': [list(f.vertices) for f in obj.data.polygons]}, sort_keys=True).encode()).hexdigest()


def point_at_x(x):
    for a, b in zip(CENTERLINE, CENTERLINE[1:]):
        if a[0] <= x <= b[0]:
            fraction = (x-a[0])/(b[0]-a[0])
            return Vector((x, a[1]+fraction*(b[1]-a[1]), 0))
    raise ValueError('Measured stake lies outside the native fence centerline')


def refine(obj):
    if obj.get('source_node') != NODE:
        raise ValueError('This measured recipe supports only the roadside rail fence')
    before = signature(obj)
    matrix = obj.matrix_world.copy()
    if obj.get('leicester_fence_anchor'):
        anchor = json.loads(obj['leicester_fence_anchor'])
    else:
        world = [matrix @ v.co for v in obj.data.vertices]
        anchor = {'bottom': min(v.z for v in world), 'top': max(v.z for v in world)}
        obj['leicester_fence_anchor'] = json.dumps(anchor, sort_keys=True)
    bottom, top = anchor['bottom'], anchor['top']
    height = top-bottom
    if height <= 0:
        raise ValueError('Fence receiver has no height')
    vertices, faces = [], []

    def beam(a, b, thickness, breadth):
        direction = (b-a).normalized()
        reference = Vector((0, 0, 1)) if abs(direction.z) < .9 else Vector((1, 0, 0))
        side = direction.cross(reference).normalized()*thickness/2
        up = direction.cross(side).normalized()*breadth/2
        start = len(vertices)
        vertices.extend([p+sign_s*side+sign_u*up for p in (a,b)
                         for sign_s, sign_u in [(-1,-1),(1,-1),(1,1),(-1,1)]])
        faces.extend([tuple(start+i for i in face) for face in
                      [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]])

    # Keep the native vertical envelope. Small irregularities visible in the
    # artwork remain texture evidence; hidden post cross-sections are inferred.
    for x in VISIBLE_STAKE_X:
        p = point_at_x(x)
        beam(p+Vector((0,0,bottom)), p+Vector((0,0,top)), 3.0, 4.0)
    for a, b in zip(CENTERLINE, CENTERLINE[1:]):
        for fraction in (.18, .48, .78):
            z = bottom+height*fraction
            beam(Vector((*a,z)), Vector((*b,z)), 2.4, 4.0)
    mesh = bpy.data.meshes.new(obj.name+' separated rails')
    inverse = matrix.inverted()
    mesh.from_pydata([inverse @ v for v in vertices], [], faces)
    mesh.uv_layers.new(name='UVMap')
    mesh.update()
    for material in obj.data.materials:
        mesh.materials.append(material)
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    topology = {'vertices': len(bm.verts), 'faces': len(bm.faces),
                'boundary_edges': sum(e.is_boundary for e in bm.edges),
                'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
                'degenerate_faces': sum(f.calc_area() < 1e-7 for f in bm.faces)}
    if any(topology[key] for key in ('boundary_edges','nonmanifold_edges','degenerate_faces')):
        raise ValueError('Fence beam topology failed validation: '+str(topology))
    bm.to_mesh(mesh); bm.free()
    previous = obj.data
    obj.data = mesh
    if previous.users == 0:
        bpy.data.meshes.remove(previous)
    obj['leicester_geometry_recipe'] = VERSION
    if obj.matrix_world != matrix:
        raise ValueError('Fence refinement changed the object transform')
    return {'source_node': NODE, 'before_geometry_sha256': before,
            'after_geometry_sha256': signature(obj), 'world_transform_drift': 0,
            'visible_stake_count': len(VISIBLE_STAKE_X), 'visible_stake_source_x': VISIBLE_STAKE_X,
            'rail_levels': 3, 'native_centerline': CENTERLINE, 'anchor': anchor,
            'topology': topology}


def run(workspace):
    workspace = Path(workspace).resolve()
    config = json.loads((workspace/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve() != workspace/'model.blend':
        raise ValueError('Open the isolated worker model.blend')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from refinement_workspace import validate
    validate(workspace)
    targets = [o for o in bpy.data.collections[config['collection_name']].all_objects
               if o.type == 'MESH' and o.get('asset_group') == config['asset_id']]
    if len(targets) != 1 or targets[0].get('source_node') != NODE:
        raise ValueError('Roadside fence recipe requires its one canonical receiver')
    result = refine(targets[0]); first = signature(targets[0]); refine(targets[0])
    if signature(targets[0]) != first:
        raise ValueError('Fence recipe is not idempotent')
    report = {'recipe': VERSION, 'asset_id': config['asset_id'], 'objects': [result],
        'idempotence': 'PASS', 'projection_status': 'STALE; rebuild modified packet',
        'approval_status': 'refinement in progress', 'texture_generation': 'not-started',
        'source_supported': 'Eighteen visible upright centers traced from covered artwork; three rail levels; ground line and vertical envelope anchored to native receiver.',
        'limitations': ['Stake centers have approximately 2 source-pixel manual measurement uncertainty.',
                       'Cross-section widths and constant-height rear faces are inferred; source-only projection must leave unknown faces neutral.',
                       'The final fence end is hidden by foreground foliage; no extra concealed stakes are invented.',
                       'Six rail beams meet at the native bend; beam intersections at posts are intentional timber contacts.',
                       'Warp, broken tips, and finer rail irregularities remain texture detail; source masks must reject neighboring tree foliage.']}
    validate(workspace)
    (workspace/'inspection').mkdir(exist_ok=True)
    (workspace/'inspection'/'fence-recipe.json').write_text(json.dumps(report, indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    print(json.dumps(run(args.workspace)))
