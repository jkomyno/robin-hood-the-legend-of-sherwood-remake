"""Archive unapproved leaf-only packets and prepare wider hardware comparisons."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from bridges_batch import run,DIRECTORY,ROOT

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assets=['leicester-west-tower-footbridge','leicester-east-moat-drawbridge','leicester-east-village-drawbridge','leicester-south-drawbridge']
    selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    for asset in assets:
        if selected and asset not in selected:continue
        static=asset.endswith('footbridge')
        for state in (['initial'] if static else ['initial','applied']):
            base='assets-v2' if state=='initial' else 'bridge-applied'
            workspace=ROOT/'round-1'/base/asset
            archive=ROOT/'round-1/bridge-revision-archive/pre-hardware'/base/asset
            if not archive.exists():
                if not (workspace/'workspace.json').is_file():raise ValueError('Expected existing complete leaf-only packet')
                if (workspace/'handoff.json').is_file() and json.loads((workspace/'handoff.json').read_text()).get('status')=='approved':raise ValueError('Cannot replace approved candidate')
                hashes={str(p.relative_to(workspace)):digest(p) for p in workspace.rglob('*') if p.is_file()}
                archive.parent.mkdir(parents=True,exist_ok=True)
                workspace.rename(archive)
                (archive.parent/(asset+'-archive.json')).write_text(json.dumps({'original_path':str(workspace),'archived_path':str(archive),'files_sha256':hashes,
                    'reason':'Hardware extends beyond frozen leaf-only cameras; create a fresh unapproved workspace with wider fixed input/modified framing.',
                    'path_note':'Archived configuration retains original absolute paths; file bytes are preserved. Resolve original workspace prefix to archived prefix when replaying this historical packet.'},indent=2)+'\n')
            if not (workspace/'workspace.json').exists():
                if static:run('bridges_prepare.py',[asset,'--framing-padding','2.0','--source-masks',ROOT/'bridge-evidence/west-footbridge-ownership/initial-masks.json'])
                else:
                    extra=[]
                    if asset=='leicester-east-village-drawbridge':
                        from bridges_context import prepare_context
                        extra=['--source-blend',prepare_context()]
                    run('bridges_states.py',['prepare',asset,state,'--framing-padding','3.6' if state=='initial' else '4.2']+extra)
            bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
            bpy.context.scene.render.threads_mode='FIXED';bpy.context.scene.render.threads=2
            if static:run('bridges.py',[workspace,'--render'])
            else:run('bridges_states.py',['refine',asset,state])
            report=json.loads((workspace/'inspection'/('bridge-recipe.json' if static else 'bridge-state.json')).read_text())
            recipe=DIRECTORY/('bridges.py' if static else 'bridges_states.py')
            shutil.copy2(recipe,workspace/'inspection'/('recipe-executed.py' if static else 'state-recipe-executed.py'))
            for name in report.get('recipe_dependencies',{}):shutil.copy2(DIRECTORY/name,workspace/'inspection'/name)
            print('WIDER HARDWARE PACKET COMPLETE',asset,state,flush=True)
if __name__=='__main__':main()
