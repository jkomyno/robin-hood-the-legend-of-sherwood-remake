"""Rebuild the source-measured pointed church arch on its native wall plane.

Run refine(workspace, root) in the isolated worker model, then the shared
modified packet and material audit. This recipe does not render or approve.
"""
import hashlib
import json
import math
from pathlib import Path
import argparse
import shutil
import sys

RECIPE = 'native-mask-pointed-arch-v1'
NODES = [f'building-{i}' for i in range(351, 355)]


def refine(workspace, root):
    import bpy
    import bmesh
    from mathutils import Vector
    from PIL import Image
    import refinement_workspace as worker

    workspace, root = Path(workspace), Path(root)
    config = json.loads((workspace / 'workspace.json').read_text())
    if config['asset_id'] != 'leicester-church-west-archway':
        raise ValueError('Wrong archway workspace')
    worker.validate(workspace)
    objects, _ = worker._ownership(config)
    by_node = {o['source_node']: o for o in objects}
    if set(by_node) != set(NODES) or len(objects) != 4:
        raise ValueError('Expected four unique native archway pieces')
    if all(o.get('archway_recipe') == RECIPE for o in objects):
        return {'reused': True, 'source_nodes': NODES}
    if any(o.get('archway_recipe') for o in objects):
        raise ValueError('Mixed archway recipe revisions')
    level_file = root / 'source-audit/Leicester.rhp.json'
    level = json.loads(level_file.read_text())
    mask_file = root / 'source-audit/native-masks/000245.png'
    if mask_file.read_bytes() != (root / 'source-audit/native-masks/000251.png').read_bytes():
        raise ValueError('Archway layer masks changed')
    alpha = Image.open(mask_file).convert('L')
    # The explicitly open black region begins at x939 and ends at x986.
    # Measure its arch boundary, not the exterior bottom edge or foliage.
    contour = []
    for x in range(939, 987):
        ys = [y for y in range(700, 781) if alpha.getpixel((x-895, y-654)) == 0]
        if not ys:
            raise ValueError(f'Missing measured opening column {x}')
        contour.append((float(x), float(min(ys))))
    if min(contour, key=lambda p: p[1]) != (957., 717.):
        raise ValueError('Measured pointed apex changed')
    p0, p1 = level['sight_obstacles'][351]['points'][2:4]
    p2 = level['sight_obstacles'][354]['points'][1]
    slope = (p2['y']-p0['y'])/(p2['x']-p0['x'])
    front_y = lambda x: p0['y'] + (x-p0['x'])*slope
    dx, dy = p1['x']-p0['x'], p1['y']-p0['y']
    front_top, back_top = p0['z_top'], p1['z_top']
    floor = level['sight_obstacles'][123]['points'][0]['z_top']
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    # One-pixel samples preserve the measured shape. Hidden back intrados
    # keeps the same elevation across native wall thickness: explicit inference.
    opening = [(x, front_y(x)-y) for x, y in contour]
    profiles = [
        [(p0['x'], floor), (939., floor)],
        [p for p in opening if p[0] <= 957.],
        [p for p in opening if p[0] >= 957.],
        [(986., floor), (p2['x'], floor)],
    ]
    reports = []
    for node, underside in zip(NODES, profiles):
        obj = by_node[node]
        matrix = obj.matrix_world.copy()
        inverse = matrix.inverted()
        before = worker._geometry(obj)
        profile = underside + [(underside[-1][0], front_top), (underside[0][0], front_top)]
        vertices = []
        for back in (False, True):
            for index, (x, z) in enumerate(profile):
                # Only the tiled top rises across the wall thickness.
                zz = back_top if back and index >= len(underside) else z
                xx, yy = x + (dx if back else 0), front_y(x) + (dy if back else 0)
                vertices.append(inverse @ Vector((xx, -yy/sine, zz/cosine)))
        n = len(profile)
        faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
        faces += [(i, (i+1) % n, (i+1) % n+n, i+n) for i in range(n)]
        mesh = bpy.data.meshes.new(f'{node} measured pointed arch')
        mesh.from_pydata(vertices, [], faces)
        for material in obj.data.materials:
            mesh.materials.append(material)
        mesh.uv_layers.new(name='Projection pending')
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bad = sum(not e.is_manifold for e in bm.edges)
        degenerate = sum(f.calc_area() < 1e-8 for f in bm.faces)
        if bad or degenerate:
            bm.free()
            raise ValueError(f'Invalid archway topology {node}: {bad}, {degenerate}')
        bm.to_mesh(mesh)
        bm.free()
        obj.data = mesh
        obj['archway_recipe'] = RECIPE
        if obj.matrix_world != matrix:
            raise ValueError('Archway transform changed')
        reports.append(dict(source_node=node, before=before, after=worker._geometry(obj),
                            vertices=len(mesh.vertices), faces=len(mesh.polygons),
                            nonmanifold_edges=bad, degenerate_faces=degenerate, transform_drift=0))
    outside = worker.validate(workspace)
    report = dict(recipe=RECIPE, objects=reports, opening_source_contour=contour,
                  floor_game_height=floor, native_depth_game=[dx, dy],
                  source_mask_sha256=hashlib.sha256(mask_file.read_bytes()).hexdigest(),
                  source_level_sha256=hashlib.sha256(level_file.read_bytes()).hexdigest(),
                  outside_validation=outside, state='static, identical layer0/layer1 silhouette; no patch membership',
                  limitations=['Back intrados keeps front elevation across native depth; unseen thickness is inferred.',
                               'No individual stone relief or tile thickness inferred from painted detail.',
                               'Foliage-obscured left pier remains native planar wall, without invented ivy volume.'])
    (workspace / 'archway-report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def main():
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'refine'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    root, workspace = args.root.resolve(), args.workspace.resolve()
    sys.path.insert(0, str(root.parents[1] / 'blender'))
    import refinement_workspace as worker
    if args.phase == 'prepare':
        worker.prepare(workspace, asset_id='leicester-church-west-archway',
                       scene_name='Leicester Refinement', collection_name='Leicester Working',
                       source_path=str(root / 'layers/covered.png'),
                       grouping_manifest=str(root / 'catalog/catalog.json'),
                       inventory_path=str(root / 'round-1/preflight/inventory/inventory.json'),
                       review_path=str(root / 'catalog/grouping-review.json'),
                       source_mask_manifest=str(root / 'round-1/archway-inspection/source-masks.json'),
                       width=384, height=256)
        return
    if Path(bpy.data.filepath).resolve() != workspace / 'model.blend':
        raise ValueError('Open isolated worker model.blend')
    report = refine(workspace, root)
    before = {o['source_node']: worker._geometry(o) for o in worker._ownership(
        json.loads((workspace / 'workspace.json').read_text()))[0]}
    repeated = refine(workspace, root)
    after = {o['source_node']: worker._geometry(o) for o in worker._ownership(
        json.loads((workspace / 'workspace.json').read_text()))[0]}
    if before != after or not repeated.get('reused'):
        raise ValueError('Archway recipe is not idempotent')
    report['idempotence'] = 'PASS: repeated recipe leaves all four geometry hashes unchanged'
    (workspace / 'archway-report.json').write_text(json.dumps(report, indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    worker.modified(workspace)
    from leicester.verify_candidate import verify
    verify(workspace)
    shutil.copy2(__file__, workspace / 'recipe.py')
    ownership = max((p for p in (workspace / 'projection').glob('*/ownership.json')
                     if p.parent.name != 'input'), key=lambda p:p.stat().st_mtime_ns)
    handoff = dict(status='validation-pending', all_eight_views_inspected=False,
                   recipe='recipe.py', ownership=str(ownership.relative_to(workspace)),
                   geometry_approval='pending', texture_generation='not-started', has_revealed_state=False,
                   notes=['Source-measured pointed arch; native wall depth and sloped cap retained.',
                          'Courtyard contact corrected; hidden back intrados depth remains inferred.'])
    (workspace / 'handoff.json').write_text(json.dumps(handoff, indent=2)+'\n')


if __name__ == '__main__':
    main()
