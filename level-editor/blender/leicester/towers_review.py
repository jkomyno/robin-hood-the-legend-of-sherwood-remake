"""Render a tower packet, paired display states, and their stored materials."""
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve()
sys.path.insert(0,str(HERE.parents[1]))
sys.path.insert(0,str(HERE.parents[2]/'refinement/blender'))
from refinement_workspace import modified
from asset_reference_views import render_states
from audit_stored_materials import run as audit


def run(workspace):
    version=1
    while (workspace/f'inspection/states-v{version}').exists():version+=1
    modified(workspace)
    states=render_states(workspace,workspace/f'inspection/states-v{version}')
    reports=[]
    for state in states['states']:
        target=workspace/f'inspection/stored-material-{state["patch_id"]}-{state["state"]}-v{version}'
        report=audit(workspace,target,render=True,export=True,
                     render_object_names=state['object_names'],frame_manifest=workspace/'input/views.json')
        reports.append(dict(path=str(target),status=report['status'],problems=report['problems']))
    print(json.dumps(dict(workspace=str(workspace),state_version=version,material_audits=reports),indent=2))


if __name__=='__main__':run(Path(sys.argv[sys.argv.index('--')+1]).resolve())
