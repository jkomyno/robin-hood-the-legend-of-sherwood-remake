"""Audit saved southern materials, including explicit gatehouse display states."""
import argparse
import json
from pathlib import Path
import sys
import uuid

DIRECTORY=Path(__file__).resolve().parent
sys.path.insert(0,str(DIRECTORY.parent))
from audit_stored_materials import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspaces',nargs='+',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    for workspace in args.workspaces:
        cases=[('stored-materials',workspace/'modified/views.json')]
        patch={'leicester-south-gatehouse':'patch-004','leicester-west-wing':'patch-000'}.get(workspace.name)
        if patch:
            cases += [('stored-materials-'+state,workspace/f'inspection/states/{patch}/{state}/views.json')
                      for state in ('covered','revealed')]
        for name,frame in cases:
            output=workspace/'inspection'/name
            if output.exists():
                history=workspace/'inspection/material-history';history.mkdir(exist_ok=True)
                output.rename(history/(name+'-'+uuid.uuid4().hex[:12]))
            names=json.loads(frame.read_text()).get('render_object_names')
            report=run(workspace,output,render=True,export=True,
                       render_object_names=names,frame_manifest=frame)
            if report['status']!='STRUCTURAL-PASS':
                raise RuntimeError(report['problems'])
        from refinement_workspace import validate
        (workspace/'validation.json').write_text(json.dumps(validate(workspace),indent=2)+'\n')


if __name__=='__main__':main()
