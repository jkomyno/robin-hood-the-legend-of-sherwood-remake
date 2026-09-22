"""Apply owned reviewed mask assignments without changing mesh geometry."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
select_tooling()
from render_slots import acquire
acquire()
import bpy
import refinement_workspace as rw


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry():
    return {o.name: {'vertices': [list(v.co) for v in o.data.vertices],
                     'faces': [list(p.vertices) for p in o.data.polygons],
                     'matrix_world': [list(r) for r in o.matrix_world]}
            for o in bpy.data.objects if o.type == 'MESH'}


def geometry_sha(records):
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def main(workspace, sidecars):
    workspace = workspace.resolve()
    config = json.loads((workspace / 'workspace.json').read_text())
    model = workspace / 'model.blend'
    before_hash = sha(model)
    previous = workspace / 'projection-correction-reference' / before_hash[:12]
    if not previous.exists():
        previous.mkdir(parents=True)
        shutil.copy2(model, previous / 'model.blend')
        shutil.copytree(workspace / 'modified', previous / 'modified')
        shutil.copy2(workspace / 'source-masks.json', previous / 'source-masks.json')
        shutil.copy2(workspace / 'candidate.json', previous / 'candidate.json')
    candidate_path = workspace / 'candidate.json'
    candidate = json.loads(candidate_path.read_text())
    candidate['status'] = 'refinement-in-progress'
    candidate['projection_fix_status'] = 'regenerating-reviewed-mask-correction'
    candidate_path.write_text(json.dumps(candidate, indent=2) + '\n')
    bpy.ops.wm.open_mainfile(filepath=str(model))
    before = geometry()
    mask_path = Path(config['source_mask_manifest'])
    masks = json.loads(mask_path.read_text())
    changes = []
    for path in sidecars:
        sidecar = json.loads(path.read_text())
        label = sidecar['projection']
        authority = masks['projections'][label]
        if authority['source_sha256'] != sidecar['source_sha256']:
            raise ValueError('Reviewed source hash changed')
        entries = [e for e in sidecar['assignments'] if e['source_node'] in config['part_ids']]
        if not entries:
            raise ValueError('Sidecar has no owned receivers')
        nodes = {e['source_node'] for e in entries}
        old = [e for e in authority['assignments'] if e['source_node'] in nodes]
        authority['assignments'] = [e for e in authority['assignments'] if e['source_node'] not in nodes] + entries
        changes.append({'sidecar': str(path.resolve()), 'sha256': sha(path),
                        'projection': label, 'before': old, 'after': entries})
    mask_path.write_text(json.dumps(masks, indent=2) + '\n')
    bpy.context.window.scene = bpy.data.scenes[config['scene_name']]
    rw.modified(workspace)
    after = geometry()
    if before != after:
        raise ValueError('Projection correction changed vertices, faces or world transforms')
    report = {'version': 1, 'asset_id': config['asset_id'],
              'status': 'awaiting-visual-inspection', 'inspected_views': [],
              'previous_model_sha256': before_hash, 'model_sha256': sha(model),
              'geometry_before_sha256': geometry_sha(before),
              'geometry_after_sha256': geometry_sha(after),
              'reference': str(previous), 'changes': changes,
              'recipe_sha256': sha(__file__), 'mesh_count': len(before)}
    (workspace / 'projection-correction.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PROJECTION CORRECTION: GEOMETRY IDENTICAL ' + config['asset_id'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    parser.add_argument('sidecars', nargs='+', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    main(args.workspace, args.sidecars)
