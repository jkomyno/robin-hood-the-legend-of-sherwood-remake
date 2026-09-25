"""Refresh held support diagnostics with tight camera depth; never save models."""
import json,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path[:0]=[str(HERE),str(HERE.parents[1]/'refinement/blender')]
import bpy
from PIL import Image
from triage_support_backlog import OUT,sha
from render_slots import acquire,release
from render_multiview_asset import render
from render_texture_coverage import inspect
from trace_texture_coverage_pixels import run as trace
rows=json.loads((OUT/'inventory.json').read_text())
for row in rows:
 if row.get('depth_corrected'):continue
 bake=Path(row['bake']);manifest=Path(row['manifest']);output=OUT/row['asset_id'];output.mkdir(exist_ok=True)
 acquire()
 try:
  assert sha(bake/'worker.blend')==row['model_sha256'];assert sha(manifest)==row['manifest_sha256']
  bpy.ops.wm.open_mainfile(filepath=str(bake/'worker.blend'));data=json.loads(manifest.read_text());w,h=data['tile_size'];actual=output/'actual-depth'
  if actual.exists():raise ValueError('Use fresh output; prior diagnostics already exist')
  render(manifest,actual,width=w);sheet=Image.new('RGBA',(w*4,h*2))
  for i in range(8):
   with Image.open(actual/f'view-{i}-textured.png')as im:sheet.paste(im,(i%4*w,i//4*h))
  sheet.save(actual/'textured.png');coverage=output/'coverage-depth';inspect(manifest,bake,coverage)
  report=dict(status='DIAGNOSTIC-READY',asset_id=row['asset_id'],model_sha256=row['model_sha256'],manifest_sha256=row['manifest_sha256'],coverage=str(coverage/'coverage.json'),coverage_sha256=sha(coverage/'coverage.json'),actual=str(actual/'textured.png'),actual_sha256=sha(actual/'textured.png'),actual_views={str(i):sha(actual/f'view-{i}-textured.png')for i in range(8)},bake=str(bake),manifest=str(manifest))
  assert sha(bake/'worker.blend')==row['model_sha256'];(output/'depth-review.json').write_text(json.dumps(report,indent=2)+'\n')
 finally:release()
 # Read-only ray diagnostics do not occupy a render lease.
 trace(coverage,subrays=True);time.sleep(1.1)
