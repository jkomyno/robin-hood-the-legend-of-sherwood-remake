"""Refresh rejected tree candidates without erasing their exact user feedback."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import bpy


@bpy.app.handlers.persistent
def _cutout_ray_depth(scene):
    scene.cycles.transparent_max_bounces=128


def run(workspace):
    workspace=Path(workspace).resolve()
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from refinement_workspace import modified
    from audit_stored_materials import run as audit
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'),load_ui=False)
    feedback=json.loads((workspace/'user-feedback.json').read_text())
    volume_report=workspace/'inspection/continuous-volume/report.json'
    report=json.loads((volume_report if volume_report.exists() else workspace/'inspection/foliage-recipe.json').read_text())
    if not report['recipe'].startswith(('leicester-foliage-lobes-','leicester-neutral-regional-fringe-','leicester-continuous-forest-volume-')):
        raise ValueError('Apply current foliage recipe before building the packet')
    modified(workspace)
    latest=max((workspace/'projection').glob('*/ownership.json'),key=lambda p:p.stat().st_mtime_ns)
    shutil.copy2(latest,workspace/'inspection/ownership.json')
    shutil.copy2(Path(__file__).with_name('foliage_trees.py'),workspace/'foliage_trees.py')
    recipe='foliage_trees.py'
    if report['recipe'].startswith('leicester-neutral-regional-fringe-'):
        recipe='forest_fringe.py'
        shutil.copy2(Path(__file__).with_name(recipe),workspace/recipe)
    if report['recipe'].startswith('leicester-continuous-forest-volume-'):
        recipe='forest_volume.py'
        shutil.copy2(Path(__file__).with_name(recipe),workspace/recipe)
    audit_output=workspace/'inspection/stored-materials'
    if audit_output.exists():
        identity=hashlib.sha256((audit_output/'audit.json').read_bytes()).hexdigest()[:16]
        archive=workspace/'history'/('stored-materials-'+identity)
        if archive.exists():
            raise FileExistsError('Audit revision already archived: '+str(archive))
        audit_output.rename(archive)
    bpy.app.handlers.render_pre.append(_cutout_ray_depth)
    try:
        material_report=audit(workspace,audit_output,render=True,export=True)
    finally:
        bpy.app.handlers.render_pre.remove(_cutout_ray_depth)
    material_report['render']['transparent_max_bounces']=128
    material_report['render']['transparent_depth_reason']='Physical foliage coverage must survive transparent front and rear surface traversals.'
    (audit_output/'audit.json').write_text(json.dumps(material_report,indent=2)+'\n')
    handoff=json.loads((workspace/'handoff.json').read_text())
    handoff.update(status='fix-needed',recipe=recipe,all_eight_views_inspected=False,
                   geometry_approval='not-approved',texture_generation='not-started',
                   notes=report['limitations']+['New physical foliage cutout candidate awaits all-eight-view review.'],
                   exact_user_feedback=feedback,
                   current_revision_blockers=['Refreshed eight-view packet requires independent visual inspection and user geometry review.'])
    (workspace/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n')
    if json.loads((workspace/'user-feedback.json').read_text())!=feedback:
        raise ValueError('Feedback changed')
    print('FOLIAGE_PACKET_COMPLETE',workspace.name,material_report['status'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('workspaces',nargs='+',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    for workspace in args.workspaces:run(workspace)
