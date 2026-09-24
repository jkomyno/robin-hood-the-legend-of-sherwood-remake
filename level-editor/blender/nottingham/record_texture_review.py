"""Record a human/agent visual inspection after inspecting the actual eight views."""
import argparse
import os
import json
from pathlib import Path
from bake_ready_textures import ROOT, sha, write, update_ledger


def record(asset, status, observations):
    ledger_path=ROOT/'level-editor/work/nottingham-refinement/texture-generation/static-bake-jobs.json'
    job=json.loads(ledger_path.read_text())['assets'][asset]
    output=Path(job['output']);validation=json.loads((output/'validation.json').read_text())
    for name,path in [('model_sha256',output/'worker.blend'),('actual_sheet_sha256',output/'actual/textured.png'),('validation_sha256',output/'validation.json')]:
        if job[name]!=sha(path):raise ValueError('Baked artifact changed: '+name)
    report=dict(asset_id=asset,status=status,approval='pending-user-texture-review',publication='not-published',
        all_eight_actual_material_views_inspected=True,inspected_views=list(range(8)),observations=observations,
        geometry_verified=validation['geometry_verified'],outside_objects_unchanged=validation['outside_objects_unchanged'],
        source_preservation=validation['source_preservation'],counts=validation['counts'],
        model_sha256=job['model_sha256'],actual_sheet_sha256=job['actual_sheet_sha256'],validation_sha256=job['validation_sha256'],
        generation_review_sha256=job['generation_review_sha256'],
        limitations=['Generated hidden surface details are inferred, not recovered original artwork.',
            'Unfilled atlas counts include padding and surfaces unseen in the eight cameras; the eight-view inspection does not prove underside completeness.',
            'Texture approval is separate from the earlier geometry approval.'])
    write(output/'texture-review.json',report)
    experiment=Path(job['experiment'])
    generation=json.loads((experiment/'generation-review.json').read_text())
    gallery=dict(status='ready-for-user' if status=='ready-for-user-texture-review' else 'fix-needed',bake=str(output.relative_to(experiment)),generation=os.path.relpath(Path(generation['generated_preserved_path']).parent,experiment),all_eight_actual_views_inspected=True,actual_sheet_sha256=job['actual_sheet_sha256'],baked_model_sha256=job['model_sha256'],notes=observations)
    write(experiment/'texture-review.json',gallery)
    job.update(status=status,texture_review=str(output/'texture-review.json'),texture_review_sha256=sha(output/'texture-review.json'))
    update_ledger(ledger_path,asset,job)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('asset');parser.add_argument('status',choices=['ready-for-user-texture-review','needs-refinement']);parser.add_argument('observations',nargs='+');args=parser.parse_args()
    record(args.asset,args.status,args.observations)
