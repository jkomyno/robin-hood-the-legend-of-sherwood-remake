"""Export baked Sherwood texture candidates without changing the live library."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
EDITOR = HERE.parents[1]
sys.path[:0] = [str(HERE), str(EDITOR/'refinement'), str(EDITOR/'refinement/blender')]
from stage_editor_migration import sha, write, finalize_glb
from export_editor import export_editor
from asset_index import write_asset_index
from verify_editor_handoff import points, deviation
from lossy_assets import read_glb, accessor_array, mesh_instances, refresh_derivatives
import render_slots


def main(baseline, candidate, output):
    baseline, candidate, output = [Path(p).resolve() for p in (baseline, candidate, output)]
    installed = json.loads((baseline/'installation.json').read_text())
    fill = json.loads((candidate/'fill.json').read_text())
    if installed['status'] != 'APPLIED' or not fill['geometry_and_uvs_unchanged']:
        raise ValueError('Missing initial publication or verified texture bake')
    worker = candidate/'candidate.blend'
    if sha(worker) != fill['worker_sha256']:
        raise ValueError('Candidate worker changed since its texture verification')
    output.mkdir(parents=True, exist_ok=False)
    render_slots.acquire()
    bpy.ops.wm.open_mainfile(filepath=str(worker))
    bpy.context.window.scene = bpy.data.scenes['Sherwood Editor Migration']
    groups = {}
    for obj in bpy.data.collections['Sherwood Working'].objects:
        if obj.type == 'MESH':
            groups.setdefault(obj['asset_group'], []).append(obj)
    document = json.loads((baseline/'sherwood.rhlos-map.json').read_text())
    reports = []
    root = output/'map-assets/3d-assets'
    for ref in document['assetSources'] + document['sceneAssets']:
        descriptor = json.loads((baseline/'map-assets'/ref['descriptor']).read_text())
        directory = root/'sherwood'/ref['id']
        model = directory/'model.glb'
        export_editor('Sherwood', model, asset_id=ref['id'],
                      standalone_pivot=descriptor.get('source_origin_scene', [0, 0, 0]))
        finalize_glb(model, descriptor)
        for key in ('lossy_model', 'preview_model'):
            descriptor.pop(key, None)
        descriptor['texture_candidate'] = {
            'status': 'review-pending', 'worker_sha256': fill['worker_sha256'],
            'source_worker_sha256': fill['source_worker_sha256'],
            'fill_report_sha256': sha(candidate/'fill.json'),
        }
        write(directory/'asset.json', descriptor)
        ref['model_sha256'] = sha(model)
        ref['descriptor_sha256'] = sha(directory/'asset.json')
        gltf, binary, _ = read_glb(model)
        instances = mesh_instances(gltf)
        exported, triangles = [], 0
        for index, mesh in enumerate(gltf.get('meshes', [])):
            matrix = instances[index]
            for primitive in mesh['primitives']:
                vertices = accessor_array(gltf, binary, primitive['attributes']['POSITION'], True)
                exported.append(vertices @ matrix[:3, :3].T + matrix[:3, 3]
                                + descriptor.get('source_origin_scene', [0, 0, 0]))
                triangles += len(accessor_array(gltf, binary, primitive['indices'])) // 3
        expected, actual = points(groups[ref['id']]), np.concatenate(exported)
        drift = max(deviation(expected, actual), deviation(actual, expected))
        count = 0
        for obj in groups[ref['id']]:
            obj.data.calc_loop_triangles()
            count += len(obj.data.loop_triangles)
        if drift >= .001 or count != triangles:
            raise ValueError(f'Candidate export changed geometry: {ref["id"]}, {drift}, {count}/{triangles}')
        reports.append({'asset': ref['id'], 'triangles': triangles, 'maximum_world_vertex_drift': drift})
        print(json.dumps(reports[-1]), flush=True)
    write(output/'sherwood.rhlos-map.json', document)
    write_asset_index(root)
    write(output/'texture-handoff.json', {
        'status': 'PASS', 'texture_review': 'pending', 'assets': reports,
        'source_worker_sha256': fill['source_worker_sha256'],
        'candidate_worker_sha256': fill['worker_sha256'], 'live_library_changed': False,
    })
    render_slots.release()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    write(output/'derivatives.json', refresh_derivatives(root, output/'derivatives', lossy=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    main(args.baseline, args.candidate, args.output)
