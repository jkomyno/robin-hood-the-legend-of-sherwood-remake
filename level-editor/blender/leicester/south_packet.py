"""Prepare or refine one southern worker packet after its input is inspected."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy

DIRECTORY = Path(__file__).resolve().parent
ROOT = DIRECTORY.parents[1] / 'work/leicester-refinement'
sys.path.insert(0, str(DIRECTORY.parent))
sys.path.insert(0, str(DIRECTORY))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'refine'])
    parser.add_argument('asset')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    dispatch = json.loads((ROOT / 'round-1/assets-v2/dispatch.json').read_text())
    job = next(j for j in dispatch['jobs'] if j['asset_id'] == args.asset)
    workspace = Path(job['workspace'])
    from refinement_workspace import prepare, modified
    if args.action == 'prepare':
        if workspace.exists():
            raise FileExistsError('Preserve existing worker packet: ' + str(workspace))
        argv = job['prepare_argv']
        options = argv[argv.index('--asset-id'):]
        kw = {options[i][2:].replace('-', '_'): options[i+1] for i in range(0,len(options),2)}
        kw['source_mask_manifest'] = str(ROOT / 'south-inspection/source-masks.json')
        bpy.ops.wm.open_mainfile(filepath=argv[2], load_ui=False)
        bpy.context.scene.render.threads_mode='FIXED';bpy.context.scene.render.threads=2
        prepare(workspace, **kw)
        return
    if not (workspace / 'input/views.json').is_file():
        raise RuntimeError('Complete immutable input is required')
    review = workspace / 'inspection/input-review.json'
    if not review.is_file() or not json.loads(review.read_text()).get('all_eight_views_inspected'):
        raise RuntimeError('Inspect and record every frozen input view before refining')
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'), load_ui=False)
    import south_structures
    report = south_structures.refine(args.asset)
    report['recipe_sha256'] = hashlib.sha256(Path(south_structures.__file__).read_bytes()).hexdigest()
    report_path = workspace / 'geometry-report.json'
    if report.get('reused') and report_path.exists():
        previous = json.loads(report_path.read_text())
        report['changes'] = previous['changes']
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'), load_ui=False)
    modified(workspace)


if __name__ == '__main__':
    main()
