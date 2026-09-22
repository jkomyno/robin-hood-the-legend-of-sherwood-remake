"""Run one authorized props render slot sequentially; leave visual review pending."""
import argparse
import importlib
import json
from pathlib import Path
import shutil
import sys

import bpy


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dispatch',type=Path)
    parser.add_argument('assets',nargs='+')
    parser.add_argument('--recipe',choices=['props','props_shells','props_fences','props_carpentry','props_timber','props_special','props_trees','props_gate'],default='props')
    parser.add_argument('--width',type=int,default=256)
    parser.add_argument('--height',type=int,default=320)
    parser.add_argument('--framing-padding',type=float)
    parser.add_argument('--context-padding',type=int)
    parser.add_argument('--assignments-from',type=Path)
    parser.add_argument('--prepare-mask-manifest',type=Path)
    parser.add_argument('--workspace-root',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    script_dir=Path(__file__).resolve().parent
    sys.path.insert(0,str(script_dir.parent));sys.path.insert(0,str(script_dir))
    import refinement_workspace
    recipe=importlib.import_module(args.recipe)
    dispatch=json.loads(args.dispatch.read_text())
    jobs={j['asset_id']:j for j in dispatch['jobs']}
    for asset in args.assets:
        job=jobs[asset];workspace=(args.workspace_root/asset).resolve() if args.workspace_root else Path(job['workspace'])
        if not workspace.exists():
            bpy.ops.wm.open_mainfile(filepath=dispatch['source_blend'],load_ui=False)
            argv=job['prepare_argv'];argv=argv[argv.index('--')+1:]
            argv[1]=str(workspace)
            # Freestanding props have no revealed interior receivers. Their
            # native exterior masks remain authoritative without map layers.
            if '--projection-manifest' in argv:
                index=argv.index('--projection-manifest');argv=argv[:index]+argv[index+2:]
            if args.prepare_mask_manifest:
                index=argv.index('--source-mask-manifest');argv[index+1]=str(args.prepare_mask_manifest.resolve())
            framing=[]
            if args.framing_padding is not None:framing+=['--framing-padding',str(args.framing_padding)]
            if args.context_padding is not None:framing+=['--context-padding',str(args.context_padding)]
            refinement_workspace.main(argv+['--width',str(args.width),'--height',str(args.height)]+framing)
        elif not (workspace/'model.blend').exists():
            raise RuntimeError(f'Incomplete workspace requires inspection before resuming: {workspace}')
        bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'),load_ui=False)
        if args.assignments_from:
            config=json.loads((workspace/'workspace.json').read_text())
            mask_path=Path(config['source_mask_manifest'])
            local=json.loads(mask_path.read_text());incoming=json.loads(args.assignments_from.read_text())
            inventory=(mask_path.parent/local['mask_inventory']).resolve()
            indices={r['index'] for r in json.loads(inventory.read_text())['masks']}
            for label,projection in local['projections'].items():
                owned=[a for a in incoming['projections'][label]['assignments']
                       if a.get('source_node') in config['part_ids'] or a.get('asset_group')==asset]
                for assignment in owned:
                    if any(i not in indices for i in assignment['mask_indices']+assignment.get('exclude_mask_indices',[])):
                        raise ValueError('New mask bitmap requires a separately frozen workspace revision')
                keys={(a.get('source_node'),a.get('asset_group'),a.get('projection_component')) for a in owned}
                projection['assignments']=[a for a in projection['assignments']
                    if (a.get('source_node'),a.get('asset_group'),a.get('projection_component')) not in keys]+owned
            mask_path.write_text(json.dumps(local,indent=2)+'\n')
            refinement_workspace.validate(workspace)
        report=recipe.run(workspace)
        refinement_workspace.modified(workspace)
        shutil.copy2(script_dir/(args.recipe+'.py'),workspace/(args.recipe+'.py'))
        if args.recipe=='props_shells':
            shutil.copy2(script_dir/'props_timber.py',workspace/'props_timber.py')
        latest=max((workspace/'projection').glob('*/ownership.json'),key=lambda p:p.stat().st_mtime_ns)
        shutil.copy2(latest,workspace/'inspection'/'ownership.json')
        review=['# '+asset,'','Status: visual review pending.','',
                'The recipe was applied twice with matching geometry hashes. Projection and all fixed cameras were regenerated.','',
                '## Limitations','']+['- '+s for s in report['limitations']]+['',
                'Geometry approval: pending. Texture generation: not started.','']
        (workspace/'review.md').write_text('\n'.join(review))
        handoff={'status':'validation-pending','notes':report['limitations']+['All eight solid/source-textured views await visual inspection.'],
                 'recipe':args.recipe+'.py','ownership':'inspection/ownership.json',
                 'all_eight_views_inspected':False,'has_revealed_state':False,
                 'geometry_approval':'pending','texture_generation':'not-started'}
        (workspace/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n')
        print('PROPS_PACKET_COMPLETE '+asset,flush=True)


if __name__=='__main__':main()
