"""Render the primary stored-material audits required by the shared collector."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
from audit_stored_materials import run
base=Path(__file__).resolve().parents[2]/'work/leicester-refinement/round-1/assets-v2'
for name in ['northwest','east-moat','church-side','west-moat']:
 workspace=base/f'leicester-{name}-tower'
 result=run(workspace,workspace/'inspection/stored-materials',render=True,export=True)
 assert result['status']=='STRUCTURAL-PASS',result['problems']
