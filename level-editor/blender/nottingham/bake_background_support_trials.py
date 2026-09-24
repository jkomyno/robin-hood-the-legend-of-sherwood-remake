"""Bake explicitly diagnosed background-spill trials, releasing the lease per asset."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent))
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from render_slots import acquire,release
import bpy
from bake_reviewed_asset import stage
for asset in sys.argv[sys.argv.index('--')+1:]:
 p=ROOT/'level-editor/work/nottingham-refinement/texture-generation/experiments'/asset
 scoped=p/'repair-background-support';g=p/'generation-short-no-mask-with-lighting-openrouter'
 diagnosis=json.loads((scoped/'diagnosis.json').read_text());m=json.loads((scoped/'views.json').read_text())
 if diagnosis['asset_id']!=asset or m.get('texture_generated_background_max_rgb')!=.015:raise ValueError('Missing scoped diagnosis/policy')
 index=1
 while (p/f'bake-background-support-{index:03d}').exists():index+=1
 output=p/f'bake-background-support-{index:03d}'
 acquire()
 try:
  bpy.ops.wm.open_mainfile(filepath=str(scoped/'approved-model.blend'))
  result=stage(scoped/'views.json',g/'generated-preserved.png',output,texels_per_unit=2,reconciliation_reference=g/'generated-raw.png')
  print('BACKGROUND SUPPORT BAKED '+asset+' '+str(output),flush=True)
 finally:release()
