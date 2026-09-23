"""Build the covered bridge's isolated geometry and paired source packets."""
import json
from pathlib import Path
import shutil
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import covered_bridge
from refinement_workspace import main as workspace_main,modified
from asset_reference_views import render_states
root=Path(sys.argv[sys.argv.index('--')+1]).resolve();workspace=root/'round-1/assets-v2'/covered_bridge.ASSET
masks=root/'mask-audit/covered-bridge-v1/source-masks.json'
if not masks.exists():covered_bridge.prepare_masks(root/'mask-audit/source-masks-v3.json',root/'layers/revealed.png',masks)
if not workspace.exists():
    dispatch=json.loads((root/'round-1/dispatch-v3/dispatch.json').read_text());job=next(j for j in dispatch['jobs'] if j['asset_id']==covered_bridge.ASSET)
    bpy.ops.wm.open_mainfile(filepath=dispatch['source_blend'],load_ui=False)
    argv=job['prepare_argv'];argv=argv[argv.index('--')+1:];argv[1]=str(workspace);argv[argv.index('--source-mask-manifest')+1]=str(masks)
    workspace_main(argv+['--width','384','--height','512','--framing-padding','1.25'])
bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'),load_ui=False)
report=covered_bridge.run(workspace);modified(workspace);states=render_states(workspace,workspace/'inspection/states')
shutil.copy2(Path(__file__).with_name('covered_bridge.py'),workspace/'recipe.py')
(workspace/'handoff.json').write_text(json.dumps({'status':'validation-pending','notes':report['limitations'],'recipe':'recipe.py','ownership':str(max((workspace/'projection').glob('*/layers-report.json'),key=lambda p:p.stat().st_mtime_ns).relative_to(workspace)),'all_eight_views_inspected':False,'has_revealed_state':True,'geometry_approval':'pending','texture_generation':'not-started','revealed_solid':'inspection/states/patch-003/revealed/solid.png','revealed_textured':'inspection/states/patch-003/revealed/textured.png','revealed_context':'inspection/states/patch-003/revealed/context.png'},indent=2)+'\n')
print('COVERED_BRIDGE_PACKETS_COMPLETE')
