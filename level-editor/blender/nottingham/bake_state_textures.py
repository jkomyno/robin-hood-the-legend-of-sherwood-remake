"""Bake independently reviewed state images, keeping every state worker separate."""
import json
from pathlib import Path
import sys
import traceback
import time

ROOT = Path(__file__).resolve().parents[3]
GEN = ROOT / 'level-editor/work/nottingham-refinement/texture-generation'
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / 'level-editor/refinement/blender'))
from bake_ready_textures import reviewed_inputs, sha, write, claim
from render_slots import acquire, release


def main():
    import bpy
    from bake_reviewed_asset import stage
    ledger_path = GEN / 'state-bake-jobs.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'version': 1, 'states': {}}
    for job in json.loads((GEN / 'state-preparation-jobs.json').read_text())['jobs']:
        key = job['asset_id'] + '/' + job['state']
        experiment = Path(job['experiment'])
        lock = claim(experiment)
        if lock is None:
            continue
        try:
            bound = reviewed_inputs(experiment, job['asset_id'])
            if bound is None:
                continue
            review, review_hash = bound
            output = experiment / 'bake-v1'
            if output.exists() and not (output / 'validation.json').exists():
                raise ValueError('Incomplete bake retained; inspect before retrying')
            if not output.exists():
                acquire()
                ledger['states'][key] = dict(asset_id=job['asset_id'], state=job['state'], status='baking', output=str(output))
                write(ledger_path, ledger)
                bpy.ops.wm.open_mainfile(filepath=str(experiment / 'approved-model.blend'))
                stage(experiment / 'views.json', review['generated_preserved_path'], output,
                      texels_per_unit=2, reconciliation_reference=review['generated_raw_path'])
            validation = json.loads((output / 'validation.json').read_text())
            if reviewed_inputs(experiment, job['asset_id'])[1] != review_hash:
                raise ValueError('Generation review changed during bake')
            if validation['generated_sha256'] != review['generated_preserved_sha256']:
                raise ValueError('Existing bake used a different generated image')
            ledger['states'][key] = dict(asset_id=job['asset_id'], state=job['state'],
                status='baked-awaiting-visual-review', output=str(output), experiment=str(experiment),
                generation_review_sha256=review_hash, geometry_revision=job['geometry_revision'],
                preparation_revision=job['preparation_revision'], model_sha256=sha(output / 'worker.blend'),
                actual_sheet_sha256=sha(output / 'actual/textured.png'), validation_sha256=sha(output / 'validation.json'))
            print('BAKED STATE ' + key, flush=True)
        except Exception as error:
            traceback.print_exc()
            ledger['states'][key] = dict(asset_id=job['asset_id'], state=job['state'], status='failed', error=str(error))
        finally:
            write(ledger_path, ledger)
            lock.close()
            release()
            time.sleep(1.1)


if __name__ == '__main__':
    main()
