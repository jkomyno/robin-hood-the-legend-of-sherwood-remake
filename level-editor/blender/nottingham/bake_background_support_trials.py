"""Bake explicitly diagnosed background-spill trials, releasing the lease per asset."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent))
from texture_experiment_paths import selected_experiment
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from render_slots import acquire,release
from bake_ready_textures import claim
import bpy
from bake_reviewed_asset import stage
from render_texture_coverage import inspect
for asset in sys.argv[sys.argv.index('--')+1:]:
 p=selected_experiment(asset)
 scoped=p/'repair-background-support';g=p/'generation-short-no-mask-with-lighting-openrouter'
 diagnosis=json.loads((scoped/'diagnosis.json').read_text());g=Path(diagnosis.get('generation_directory',g));m=json.loads((scoped/'views.json').read_text())
 if diagnosis['asset_id']!=asset or m.get('texture_generated_background_max_rgb')!=.015:raise ValueError('Missing scoped diagnosis/policy')
 claim_handle=claim(p)
 if claim_handle is None:raise RuntimeError('Another texture bake owns '+asset)
 index=1
 while (p/f'bake-background-support-{index:03d}').exists():index+=1
 output=p/f'bake-background-support-{index:03d}'
 acquire()
 try:
  if output.exists():raise RuntimeError('Output appeared while waiting for render lease: '+str(output))
  bpy.ops.wm.open_mainfile(filepath=str(scoped/'approved-model.blend'))
  result=stage(scoped/'views.json',g/'generated-preserved.png',output,texels_per_unit=2,reconciliation_reference=g/'generated-raw.png')
  inspect(scoped/'views.json',output,output/'coverage')
  print('BACKGROUND SUPPORT BAKED '+asset+' '+str(output),flush=True)
 finally:
  release()
  claim_handle.close()
  time.sleep(1.1)  # Give already queued one-second pollers a chance before reacquiring.
