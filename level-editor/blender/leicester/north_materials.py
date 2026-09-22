"""Audit actual saved atlases for both complete keep visibility states."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit_stored_materials import run

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);p.add_argument('states',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    for state in ('covered','revealed'):
        frame=a.states/'combined'/state/'views.json';names=json.loads(frame.read_text())['render_object_names']
        report=run(a.workspace,a.output/state,render=True,export=True,render_object_names=names,frame_manifest=frame)
        if report['status']!='STRUCTURAL-PASS':raise RuntimeError(report['problems'])
        print(state,report['status'],flush=True)
