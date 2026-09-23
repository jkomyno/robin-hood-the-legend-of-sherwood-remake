"""Validate saved bridge materials sequentially in one two-thread worker."""
import hashlib,json
from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
from audit_stored_materials import run
ROOT=Path('level-editor/work/leicester-refinement/round-1').resolve()
def main():
 assets=['leicester-west-tower-footbridge','leicester-east-moat-drawbridge','leicester-east-village-drawbridge','leicester-south-drawbridge']
 selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
 for asset in assets:
  if selected and asset not in selected:continue
  for base in (['assets-v2'] if asset.endswith('footbridge') else ['assets-v2','bridge-applied']):
   workspace=ROOT/base/asset;output=workspace/'inspection/stored-materials'
   if output.exists():
    report=json.loads((output/'audit.json').read_text())
    if report['model_sha256']==hashlib.sha256((workspace/'model.blend').read_bytes()).hexdigest() and not report['problems']:continue
    raise ValueError('Preserve stale/failed material audit before retry: '+str(output))
   bpy.context.scene.render.threads_mode='FIXED';bpy.context.scene.render.threads=2
   run(workspace,output,render=True,export=True)
   print('BRIDGE MATERIAL AUDIT COMPLETE',asset,base,flush=True)
if __name__=='__main__':main()
