"""Prove a globally reprojected (or texture-combined) worker differs from its stage-in only in unknown texels.

    blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/verify_global_reprojection.py -- <stage> <report.json>

`<stage>/integration.json` names the stage-in worker (`global_reprojection.stage_in`). Both workers
are compared object by object: names, custom ownership properties, visibility, world vertices,
topology, every UV layer, material slot graphs (node types, links, UV map names, image settings)
and image pixels. Every changed texel must lie in the pass's fill mask for that object/slot and
must have been unknown in the stage-in atlas (opaque neutral gray R=G=B 40..83, or alpha 0 on the
source-projected terrain atlas), except grazing resets
(fill value 3), which must now hold a neutral shade. Non-ownership images
must be byte-identical. Writes the report with status PASS or raises.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot(bpy, keep_pixels):
    working = bpy.data.collections['lincoln Working']
    out = {}
    for obj in working.all_objects:
        if obj.type != 'MESH':
            continue
        mesh = obj.data
        co = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get('co', co)
        m = np.array(obj.matrix_world, dtype=np.float64)
        world = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
        loops = np.empty(len(mesh.loops), dtype=np.int64)
        mesh.loops.foreach_get('vertex_index', loops)
        totals = np.empty(len(mesh.polygons), dtype=np.int64)
        mesh.polygons.foreach_get('loop_total', totals)
        slots = np.empty(len(mesh.polygons), dtype=np.int64)
        mesh.polygons.foreach_get('material_index', slots)
        uv = hashlib.sha256()
        for layer in mesh.uv_layers:
            data = np.empty(len(mesh.loops) * 2, dtype=np.float32)
            layer.data.foreach_get('uv', data)
            uv.update(layer.name.encode() + b'\0' + data.tobytes())
        materials, pixels = [], {}
        used = set(slots.tolist())
        for index, material in enumerate(mesh.materials):
            if material is None or material.node_tree is None:
                materials.append(None)
                continue
            nodes = sorted([n.type, getattr(n, 'uv_map', '') or '',
                            json.dumps([n.image.colorspace_settings.name, n.image.alpha_mode, list(n.image.size),
                                        bool(n.image.packed_file)]) if n.type == 'TEX_IMAGE' and n.image else '']
                           for n in material.node_tree.nodes)
            links = sorted([l.from_node.type, l.from_socket.identifier, l.to_node.type, l.to_socket.identifier]
                           for l in material.node_tree.links)
            props = {k: material[k] for k in ('source_ownership_bake', 'source_ownership_label', 'source_ownership_fill')
                     if k in material}
            materials.append(hashlib.sha256(json.dumps([nodes, links, props], default=str).encode()).hexdigest())
            if keep_pixels and index in used:
                images = [n.image for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
                if len(images) == 1:
                    image = images[0]
                    buffer = np.empty(image.size[0] * image.size[1] * 4, dtype=np.float32)
                    image.pixels.foreach_get(buffer)
                    pixels[index] = np.rint(buffer.reshape(image.size[1], image.size[0], 4) * 255).astype(np.uint8)
        out[obj.name] = {
            'props': [obj.get(k) for k in ('asset_group', 'source_node', 'projection_component')],
            'hide': [obj.hide_render, obj.hide_viewport],
            'world': hashlib.sha256(world.tobytes()).hexdigest(),
            'topology': hashlib.sha256(loops.tobytes() + totals.tobytes() + slots.tobytes()).hexdigest(),
            'uv': uv.hexdigest(), 'materials': materials, 'pixels': pixels}
    return out


def main(stage, report_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_slots import acquire
    acquire()
    import bpy
    stage = Path(stage).resolve(strict=True)
    integration = json.loads((stage / 'integration.json').read_text())
    # A texture-combine stage (generated fill on top of a global reprojection) has no fill masks:
    # every changed texel must simply have been unknown in its stage-in atlas.
    combine = 'texture_combine' in integration
    record = integration['texture_combine' if combine else 'global_reprojection']
    stage_in = Path(record['stage_in'])
    if sha(stage / 'worker.blend') != integration['worker_sha256']:
        raise ValueError('Staged worker changed after global reprojection')
    if sha(stage_in / 'worker.blend') != record['stage_in_worker_sha256']:
        raise ValueError('Stage-in worker changed')
    if sha(record['report']) != record['report_sha256']:
        raise ValueError('Stage report changed')
    report = {'objects': []} if combine else json.loads(Path(record['report']).read_text())
    fills = {}
    for row in report['objects']:
        for slot in row['slots']:
            if slot['kind'] == 'ownership' and slot.get('fill_mask'):
                path = Path(slot['fill_mask']['path'])
                if sha(path) != slot['fill_mask']['sha256']:
                    raise ValueError('Fill mask changed: ' + str(path))
                fills[(row['object'], slot['slot'])] = path
    bpy.ops.wm.open_mainfile(filepath=str(stage_in / 'worker.blend'))
    before = snapshot(bpy, True)
    bpy.ops.wm.open_mainfile(filepath=str(stage / 'worker.blend'))
    after = snapshot(bpy, True)
    if set(before) != set(after):
        raise RuntimeError('Object set changed')
    changed_texels, reset_texels, objects_changed, failures = 0, 0, 0, []
    for name, old in before.items():
        new = after[name]
        for key in ('props', 'hide', 'world', 'topology', 'uv', 'materials'):
            if old[key] != new[key]:
                failures.append(f'{name}: {key} changed')
        if set(old['pixels']) != set(new['pixels']):
            failures.append(f'{name}: textured slots changed')
            continue
        touched = False
        for slot, pixels in old['pixels'].items():
            other = new['pixels'][slot]
            if pixels.shape != other.shape:
                failures.append(f'{name} slot {slot}: atlas size changed')
                continue
            diff = np.any(pixels != other, axis=2)
            if not diff.any():
                continue
            touched = True
            def neutral(values):
                rgb = values.astype(np.int16)
                # Face-island atlases shade unknown texels opaque gray; the source-projected
                # terrain atlas marks them with alpha 0.
                return (((rgb[:, 0] == rgb[:, 1]) & (rgb[:, 1] == rgb[:, 2]) & (rgb[:, 3] == 255)
                         & (rgb[:, 0] >= 40) & (rgb[:, 0] <= 83)) | (rgb[:, 3] == 0))
            if combine:
                if not neutral(pixels[diff]).all():
                    failures.append(f'{name} slot {slot}: {int((~neutral(pixels[diff])).sum())} known texels overwritten')
                changed_texels += int(diff.sum())
                continue
            if (name, slot) not in fills:
                failures.append(f'{name} slot {slot}: pixels changed without fill mask')
                continue
            fill = np.load(fills[(name, slot)])['fill']
            if np.any(diff & (fill == 0)):
                failures.append(f'{name} slot {slot}: {int((diff & (fill == 0)).sum())} texels changed outside fill mask')
            filled = diff & ((fill == 1) | (fill == 2))
            if not neutral(pixels[filled]).all():
                failures.append(f'{name} slot {slot}: {int((~neutral(pixels[filled])).sum())} non-neutral texels filled')
            reset = diff & (fill == 3)
            if not neutral(other[reset]).all():
                failures.append(f'{name} slot {slot}: grazing reset left {int((~neutral(other[reset])).sum())} non-neutral texels')
            reset_texels += int(reset.sum())
            changed_texels += int(diff.sum())
        objects_changed += touched
    result = {'status': 'FAIL' if failures else 'PASS', 'stage': str(stage),
              'worker_sha256': integration['worker_sha256'], 'stage_in': str(stage_in),
              'stage_in_worker_sha256': record['stage_in_worker_sha256'],
              'objects': len(before), 'objects_with_changed_texels': objects_changed,
              'changed_texels': changed_texels, 'grazing_reset_texels': reset_texels, 'failures': failures[:200],
              'mode': 'texture-combine' if combine else 'global-reprojection',
              'comparison': 'Names, ownership properties, visibility, world vertices, topology, all UV layers and '
                            'material slot graphs exact; ' + (
                                'texels change only where the stage-in atlas was unknown.' if combine else
                                'texels change only inside fill masks: from neutral gray (fills) or to neutral gray (grazing resets).')}
    Path(report_path).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'objects', 'objects_with_changed_texels', 'changed_texels')}))
    if failures:
        raise RuntimeError('Global reprojection verification failed: ' + '; '.join(failures[:5]))


if __name__ == '__main__':
    main(*sys.argv[sys.argv.index('--') + 1:])
