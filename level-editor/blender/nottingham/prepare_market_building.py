"""Make a review workspace for one building of the approved seven-part market."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'


def geometry(obj):
    return {'vertices':[list(v.co)for v in obj.data.vertices],
            'faces':[list(p.vertices)for p in obj.data.polygons],
            'matrix':[list(row)for row in obj.matrix_world]}


def main():
    import bpy
    parser=argparse.ArgumentParser();parser.add_argument('--asset',required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    proposal=json.loads((WORK/'town-audit/market-seven-building-grouping-proposal.json').read_text())
    building=next(g for g in proposal['buildings']if g['proposed_id']==args.asset)
    sys.path.insert(0,str(Path(__file__).parent))
    from render_slots import acquire
    acquire()
    from freeze_tooling import select_tooling
    tooling=select_tooling(WORK/'tooling/94116d984f92dbae')
    from refinement_workspace import prepare,modified
    evidence=WORK/'grouped/nottingham-grouped-v9.evidence'
    workspace=WORK/'round-10/assets'/args.asset
    if workspace.exists():raise FileExistsError(workspace)
    bpy.ops.wm.open_mainfile(filepath=str(WORK/'grouped/nottingham-grouped-v9.blend'));bpy.context.view_layer.update()
    owned=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==args.asset and not o.hide_render]
    before={o.name:geometry(o)for o in owned}
    prepare(workspace,asset_id=args.asset,scene_name='nottingham Refinement',collection_name='nottingham Working',
            source_path=WORK/'source-states/covered.png',grouping_manifest=evidence/'catalog.json',
            inventory_path=evidence/'inventory.json',review_path=evidence/'grouping-review.json',
            source_mask_manifest=WORK/'round-1/assets/nottingham-market-terrace/source-masks.json',
            width=256,height=320,elevation_degrees=35,context_padding=24)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    print(modified(workspace),flush=True)
    after={o.name:geometry(o)for o in owned}
    if before!=after:raise ValueError('Projection changed approved partition geometry')
    report={'version':1,'asset_id':args.asset,'building_number':building['number'],'approved_parent_sha256':proposal['approved_geometry_sha256'],
            'partition_proof':str(WORK/'market-partitions-v9/partition-proof.json'),'grouping_revision':9,
            'post_projection_geometry_preserved':True,'owned_objects':list(before),'tooling':tooling,
            'scope':'Grouping-only revision of approved geometry; inferred internal party-wall caps only.',
            'limitations':['Native open roof/structural fragments remain exactly as approved. No concealed building envelope was invented.','Rear east source019 is an open lean-roof and side fragment, not a newly reconstructed closed house.']if building['number']==7 else ['Native open structural boundaries remain exactly as approved; this change only partitions ownership.']}
    (workspace/'membership-revision.json').write_text(json.dumps(report,indent=2)+'\n')
    candidate={'version':1,'asset_id':args.asset,'status':'fix-needed','geometry_refined':True,'geometry_reviewed':False,
               'inspected_views':[],'recipe':str(Path(__file__).resolve()),'model_sha256':hashlib.sha256((workspace/'model.blend').read_bytes()).hexdigest(),
               'modified_views_sha256':hashlib.sha256((workspace/'modified/views.json').read_bytes()).hexdigest(),
               'changes':['Separate this building from approved market terrace; preserve its existing geometry.',*(['Partition shared masonry base012 with disjoint provenance and internal party-wall caps.']if building['number']<=4 else [])],
               'limitations':report['limitations'],'geometry_approval':'pending','texture_generation':'not-started','membership_evidence':'membership-revision.json'}
    (workspace/'candidate.json').write_text(json.dumps(candidate,indent=2)+'\n')
    (workspace/'review.md').write_text('# Market building grouping revision\n\nThe prior whole-terrace geometry approval is preserved. This fresh packet awaits review of its new standalone ownership and framing.\n\n'+report['scope']+'\n\n'+'\n'.join(report['limitations'])+'\n')


if __name__=='__main__':main()
