"""Bake measured base-only candidates and verify their exact untouched atlas data."""
import sys,json,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'refinement/blender'))
import bpy
from texture_experiment_paths import selected_experiment
from render_slots import acquire,release
from bake_ready_textures import claim,sha
from bake_reviewed_asset import stage
from audit_inferred_gap import run as audit
from render_texture_coverage import inspect
for asset in sys.argv[sys.argv.index('--')+1:]:
 p=selected_experiment(asset);scoped=p/'repair-measured-base-v1';out=p/'bake-measured-base-v1'
 contract=json.loads((scoped/'repair-contract.json').read_text());old=Path(contract['previous_bake'])
 if sha(scoped/'views.json')!=contract['manifest_sha256'] or sha(old/'worker.blend')!=contract['previous_model_sha256']:raise ValueError('Repair contract drift')
 handle=claim(p)
 if handle is None:raise RuntimeError('Another bake owns '+asset)
 acquire()
 try:
  if out.exists():raise ValueError('Fresh output required: '+str(out))
  diagnosis=json.loads((scoped/'diagnosis.json').read_text());g=Path(diagnosis['generation_directory'])
  bpy.ops.wm.open_mainfile(filepath=str(scoped/'approved-model.blend'))
  stage(scoped/'views.json',g/'generated-preserved.png',out,texels_per_unit=2,reconciliation_reference=g/'generated-raw.png')
  audit(old,out)
  inspect(scoped/'views.json',out,out/'coverage')
  print('MEASURED BASE BAKED '+asset,flush=True)
 except Exception as exc:
  error=p/'measured-base-error.json'
  error.write_text(json.dumps(dict(status='FAILED-NOT-READY',asset_id=asset,error=str(exc),traceback=traceback.format_exc()),indent=2)+'\n')
  print('MEASURED BASE FAILED '+asset+' '+str(exc),flush=True)
 finally:
  release();handle.close();time.sleep(1.1)
