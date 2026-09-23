"""Freeze new bridge source-profile revisions, retaining every prior packet."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from bridges_batch import ROOT,run
ALLOWED={'leicester-west-tower-footbridge','leicester-east-moat-drawbridge','leicester-east-village-drawbridge','leicester-south-drawbridge'}

def main():
 selected=sys.argv[sys.argv.index('--')+1:]
 if not selected or set(selected)-ALLOWED:raise ValueError('Select unapproved bridge geometry explicitly')
 for asset in selected:
  for base in (['assets-v2'] if asset.endswith('footbridge') else ['assets-v2','bridge-applied']):
   workspace=ROOT/'round-1'/base/asset;archive=ROOT/'round-1/bridge-revision-archive/pre-measured-profiles'/base/asset
   if not archive.exists():
    if not (workspace/'workspace.json').is_file():raise ValueError('Expected prior complete packet')
    handoff=json.loads((workspace/'handoff.json').read_text())
    if handoff['status']!='fix-needed':raise ValueError('Only explicitly failed candidates may be revised')
    hashes={str(p.relative_to(workspace)):hashlib.sha256(p.read_bytes()).hexdigest() for p in workspace.rglob('*') if p.is_file()}
    archive.parent.mkdir(parents=True,exist_ok=True);workspace.rename(archive)
    (archive.parent/(asset+'-archive.json')).write_text(json.dumps({'original_path':str(workspace),'archived_path':str(archive),'files_sha256':hashes,
       'reason':'Measured source silhouette and physical support correction; previous immutable input and every review artifact retained.','path_note':'Historical absolute workspace paths resolve by original→archive prefix replacement.'},indent=2)+'\n')
  run('bridges_hardware_batch.py',[asset])
  run('bridges_material_audits.py',[asset])
if __name__=='__main__':main()
