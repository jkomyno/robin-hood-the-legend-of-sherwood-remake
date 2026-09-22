"""Freeze V7 courtyard/stair packets with room for measured stair endpoints."""
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from refine_castle_secondary import WORK,write,sha
from freeze_tooling import select_tooling

def main():
    tooling=select_tooling(WORK/'tooling-common-v1/2fbc2cbceea1fd2d')
    from render_slots import acquire
    acquire()
    import bpy
    from mathutils import Vector
    import refinement_review
    from refinement_workspace import prepare,validate
    from prepare_assets import preflight_source
    original=refinement_review.fit_camera
    def fit(*args,**kwargs):
        kwargs['padding']=1.15
        if asset.endswith('southwest-stair'):
            s,c=math.sin(math.radians(35)),math.cos(math.radians(35))
            kwargs['points']=list(kwargs['points'])+[Vector((x,-y/s,z/c)) for x in (615,780) for y in (1570,1800) for z in (0,175)]
        return original(*args,**kwargs)
    refinement_review.fit_camera=fit
    catalog=WORK/'grouping/catalog-v7.json'
    for short in ['castle-west-courtyard-wall','castle-southwest-stair']:
        asset='nottingham-'+short
        workspace=WORK/'round-5/assets'/asset
        if workspace.exists():raise FileExistsError(workspace)
        bpy.ops.wm.open_mainfile(filepath=str(WORK/'grouped/nottingham-grouped-v7.blend'))
        preflight_source('nottingham Refinement','nottingham Working',json.loads(catalog.read_text()))
        prepared=prepare(workspace,asset_id=asset,scene_name='nottingham Refinement',collection_name='nottingham Working',
            source_path=WORK/'source-states/covered.png',grouping_manifest=catalog,inventory_path=WORK/'inventory/inventory-v2.json',
            review_path=WORK/'grouping/grouping-review-v7.json',source_mask_manifest=WORK/'mask-review/source-masks-v11-baseline.json',
            width=384,height=448,context_padding=150)
        write(workspace/'preparation.json',{'tooling':tooling,'prepared':prepared,'validation':validate(workspace),'recipe_sha256':sha(__file__)})
        if short=='castle-west-courtyard-wall':
            from refine_castle_secondary_details import apply
            apply(workspace)

if __name__=='__main__':main()
