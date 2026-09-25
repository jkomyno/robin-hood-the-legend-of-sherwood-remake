"""Give painted spire edging compact receivers instead of grazing roof faces.

Builds an isolated, unapproved source-only revision. Original workspaces and
their approval records are never changed. The source masks remain unchanged.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
sys.path[:0] = [str(ROOT / 'level-editor/refinement/blender'), str(Path(__file__).parent)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def topology(obj):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    remaining = set(bm.verts)
    components = 0
    while remaining:
        stack = [remaining.pop()]
        components += 1
        while stack:
            vertex = stack.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
    result = dict(vertices=len(bm.verts), faces=len(bm.faces),
                  nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
                  degenerate_faces=sum(f.calc_area() < 1e-9 for f in bm.faces),
                  connected_components=components, signed_volume=bm.calc_volume(signed=True))
    bm.free()
    return result


def apply_ridges(asset, spec):
    import bpy
    from mathutils import Vector
    from refinement_review import _tree
    from refine_village_secondary import digest, replace
    owned = [o for o in bpy.context.scene.objects
             if o.type == 'MESH' and not o.hide_render and o.get('asset_group') == asset]
    tree, _, _ = _tree(owned)
    before = {o.name: digest(o) for o in bpy.context.scene.objects if o.type == 'MESH'}
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    toward = Vector((0, -cosine, sine))
    parts = []
    for ridge in spec['ridges']:
        matches = [o for o in owned if o.get('source_node') == ridge['source_node']]
        if len(matches) != 1:
            raise ValueError(('Expected one roof receiver', ridge['source_node'], len(matches)))
        obj = matches[0]
        old_topology = topology(obj)
        intercept, slope = ridge['ridge_center_x_by_source_y']
        polygon = ridge['source_polygon']
        front = []
        for x, y in polygon:
            center_x = intercept + slope * y
            origin = Vector((center_x, -y * sine, -y * cosine)) + toward * 10000
            point, _, face, _ = tree.ray_cast(origin, -toward)
            if face is None:
                raise ValueError(('No roof under painted metal ridge', x, y))
            front.append(point + Vector((x - center_x, 0, 0))
                         + toward * spec['front_offset_world'])
        count = len(front)
        vertices = front + [p - toward * spec['metal_depth_world'] for p in front]
        faces = [tuple(range(count)), tuple(reversed(range(count, 2 * count)))]
        faces.extend((i, (i + 1) % count, count + (i + 1) % count, count + i)
                     for i in range(count))
        metal = obj.copy()
        metal.data = obj.data.copy()
        bpy.context.scene.collection.objects.link(metal)
        metal.name = '_temporary compact spire edging'
        replace(metal, vertices, faces, 'Source-fitted compact metal ridge')
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        modifier = obj.modifiers.new('Attach compact metal edging', 'BOOLEAN')
        modifier.operation = 'UNION'
        modifier.solver = 'EXACT'
        modifier.object = metal
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.data.objects.remove(metal, do_unlink=True)
        # Rebuild the fallback UV/material schema before the shared projection pass.
        vertices = [obj.matrix_world @ v.co for v in obj.data.vertices]
        faces = [tuple(p.vertices) for p in obj.data.polygons]
        replace(obj, vertices, faces, 'Roof with attached compact metal edging')
        final = topology(obj)
        if final['nonmanifold_edges'] or final['degenerate_faces'] or final['connected_components'] != 1:
            raise ValueError(('Invalid roof/ridge union', obj.name, final))
        if final['signed_volume'] < old_topology['signed_volume'] - 0.01:
            raise ValueError(('Union unexpectedly removed roof volume', obj.name))
        parts.append(dict(source_node=ridge['source_node'], before=old_topology, after=final))
    changed = [name for name, digest_before in before.items()
               if digest(bpy.data.objects[name]) != digest_before]
    if len(changed) != len(spec['ridges']):
        raise ValueError(('Unexpected changed objects', changed))
    return dict(parts=parts, changed_objects=changed,
                unchanged_objects=len(before) - len(changed), source_masks_changed=False,
                method='Exact Boolean union adds compact metal detail while retaining the original roof volume.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset', required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    traces = Path(__file__).with_name('spire_metal_ridge_traces.json')
    spec = json.loads(traces.read_text())['assets'][args.asset]
    old = WORK / spec['approved_workspace']
    if sha(old / 'model.blend') != spec['approved_model_sha256']:
        raise ValueError('Approved donor model changed')
    if sha(old / 'reference/source.png') != spec['source_sha256']:
        raise ValueError('Source artwork changed')
    new = args.workspace.resolve()
    if new == old.resolve():
        raise ValueError('Output must not be the approved workspace')
    from render_slots import acquire
    acquire(slots=2)
    import bpy
    import refinement_workspace as rw
    config = json.loads((old / 'workspace.json').read_text())
    if not new.exists():
        bpy.ops.wm.open_mainfile(filepath=str(old / 'model.blend'))
        rw.prepare(new, asset_id=args.asset, scene_name=config['scene_name'],
                   collection_name=config['collection_name'], source_path=old / 'reference/source.png',
                   grouping_manifest=old / 'reference/grouping.json',
                   inventory_path=old / 'reference/inventory.json',
                   review_path=old / 'reference/grouping-review.json',
                   source_mask_manifest=old / 'source-masks.json',
                   width=320, height=384, context_padding=25, framing_padding=1.12,
                   lighting=json.loads((WORK / 'lighting-calibration/map-lighting.json').read_text())['lighting'])
    bpy.ops.wm.open_mainfile(filepath=str(new / 'baseline.blend'))
    report = apply_ridges(args.asset, spec)
    (new / 'source-trace.json').write_bytes(traces.read_bytes())
    report.update(asset_id=args.asset, source_trace_sha256=sha(traces),
                  original_model_sha256=spec['approved_model_sha256'],
                  limitations=spec['limitations'], approval_status='pending-new-user-review')
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(new / 'model.blend'))
    rw.modified(new)
    inspection = new / 'inspection'
    inspection.mkdir(exist_ok=True)
    from restore_foreign_uv_schema import restore_foreign_uv_schema
    restore_foreign_uv_schema(new, apply=True)
    from audit_stored_materials import run
    run(new, inspection / 'stored-materials', render=True, export=False)
    report.update(model_sha256=sha(new / 'model.blend'),
                  modified_views_sha256=sha(new / 'modified/views.json'))
    (new / 'geometry-report.json').write_text(json.dumps(report, indent=2) + '\n')
    (new / 'candidate.json').write_text(json.dumps(dict(
        asset_id=args.asset, status='refinement-in-progress', approval_status='pending',
        model_sha256=report['model_sha256'], modified_views_sha256=report['modified_views_sha256'],
        limitations=spec['limitations'], recipe=str(Path(__file__).resolve())), indent=2) + '\n')


if __name__ == '__main__':
    main()
