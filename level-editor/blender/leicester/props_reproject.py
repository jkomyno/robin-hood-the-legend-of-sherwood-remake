"""Refresh existing props after owned mask review without changing geometry."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from refinement_workspace import modified

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspaces',nargs='+',type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    for workspace in args.workspaces:
        workspace=workspace.resolve()
        bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'),load_ui=False)
        modified(workspace)
        latest=max((workspace/'projection').glob('*/ownership.json'),key=lambda p:p.stat().st_mtime_ns)
        shutil.copy2(latest,workspace/'inspection'/'ownership.json')
        handoff=json.loads((workspace/'handoff.json').read_text())
        handoff.update(status='validation-pending',all_eight_views_inspected=False)
        (workspace/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n')
        print('PROPS_PROJECTION_COMPLETE '+workspace.name,flush=True)
