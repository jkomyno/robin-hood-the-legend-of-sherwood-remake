"""Replace the unapproved tight south initial comparison with fresh wider input."""
import hashlib,json,shutil,sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
from bridges_batch import ROOT,DIRECTORY,run
from refinement_workspace import _geometry
from audit_stored_materials import run as audit

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def active_geometry(asset):
 return {o.name:_geometry(o) for o in bpy.data.collections['Leicester Working'].all_objects if o.type=='MESH' and o.get('asset_group')==asset and not o.hide_render}

def main():
 asset='leicester-south-drawbridge';workspace=ROOT/'round-1/assets-v2'/asset;archive=ROOT/'round-1/bridge-revision-archive/tight-south-initial'/asset
 if not archive.exists():
  handoff=json.loads((workspace/'handoff.json').read_text())
  if handoff['status']!='fix-needed':raise ValueError('Only the failed tight-framing packet may be replaced')
  hashes={str(p.relative_to(workspace)):digest(p) for p in workspace.rglob('*') if p.is_file()}
  archive.parent.mkdir(parents=True,exist_ok=True);workspace.rename(archive)
  (archive.parent/'archive.json').write_text(json.dumps({'original_path':str(workspace),'archived_path':str(archive),'files_sha256':hashes,'reason':'Initial view3 beam tip had only0.29pixel top margin. New frozen cameras leave a clear margin; old input remains untouched.'},indent=2)+'\n')
 bpy.ops.wm.open_mainfile(filepath=str(archive/'model.blend'));before=active_geometry(asset)
 if not (workspace/'workspace.json').exists():run('bridges_states.py',['prepare',asset,'initial','--framing-padding','4.0'])
 bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'));run('bridges_states.py',['refine',asset,'initial'])
 after=active_geometry(asset)
 if before!=after:raise ValueError('Framing-only revision unexpectedly changed geometry')
 report=json.loads((workspace/'inspection/bridge-state.json').read_text());shutil.copy2(DIRECTORY/'bridges_states.py',workspace/'inspection/state-recipe-executed.py')
 for name in report['recipe_dependencies']:shutil.copy2(DIRECTORY/name,workspace/'inspection'/name)
 (workspace/'inspection/framing-only.json').write_text(json.dumps({'archived_packet':str(archive),'geometry_unchanged':True,'active_geometry_sha256':hashlib.sha256(json.dumps(after,sort_keys=True).encode()).hexdigest(),'padding':4.0},indent=2)+'\n')
 audit(workspace,workspace/'inspection/stored-materials',render=True,export=True)
if __name__=='__main__':main()
