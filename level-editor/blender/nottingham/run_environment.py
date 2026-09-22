"""Run isolated environment review packets sequentially in one two-thread lane."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
from prepare_assets import preflight_source
import refine_environment


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['source-blend','source-image','source-masks','catalog','inventory','review','output']:
        parser.add_argument('--'+key,required=True,type=Path)
    parser.add_argument('--width',default=256,type=int)
    parser.add_argument('--height',default=256,type=int)
    parser.add_argument('--framing-padding',default=1.12,type=float)
    parser.add_argument('assets',nargs='+')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    from render_slots import acquire
    acquire()
    tooling=select_tooling()
    from refinement_workspace import prepare,modified,_sha
    import refinement_review
    frozen_fit=refinement_review.fit_camera
    def fit_with_margin(*positional,**keywords):
        keywords['padding']=args.framing_padding
        if asset=='nottingham-southwest-prison-road-props':
            sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
            original=list(keywords['points'])
            keywords['points']=original+[Vector((p.x,p.y,0)) for p in original]+[
                Vector((666,-2334/sine,95/cosine)),Vector((711,-2320/sine,93/cosine))]
        return frozen_fit(*positional,**keywords)
    refinement_review.fit_camera=fit_with_margin
    source=args.source_blend.resolve(strict=True)
    source_hash=_sha(source)
    catalog=json.loads(args.catalog.read_text())
    for asset in args.assets:
        if asset not in refine_environment.ASSETS or asset=='nottingham-terrain-ground':
            raise ValueError('Unsupported environment asset '+asset)
        workspace=args.output.resolve()/asset
        if workspace.exists():raise FileExistsError(workspace)
        bpy.ops.wm.open_mainfile(filepath=str(source))
        preflight_source('nottingham Refinement','nottingham Working',catalog)
        print('ENVIRONMENT START '+asset,flush=True)
        prepared=prepare(workspace,asset_id=asset,scene_name='nottingham Refinement',
            collection_name='nottingham Working',source_path=args.source_image,
            grouping_manifest=args.catalog,inventory_path=args.inventory,review_path=args.review,
            source_mask_manifest=args.source_masks,width=args.width,height=args.height,
            context_padding=96 if asset=='nottingham-southwest-prison-road-props' else 24)
        report=refine_environment.refine(asset)
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
        (workspace/'geometry-recipe.json').write_text(json.dumps(report,indent=2)+'\n')
        validation=modified(workspace)
        if _sha(source)!=source_hash:raise ValueError('Frozen source changed')
        (workspace/'environment-review.json').write_text(json.dumps({
            'asset_id':asset,'geometry_status':report['status'],'approval':'pending',
            'texture_generation':'not started','tooling':tooling,'prepared':prepared,
            'validation':validation,'framing_padding':args.framing_padding,
            'recipe_sha256':_sha(refine_environment.__file__)},indent=2)+'\n')
        print('ENVIRONMENT COMPLETE '+asset,flush=True)


if __name__=='__main__':main()
