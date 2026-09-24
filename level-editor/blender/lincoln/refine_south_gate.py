"""Lincoln south gate and southern walls: measured geometry recipe.

Run from the repository root, one asset per process (holds a render slot):

  /usr/bin/blender --background --threads 2 --python-exit-code 1 \
    --python level-editor/blender/lincoln/refine_south_gate.py -- --asset <asset-id> [--no-packet]

Opens <workspace>/model.blend, rebuilds only the owned meshes from the frozen
native obstacle inventory plus the lane's measurement traces
(<workspace>/inspection/corner-trace.json from south_gate_walls_trace.py),
saves, then regenerates the fixed eight-view modified packet with the frozen
tooling. Idempotent: every owned mesh is rebuilt from frozen inputs each run.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, 'level-editor/blender/lincoln')
from south_gate_walls_geometry import (Mesh, prism, ribbon, crenellated_strip,  # noqa: E402
                                       validate, to_world, lerp, polyline_length,
                                       point_at, arc_param_at_x, SIN, COS)
import south_gate_walls_assets as assets  # noqa: E402

ROOT = HERE.parents[2]
R = ROOT / 'level-editor/work/lincoln-refinement'
TOOLING = R / 'tooling/e6b57cb851c7142b'
TAG = 'south_gate_walls_recipe_v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def install(obj, mesh, notes):
    import bpy
    import bmesh
    from mathutils import Vector
    stats = validate(mesh)
    if stats['nonmanifold_edges']:
        raise ValueError(f"{obj.name}: {stats['nonmanifold_edges']} nonmanifold edges")
    inverse = obj.matrix_world.inverted()
    matrix = [list(r) for r in obj.matrix_world]
    data = bpy.data.meshes.new(obj.data.name.split(' / south-gate')[0] + ' / south-gate refined')
    data.from_pydata([inverse @ Vector(to_world(v)) for v in mesh.verts], [], mesh.faces)
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    degenerate = [f for f in bm.faces if f.calc_area() < 1e-6]
    if degenerate:
        raise ValueError(f'{obj.name}: {len(degenerate)} zero-area faces')
    if any(not e.is_manifold for e in bm.edges):
        raise ValueError(f'{obj.name}: nonmanifold after normal recalculation')
    volume = bm.calc_volume(signed=True)
    if volume <= 0:
        raise ValueError(f'{obj.name}: non-positive signed volume {volume}')
    bm.to_mesh(data)
    bm.free()
    for material in obj.data.materials:
        data.materials.append(material)
    data.uv_layers.new(name='UVMap')
    old = obj.data
    obj.data = data
    if old.users == 0:
        bpy.data.meshes.remove(old)
    assert matrix == [list(r) for r in obj.matrix_world]
    obj['source_projection_current'] = False
    obj[TAG] = json.dumps(notes)
    return {'object': obj.name, 'source_node': obj['source_node'], **stats,
            'signed_volume_world': round(volume, 3)}


def apply_mask_revisions(workspace, revisions):
    """Rebuild owned mask assignments from the frozen origin plus reviewed revisions.

    Idempotent: every owned entry is reset to the frozen assignment first, then
    each revision adds include indices and/or reviewed foreground exclusions.
    """
    origin = json.loads((workspace / 'mask-reference/assignments.json').read_text())
    path = workspace / 'source-masks.json'
    working = json.loads(path.read_text())
    frozen = {a['source_node']: a for a in origin['projections']['exterior']['assignments'] if 'source_node' in a}
    config = json.loads((workspace / 'workspace.json').read_text())
    rows = working['projections']['exterior']['assignments']
    for k, row in enumerate(rows):
        node = row.get('source_node')
        if node not in config['part_ids']:
            continue
        row = json.loads(json.dumps(frozen[node]))
        rev = revisions.get(node)
        if rev:
            if rev.get('add'):
                row['mask_indices'] = sorted(set(row['mask_indices']) | set(rev['add']))
                row['requires_first_hit_gating'] = True
                row['composite_envelope'] = ((row.get('composite_envelope') or '') + ' ' + rev['add_note']).strip()
            if rev.get('exclude'):
                row['exclude_mask_indices'] = sorted(set(row.get('exclude_mask_indices', [])) | set(rev['exclude']))
                row['exclusions_reviewed'] = True
                row['exclusion_reason'] = rev['exclude_reason']
            row['review_note'] = row.get('review_note', '') + ' Worker revision (south_gate_walls lane): ' + rev['note']
            if rev.get('evidence'):
                row['worker_revision_evidence'] = rev['evidence']
        rows[k] = row
    text = json.dumps(working, indent=2, sort_keys=True) + '\n'
    if path.read_text() != text:
        path.write_text(text)
    return {n: r for n, r in revisions.items()}


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument('--asset', required=True)
    parser.add_argument('--no-packet', action='store_true')
    args = parser.parse_args(argv)
    workspace = R / 'round-1/assets' / args.asset
    from render_slots import acquire
    acquire()
    import bpy
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    owned = {o['source_node']: o for o in bpy.data.collections['lincoln Working'].all_objects
             if o.type == 'MESH' and o.get('asset_group') == args.asset}
    trace_path = workspace / 'inspection/corner-trace.json'
    trace = json.loads(trace_path.read_text()) if trace_path.exists() else None
    built = assets.build(args.asset, trace)
    report = {'version': 1, 'asset_id': args.asset, 'recipe': str(Path(__file__).resolve()),
              'recipe_sha256': sha(__file__), 'assets_module_sha256': sha(HERE / 'south_gate_walls_assets.py'),
              'geometry_module_sha256': sha(HERE / 'south_gate_walls_geometry.py'),
              'trace_sha256': sha(trace_path) if trace else None,
              'objects': [], 'unchanged': sorted(set(owned) - set(built['meshes'])),
              'ground': built['ground'], 'changes': built['changes'],
              'inferred': built['inferred'], 'limitations': built['limitations'],
              'states': built.get('states')}
    for node, mesh in sorted(built['meshes'].items()):
        if node not in owned:
            raise ValueError(f'{node} is not owned by {args.asset}')
        report['objects'].append(install(owned[node], mesh, built['notes'].get(node, {})))
    report['mask_revisions'] = apply_mask_revisions(workspace, built.get('mask_revisions', {}))
    for node, props in built.get('object_properties', {}).items():
        for key, value in props.items():
            owned[node][key] = json.dumps(value) if isinstance(value, (dict, list)) else value
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    (workspace / 'inspection').mkdir(exist_ok=True)
    (workspace / 'inspection/geometry-recipe.json').write_text(json.dumps(report, indent=1) + '\n')
    print('SOUTH-GATE built', args.asset, [(o['source_node'], o['vertices'], o['faces']) for o in report['objects']])
    if not args.no_packet:
        sys.path.insert(0, str(TOOLING))
        import refinement_workspace
        result = refinement_workspace.modified(workspace)
        print('SOUTH-GATE packet', result['status'], result['modified'])


if __name__ == '__main__':
    main()
