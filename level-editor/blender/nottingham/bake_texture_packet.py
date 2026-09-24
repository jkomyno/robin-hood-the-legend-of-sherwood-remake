"""Bake one approved Nottingham texture packet with a shared Blender render lease.

Generation and publication remain separate operations. This wrapper delegates
all geometry, source-protection, and outside-material guards to the shared baker.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('experiment',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--generated',type=Path)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--reconciliation-reference',type=Path)
    parser.add_argument('--render-coverage',action='store_true',help='Render exact provenance under the same lease after baking')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    experiment=args.experiment.resolve();output=args.output.resolve()
    generated=(args.generated or experiment/'generation-short-no-mask-with-lighting-openrouter/generated-preserved.png').resolve()
    for p in [experiment/'approved-model.blend',experiment/'views.json',experiment/'approval.json',generated]:
        if not p.is_file():raise FileNotFoundError(p)
    manifest=(args.manifest or experiment/'views.json').resolve()
    if manifest.parent != experiment:
        raise ValueError('Candidate manifest must retain its approved experiment directory')
    if output.exists():raise FileExistsError(output)
    acquire()
    sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
    import bpy
    from bake_reviewed_asset import stage
    bpy.ops.wm.open_mainfile(filepath=str(experiment/'approved-model.blend'))
    report=stage(manifest,generated,output,texels_per_unit=2,reconciliation_reference=args.reconciliation_reference)
    if args.render_coverage:
        from render_texture_coverage import inspect
        inspect(manifest,output,output/'coverage')
    print(json.dumps(dict(asset=report['asset_id'],output=str(output),counts=report['counts'],geometry_verified=report['geometry_verified'],outside_objects_unchanged=report['outside_objects_unchanged'])),flush=True)

if __name__=='__main__':main()
