"""Render provenance for completed support bakes using the shared FIFO leases."""
import sys,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'refinement/blender'))
from texture_experiment_paths import selected_experiment
from render_slots import acquire,release
from render_texture_coverage import inspect,sha
for asset in sys.argv[sys.argv.index('--')+1:]:
 p=selected_experiment(asset);b=p/'bake-background-support-001';out=b/'coverage'
 if out.exists():
  if not (out/'coverage.json').exists() or json.loads((out/'coverage.json').read_text())['model_sha256']!=sha(b/'worker.blend'):raise ValueError('Incomplete or stale coverage '+asset)
  continue
 acquire()
 try:
  result=inspect(p/'repair-background-support/views.json',b,out)
  print(asset,[v['unfilled_visible_pixels'] for v in result['views']],flush=True)
 finally:
  release();time.sleep(1.1)
