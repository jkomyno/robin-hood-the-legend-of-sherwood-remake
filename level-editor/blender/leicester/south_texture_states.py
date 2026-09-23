"""Verify gatehouse interior preservation and render both baked display states."""
import hashlib
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement' / 'blender'))
from audit_stored_materials import inspect, run
from bake_reviewed_asset import _materials


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(model, names):
    bpy.ops.wm.open_mainfile(filepath=str(model), load_ui=False)
    objects = [bpy.data.objects[name] for name in names]
    records, problems = inspect(objects)
    if problems:
        raise RuntimeError(problems)
    return {'materials_and_uvs': {o.name: _materials(o) for o in objects},
            'stored_atlases': records}


def main(experiment, bake):
    experiment, bake = Path(experiment).resolve(), Path(bake).resolve()
    manifest = json.loads((experiment / 'views-exterior-v2.json').read_text())
    original = Path(manifest['reviewed_packet']).parent
    protected = sorted(set(manifest['object_names']) - set(manifest['texture_receiver_object_names']))
    if not protected:
        raise ValueError('Expected explicit protected gatehouse interior objects')
    before = snapshot(experiment / 'approved-model.blend', protected)
    after = snapshot(bake / 'worker.blend', protected)
    if before != after:
        raise RuntimeError('Covered texture bake changed protected interior materials, atlas pixels or UVs')
    workspace = bake / 'state-audit-workspace'
    workspace.mkdir()
    (workspace / 'model.blend').symlink_to(bake / 'worker.blend')
    (workspace / 'workspace.json').write_bytes((original / 'workspace.json').read_bytes())
    for state in ('covered', 'revealed'):
        frame = original / f'inspection/states/patch-004/{state}/views.json'
        names = json.loads(frame.read_text())['render_object_names']
        report = run(workspace, bake / f'actual-{state}', render=True, export=True,
                     render_object_names=names, frame_manifest=frame)
        if report['status'] != 'STRUCTURAL-PASS':
            raise RuntimeError(report['problems'])
    report = {'status': 'PASS', 'asset_id': manifest['asset_id'],
              'baked_model_sha256': digest(bake / 'worker.blend'),
              'approved_model_sha256': digest(experiment / 'approved-model.blend'),
              'original_material_uv_preservation': True,
              'protected_objects': protected, 'before': before, 'after': after,
              'visual_review': 'pending'}
    (bake / 'state-preservation.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main(*sys.argv[sys.argv.index('--') + 1:])
