"""Resume reviewed static texture bakes, preserving each attempt and its evidence."""
import argparse
import fcntl
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT/'level-editor/refinement/blender'))
from render_slots import acquire


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(path)


def update_ledger(path, asset, record):
    with path.with_suffix('.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current=json.loads(path.read_text()) if path.exists() else dict(version=1,assets={})
        current['assets'][asset]=record
        current['updated_utc']=datetime.now(timezone.utc).isoformat()
        write(path,current)


def reviewed_inputs(experiment, asset_id):
    review_path = experiment/'generation-review.json'
    if not review_path.exists():
        return None
    review = json.loads(review_path.read_text())
    if review.get('status') != 'ready-for-bake':
        return None
    if review.get('asset_id') != asset_id or review.get('all_eight_views_inspected') is not True:
        raise ValueError('Generation review lacks matching identity or eight-view inspection')
    bindings = {'input_sha256':experiment/'input.png', 'views_sha256':experiment/'views.json',
                'solid_sha256':experiment/'solid.png',
                'generated_preserved_sha256':Path(review['generated_preserved_path']),
                'generated_raw_sha256':Path(review['generated_raw_path'])}
    for key, path in bindings.items():
        if review.get(key) != sha(path):
            raise ValueError('Generation review binding changed: '+key)
    return review, sha(review_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--jobs',type=Path,default=ROOT/'level-editor/work/nottingham-refinement/texture-generation/preparation-jobs.json')
    parser.add_argument('--limit',type=int,default=0)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    ledger_path=args.jobs.parent/'static-bake-jobs.json'
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else dict(version=1,assets={})
    def persist(asset, record):
        update_ledger(ledger_path,asset,record)
    acquire()
    import bpy
    from bake_reviewed_asset import stage
    count=0
    for job in json.loads(args.jobs.read_text())['assets']:
        if job.get('status') == 'separate-lane' or not job.get('experiment'):
            continue
        asset=job['asset_id']; experiment=Path(job['experiment'])
        try:
            bound=reviewed_inputs(experiment,asset)
            if bound is None:
                continue
            review, review_hash=bound
            old=ledger['assets'].get(asset,{})
            if old.get('generation_review_sha256') == review_hash and old.get('status') in ('baked-awaiting-visual-review','ready-for-user-texture-review','needs-refinement','failed'):
                continue
            index=1
            while (experiment/f'bake-batch-{index:03d}').exists():
                index+=1
            output=experiment/f'bake-batch-{index:03d}'
            record=dict(asset_id=asset,experiment=str(experiment),output=str(output),generation_review_sha256=review_hash,status='baking',started_utc=datetime.now(timezone.utc).isoformat())
            ledger['assets'][asset]=record;persist(asset,record)
            bpy.ops.wm.open_mainfile(filepath=str(experiment/'approved-model.blend'))
            report=stage(experiment/'views.json',review['generated_preserved_path'],output,texels_per_unit=2,reconciliation_reference=review['generated_raw_path'])
            # Re-check the external generation review after a long-running bake.
            if reviewed_inputs(experiment,asset)[1] != review_hash:
                raise ValueError('Generation review changed during bake')
            record.update(status='baked-awaiting-visual-review',model_sha256=sha(output/'worker.blend'),actual_sheet_sha256=sha(output/'actual/textured.png'),validation_sha256=sha(output/'validation.json'),geometry_verified=report['geometry_verified'],outside_objects_unchanged=report['outside_objects_unchanged'],counts=report['counts'])
            print('BAKED '+asset+' '+str(output),flush=True)
        except Exception as error:
            traceback.print_exc()
            record=ledger['assets'].setdefault(asset,dict(asset_id=asset))
            record.update(status='failed',error=str(error))
        persist(asset,record)
        count+=1
        if args.limit and count>=args.limit:
            break

if __name__=='__main__':
    main()
