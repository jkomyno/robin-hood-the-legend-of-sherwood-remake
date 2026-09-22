"""Prepare one bridge workspace using the reviewed dispatch with room for rails."""
import argparse
import json
from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from refinement_workspace import prepare
p=argparse.ArgumentParser();p.add_argument('asset');p.add_argument('--framing-padding',type=float,default=1.5);p.add_argument('--dispatch',type=Path,default=Path('level-editor/work/leicester-refinement/round-1/assets-v2/dispatch.json'));a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
job=next(j for j in json.loads(a.dispatch.read_text())['jobs'] if j['asset_id']==a.asset)
argv=job['prepare_argv'];options=argv[argv.index('--asset-id'):];kw={options[i][2:].replace('-','_'):options[i+1] for i in range(0,len(options),2)}
bpy.ops.wm.open_mainfile(filepath=argv[2]);bpy.context.scene.render.threads_mode='FIXED';bpy.context.scene.render.threads=2
prepare(job['workspace'],**kw,framing_padding=a.framing_padding)
