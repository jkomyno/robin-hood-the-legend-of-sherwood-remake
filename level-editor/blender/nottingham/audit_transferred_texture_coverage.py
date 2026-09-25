"""Render an existing transferred atlas with its exact saved provenance supplement."""
import sys,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parents[1]/'refinement/blender')]
from audit_ready_texture_coverage import OUT,sha
from render_slots import acquire,release
from render_texture_coverage import inspect
asset=sys.argv[sys.argv.index('--')+1]
row=next(r for r in json.loads((OUT/'jobs.json').read_text())['skips'] if r.get('asset_id')==asset)
bake=Path(row['bake']);validation=json.loads((bake/'validation.json').read_text());manifest=next(Path(p)for p in validation['evidence_sha256']if Path(p).name=='views.json');proof=bake/'provenance-supplement-v1/report.json';e=json.loads(proof.read_text())
assert e['status']=='PASS' and e['model_sha256']==sha(bake/'worker.blend')==row['model_sha256']
assert e['transfer_validation_sha256']==sha(bake/'validation.json')
for p,digest in e['inputs_sha256'].items():assert sha(p)==digest,p
acquire()
try:
 output=OUT/'legacy-replay'/asset/'coverage-transfer'
 report=inspect(manifest,bake,output,provenance_reports=[proof]);print(report['views'],flush=True)
finally:release()
