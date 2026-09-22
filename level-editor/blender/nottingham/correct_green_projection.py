"""Correct a reviewed hatch mask while proving approved geometry is unchanged."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
select_tooling()
from render_slots import acquire
acquire()
import bpy
import refinement_workspace as rw

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'level-editor/work/nottingham-refinement'
WORKSPACE = BASE / 'round-1/assets/nottingham-southeast-green-house'
APPROVED = BASE / 'approval-evidence/nottingham-southeast-green-house/3af313c29d7c/model.blend'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry():
    records = {}
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        records[obj.name] = {
            'vertices': [list(v.co) for v in obj.data.vertices],
            'faces': [list(p.vertices) for p in obj.data.polygons],
            'matrix_world': [list(row) for row in obj.matrix_world],
        }
    return records


def geometry_sha(records):
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def main():
    approved_hash = sha(APPROVED)
    if approved_hash != '3af313c29d7c2fb5e19b742064ec6f09634087820aa6b5dcefcbc75d5e6adf2f':
        raise ValueError('Approved model evidence changed')
    bpy.ops.wm.open_mainfile(filepath=str(APPROVED))
    before = geometry()
    config = json.loads((WORKSPACE / 'workspace.json').read_text())
    sidecar = json.loads((BASE / 'mask-review/green-front-overrides-v5.json').read_text())
    path = Path(config['source_mask_manifest'])
    masks = json.loads(path.read_text())
    authority = masks['projections']['exterior']
    if authority['source_sha256'] != sidecar['source_sha256']:
        raise ValueError('Hatch source evidence changed')
    if {entry['source_node'] for entry in sidecar['assignments']} != {'building-045'}:
        raise ValueError('Correction exceeds reviewed receiver')
    authority['assignments'] = [entry for entry in authority['assignments']
                                if entry['source_node'] != 'building-045'] + sidecar['assignments']
    path.write_text(json.dumps(masks, indent=2) + '\n')
    bpy.context.window.scene = bpy.data.scenes[config['scene_name']]
    bpy.ops.wm.save_as_mainfile(filepath=str(WORKSPACE / 'model.blend'))
    rw.modified(WORKSPACE)
    after = geometry()
    if before != after:
        raise ValueError('Projection correction changed mesh geometry or world transforms')
    report = {
        'version': 1, 'status': 'awaiting-visual-inspection',
        'approved_model_sha256': approved_hash,
        'model_sha256': sha(WORKSPACE / 'model.blend'),
        'geometry_before_sha256': geometry_sha(before),
        'geometry_after_sha256': geometry_sha(after),
        'changes': ['Changed building045 exterior ownership from house masks42/43 to its own native hatch mask45.'],
        'inspected_views': [], 'mesh_count': len(before),
        'recipe_sha256': sha(__file__),
    }
    (WORKSPACE / 'projection-correction.json').write_text(json.dumps(report, indent=2) + '\n')
    print('GREEN HATCH PROJECTION CORRECTION: GEOMETRY IDENTICAL', flush=True)


if __name__ == '__main__':
    main()
