"""Audit saved covered-bridge materials in the base and both display states."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit_stored_materials import run
w=Path(sys.argv[sys.argv.index('--')+1]).resolve()
run(w,w/'inspection/stored-materials',render=True,export=True)
for state in ['covered','revealed']:
    frame=w/f'inspection/states/patch-003/{state}/views.json'
    names=json.loads(frame.read_text())['render_object_names']
    run(w,w/f'inspection/stored-material-states/{state}',render=True,export=True,render_object_names=names,frame_manifest=frame)
print('COVERED_BRIDGE_MATERIAL_AUDITS_COMPLETE')
