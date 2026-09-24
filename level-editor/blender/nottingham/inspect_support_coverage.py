"""Render provenance for completed support bakes using the shared FIFO leases."""
import sys,json,time,argparse
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'refinement/blender'))
from texture_experiment_paths import selected_experiment
from render_slots import acquire,release
from render_texture_coverage import inspect,sha
parser=argparse.ArgumentParser();parser.add_argument('--bake',default='bake-background-support-001');parser.add_argument('--scope',default='repair-background-support');parser.add_argument('--output',default='coverage');parser.add_argument('--actual-output');parser.add_argument('assets',nargs='+');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
if any(Path(n).name!=n for n in [args.bake,args.scope,args.output]+([args.actual_output] if args.actual_output else [])):raise ValueError('Local output directory names required')
for asset in args.assets:
 p=selected_experiment(asset);b=p/args.bake;out=b/args.output;manifest=p/args.scope/'views.json'
 if out.exists():
  if not (out/'coverage.json').exists() or json.loads((out/'coverage.json').read_text())['model_sha256']!=sha(b/'worker.blend'):raise ValueError('Incomplete or stale coverage '+asset)
  continue
 acquire()
 try:
  if args.actual_output:
   import bpy
   from PIL import Image
   from render_multiview_asset import render
   actual=b/args.actual_output
   if actual.exists():raise ValueError('Fresh supplemental actual directory required')
   actual.mkdir();m=json.loads(manifest.read_text());bpy.ops.wm.open_mainfile(filepath=str(b/'worker.blend'))
   render(manifest,actual,width=m['tile_size'][0]);w,h=m['tile_size'];sheet=Image.new('RGBA',(w*4,h*2))
   for index in range(8):
    with Image.open(actual/f'view-{index}-textured.png') as im:sheet.paste(im,((index%4)*w,(index//4)*h))
   sheet.save(actual/'textured.png')
   (actual/'evidence.json').write_text(json.dumps(dict(model_sha256=sha(b/'worker.blend'),manifest_sha256=sha(manifest),sheet_sha256=sha(actual/'textured.png'),purpose='Corrected camera depth; same source, geometry, lighting and saved materials.'),indent=2)+'\n')
  result=inspect(manifest,b,out)
  print(asset,[v['unfilled_visible_pixels'] for v in result['views']],flush=True)
 finally:
  release();time.sleep(1.1)
