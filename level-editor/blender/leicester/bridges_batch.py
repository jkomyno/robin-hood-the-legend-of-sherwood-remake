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
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');parser.add_argument('assets',nargs='*')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    selected=args.assets
    static=['leicester-south-footbridge','leicester-east-village-footbridge','leicester-west-tower-footbridge']
    dynamic=['leicester-east-village-drawbridge','leicester-east-moat-drawbridge','leicester-south-drawbridge']
    for asset in static+dynamic:
        if selected and asset not in selected:continue
        for state in (['initial'] if asset in static else ['initial','applied']):
            base='assets-v2' if state=='initial' else 'bridge-applied'
            workspace=ROOT/'round-1'/base/asset
            recipe_path=DIRECTORY/('bridges.py' if asset in static else 'bridges_states.py')
            import hashlib
            recipe_report=workspace/'inspection'/('bridge-recipe.json' if asset in static else 'bridge-state.json')
            current_recipe=recipe_report.exists() and json.loads(recipe_report.read_text()).get('recipe_sha256')==hashlib.sha256(recipe_path.read_bytes()).hexdigest()
            dependencies=json.loads(recipe_report.read_text()).get('recipe_dependencies',{}) if recipe_report.exists() else {}
            current_recipe=current_recipe and all((DIRECTORY/name).exists() and hashlib.sha256((DIRECTORY/name).read_bytes()).hexdigest()==digest for name,digest in dependencies.items())
            current_projection=recipe_report.exists() and json.loads(recipe_report.read_text()).get('projection_status')=='CURRENT'
            if current_recipe and current_projection and (workspace/'modified/views.json').exists() and (workspace/'validation.json').exists():
                print('ALREADY RENDERED',asset,state,flush=True);continue
            print('BRIDGE PACKET',asset,state,flush=True)
            if not (workspace/'workspace.json').exists():
                if workspace.exists():raise RuntimeError(f'Incomplete preparation requires explicit recovery: {workspace}')
                run('bridges_prepare.py',[asset]) if asset in static else run('bridges_states.py',['prepare',asset,state])
            bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
            bpy.context.scene.render.threads_mode='FIXED';bpy.context.scene.render.threads=2
            if asset in static:run('bridges.py',[workspace]+([] if args.prepare_only else ['--render']))
            else:run('bridges_states.py',['refine',asset,state]+(['--geometry-only'] if args.prepare_only else []))
            import shutil
            shutil.copy2(recipe_path,workspace/'inspection'/('recipe-executed.py' if asset in static else 'state-recipe-executed.py'))
            for name in json.loads(recipe_report.read_text()).get('recipe_dependencies',{}):
                shutil.copy2(DIRECTORY/name,workspace/'inspection'/name)
            print('BRIDGE PACKET COMPLETE',asset,state,flush=True)
if __name__=='__main__':main()
