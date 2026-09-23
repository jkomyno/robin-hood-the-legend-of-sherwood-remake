"""Serial reproducible preparation/refinement for the three remaining towers.

Run only with a coordinator-assigned heavy rendering slot. The frozen grouped
checkpoint is reopened for every isolated worker; packets are never shared.
"""
import json,sys
from pathlib import Path
import bpy
HERE=Path(__file__).resolve();ROOT=HERE.parents[3];BLENDER=HERE.parents[1]
sys.path.insert(0,str(BLENDER));sys.path.insert(0,str(HERE.parent))
from refinement_workspace import prepare,modified
from asset_reference_views import render_states
from towers import refine
WORK=ROOT/'level-editor/work/leicester-refinement';ROUND=WORK/'round-1'
JOBS=['leicester-east-moat-tower','leicester-church-side-tower','leicester-west-moat-tower']
MASKS={JOBS[0]:([168,190]+list(range(169,179)),270),JOBS[1]:([199,220]+list(range(200,210)),280),JOBS[2]:([258,276]+list(range(259,269)),357)}

def run(asset):
 workspace=ROUND/'assets-v2'/asset
 if (workspace/'workspace.json').exists():raise RuntimeError('Worker already frozen; use an explicit continuation instead: '+str(workspace))
 jobs=json.loads((ROUND/'dispatch-v3/dispatch.json').read_text())['jobs']
 argv=next(job for job in jobs if job['asset_id']==asset)['prepare_argv'];opts=argv[argv.index('--asset-id'):]
 kwargs={opts[i][2:].replace('-','_'):opts[i+1] for i in range(0,len(opts),2)}
 kwargs['source_mask_manifest']=str(WORK/'mask-audit/source-masks-v3.json')
 bpy.ops.wm.open_mainfile(filepath=argv[2],load_ui=False)
 bpy.context.window.scene=bpy.data.scenes[kwargs['scene_name']]
 bpy.context.scene.render.threads_mode='FIXED';bpy.context.scene.render.threads=2
 prepare(workspace,**kwargs)
 config=json.loads((workspace/'workspace.json').read_text());path=Path(config['source_mask_manifest']);m=json.loads(path.read_text());nodes,index=MASKS[asset]
 m['projections']['exterior']['assignments'] += [{'source_node':f'building-{n:03}','mask_indices':[index],'reviewed':True,'evidence':f'Native old-state mask{index} identifies this tower upper body/cone; paired covered/revealed source and native mask contact atlas reviewed. No adjacent bridge or lower-floor union is accepted.'} for n in nodes]
 path.write_text(json.dumps(m,indent=2)+'\n');refine(workspace);modified(workspace);render_states(workspace,workspace/'inspection/states-v1')
 print('TOWER_PACKET_COMPLETE',asset,flush=True)
if __name__=='__main__':
 requested=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else JOBS
 for asset in requested:
  if asset not in JOBS:raise ValueError(asset)
  run(asset)
