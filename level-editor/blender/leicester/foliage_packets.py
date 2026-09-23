"""Refresh rejected tree candidates without erasing their exact user feedback."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import bpy


def run(workspace):
    workspace=Path(workspace).resolve()
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from refinement_workspace import modified
    from audit_stored_materials import run as audit
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'),load_ui=False)
    feedback=json.loads((workspace/'user-feedback.json').read_text())
    report=json.loads((workspace/'inspection/foliage-recipe.json').read_text())
    if not report['recipe'].startswith('leicester-foliage-lobes-'):
        raise ValueError('Apply current foliage recipe before building the packet')
    modified(workspace)
    latest=max((workspace/'projection').glob('*/ownership.json'),key=lambda p:p.stat().st_mtime_ns)
    shutil.copy2(latest,workspace/'inspection/ownership.json')
    shutil.copy2(Path(__file__).with_name('foliage_trees.py'),workspace/'foliage_trees.py')
    audit_output=workspace/'inspection/stored-materials'
    if audit_output.exists():
        identity=hashlib.sha256((audit_output/'audit.json').read_bytes()).hexdigest()[:16]
        archive=workspace/'history'/('stored-materials-'+identity)
        if archive.exists():
            raise FileExistsError('Audit revision already archived: '+str(archive))
        audit_output.rename(archive)
    material_report=audit(workspace,audit_output,render=True,export=True)
    handoff=json.loads((workspace/'handoff.json').read_text())
    handoff.update(status='fix-needed',recipe='foliage_trees.py',all_eight_views_inspected=False,
                   geometry_approval='not-approved',texture_generation='not-started',
                   notes=report['limitations']+['New physical foliage cutout candidate awaits all-eight-view review.'],
                   exact_user_feedback=feedback)
    (workspace/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n')
    if json.loads((workspace/'user-feedback.json').read_text())!=feedback:
        raise ValueError('Feedback changed')
    print('FOLIAGE_PACKET_COMPLETE',workspace.name,material_report['status'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspaces',nargs='+',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    for workspace in args.workspaces:run(workspace)
