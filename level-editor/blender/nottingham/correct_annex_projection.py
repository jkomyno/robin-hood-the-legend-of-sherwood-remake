"""Rebaseline an annex mask inventory without changing its refined geometry."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'level-editor/work/nottingham-refinement'
sys.path.insert(0, str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
TOOLING = select_tooling(BASE / 'tooling-common-v1/2fbc2cbceea1fd2d')
from render_slots import acquire
acquire()
import bpy
import refinement_workspace as rw
from correct_source_projection import geometry, geometry_sha


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    old = BASE / 'round-1/assets/nottingham-southeast-stone-annex'
    new = BASE / 'round-10/assets/nottingham-southeast-stone-annex'
    cfg = json.loads((old / 'workspace.json').read_text())
    previous_model_hash = sha(old / 'model.blend')
    authority = BASE / 'mask-review/source-masks-v11-annex-wall.json'
    bpy.ops.wm.open_mainfile(filepath=str(old / 'baseline.blend'))
    rw.prepare(new, asset_id=cfg['asset_id'], scene_name=cfg['scene_name'],
               collection_name=cfg['collection_name'], source_path=old / 'reference/source.png',
               grouping_manifest=old / 'reference/grouping.json',
               inventory_path=old / 'reference/inventory.json',
               review_path=old / 'reference/grouping-review.json',
               source_mask_manifest=authority, width=cfg['width'], height=cfg['height'],
               elevation_degrees=cfg['elevation_degrees'], context_padding=cfg['context_padding'])
    bpy.ops.wm.open_mainfile(filepath=str(old / 'model.blend'))
    before = geometry()
    bpy.context.window.scene = bpy.data.scenes[cfg['scene_name']]
    bpy.ops.wm.save_as_mainfile(filepath=str(new / 'model.blend'))
    validation = rw.modified(new)
    after = geometry()
    if before != after or sha(old / 'model.blend') != previous_model_hash:
        raise ValueError('Geometry or preserved previous model changed')
    report = {'version': 1, 'asset_id': cfg['asset_id'],
              'status': 'awaiting-visual-inspection', 'inspected_views': [],
              'previous_workspace': str(old), 'previous_model_sha256': previous_model_hash,
              'model_sha256': sha(new / 'model.blend'),
              'geometry_before_sha256': geometry_sha(before),
              'geometry_after_sha256': geometry_sha(after), 'mesh_count': len(before),
              'changes': ['Created a fresh immutable authority including reviewed authored mask543 for the visible stone buttress on receiver050.'],
              'authority': str(authority), 'authority_sha256': sha(authority),
              'tooling': TOOLING, 'recipe_sha256': sha(__file__)}
    (new / 'projection-correction.json').write_text(json.dumps(report, indent=2) + '\n')
    candidate = json.loads((old / 'candidate.json').read_text())
    candidate.update(status='refinement-in-progress', projection_fix_status='awaiting-visual-inspection',
                     projection_correction='projection-correction.json',
                     model_sha256=report['model_sha256'], modified_views_sha256=sha(new / 'modified/views.json'))
    for name in ['recipe.py', 'review.md', 'geometry-report.json']:
        if (old / name).is_file():
            shutil.copy2(old / name, new / name)
    (new / 'candidate.json').write_text(json.dumps(candidate, indent=2) + '\n')
    (new / 'preparation.json').write_text(json.dumps({'version': 1, 'tooling': TOOLING,
        'previous_workspace': str(old), 'validation': validation}, indent=2) + '\n')
    print('ANNEX REBASELINE: GEOMETRY IDENTICAL', flush=True)


if __name__ == '__main__':
    main()
