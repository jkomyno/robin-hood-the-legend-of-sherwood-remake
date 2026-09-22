"""Create a fresh immutable castle packet with 30-percent camera margin."""
from pathlib import Path
import sys,json
root=Path.cwd();r=root/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(root/'level-editor/blender/nottingham'))
from render_slots import acquire
acquire()
from freeze_tooling import select_tooling
select_tooling()
import refinement_review
fit=refinement_review.fit_camera
def margin(*args,**kw):
 kw['padding']=1.3
 return fit(*args,**kw)
refinement_review.fit_camera=margin
from prepare_assets import main
asset=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'nottingham-castle-southeast-spire'
main(['--source-blend',str(r/'grouped/nottingham-grouped-v5.blend'),'--output',str(r/'round-4/assets'),'--source-path',str(r/'source-states/covered.png'),'--grouping-manifest',str(r/'grouping/catalog-v5.json'),'--inventory-path',str(r/'inventory/inventory-v2.json'),'--review-path',str(r/'grouping/grouping-review-v5.json'),'--projection-manifest',str(r/'state-review/baseline-final-layers.json'),'--source-mask-manifest',str(r/'mask-review/source-masks-v11-baseline.json'),'--width','256','--height','320','--prepare-only',asset])
from refine_castle import refine
from refinement_workspace import modified
import bpy
out=r/'round-4/assets'/asset
if asset=='nottingham-castle-entry-steps':
 from refine_castle_secondary import apply
 apply(out)
 raise SystemExit(0)
report=refine(asset)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
(out/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
from refine_castle_packets import apply_masks
apply_masks(out,r/'mask-review/castle-overrides-v11.json')
modified(out)
