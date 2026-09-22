"""Resume sequential bridge packets within one two-thread Blender worker slot."""
import json
from pathlib import Path
import runpy
import sys
import bpy
DIRECTORY=Path(__file__).resolve().parent
ROOT=DIRECTORY.parents[1]/'work/leicester-refinement'

def run(script,args):
    previous=sys.argv[:]
    try:
        sys.argv=[str(DIRECTORY/script),'--']+list(map(str,args))
        runpy.run_path(str(DIRECTORY/script),run_name='__main__')
    finally:sys.argv=previous

def main():
    selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    static=['leicester-west-tower-footbridge']
    dynamic=['leicester-east-village-drawbridge','leicester-east-moat-drawbridge','leicester-south-drawbridge']
    for asset in static+dynamic:
        if selected and asset not in selected:continue
        for state in (['initial'] if asset in static else ['initial','applied']):
            base='assets-v2' if state=='initial' else 'bridge-applied'
            workspace=ROOT/'round-1'/base/asset
            if (workspace/'modified/views.json').exists() and (workspace/'validation.json').exists():
                print('ALREADY RENDERED',asset,state,flush=True);continue
            print('BRIDGE PACKET',asset,state,flush=True)
            if not (workspace/'workspace.json').exists():
                if workspace.exists():raise RuntimeError(f'Incomplete preparation requires explicit recovery: {workspace}')
                run('bridges_prepare.py',[asset]) if asset in static else run('bridges_states.py',['prepare',asset,state])
            bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
            bpy.context.scene.render.threads_mode='FIXED';bpy.context.scene.render.threads=2
            if asset in static:run('bridges.py',[workspace,'--render'])
            else:run('bridges_states.py',['refine',asset,state])
            print('BRIDGE PACKET COMPLETE',asset,state,flush=True)
if __name__=='__main__':main()
