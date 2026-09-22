"""Prepare pending church-house membership revisions without editing prior packets.

Run in a disposable Blender process with --asset <north/west asset ID>.
The prior northern-house approval remains attached to its old revision only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry_signature(obj):
    data={'vertices':[list(v.co)for v in obj.data.vertices],
          'faces':[list(p.vertices)for p in obj.data.polygons]}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def main():
    import bpy
    parser=argparse.ArgumentParser();parser.add_argument('--asset',required=True,choices=['nottingham-church-north-house','nottingham-church-west-house']);args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    sys.path.insert(0,str(Path(__file__).parent))
    from render_slots import acquire
    acquire()
    from freeze_tooling import select_tooling
    tooling=select_tooling()
    from refinement_workspace import prepare,modified
    asset=args.asset;workspace=WORK/'round-9/assets'/asset;old=WORK/'round-1/assets'/asset;evidence=WORK/'grouped/nottingham-grouped-v7.evidence'
    prior_hash=digest(old/'model.blend')
    bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
    bpy.context.view_layer.update()
    prior_matrices={o['source_node']:o.matrix_world.copy() for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==asset}
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'baseline.blend' if workspace.exists() else WORK/'grouped/nottingham-grouped-v7.blend'))
    if not workspace.exists():prepare(workspace,asset_id=asset,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=WORK/'source-states/covered.png',grouping_manifest=evidence/'catalog.json',inventory_path=evidence/'inventory.json',review_path=evidence/'grouping-review.json',source_mask_manifest=WORK/'mask-review/source-masks-v11-baseline.json',width=256,height=320,elevation_degrees=35,context_padding=24)
    old_names=json.loads((old/'modified/views.json').read_text())['object_names']
    targets={o['source_node']:o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==asset}
    names=old_names if asset.endswith('north-house') else [name for name in old_names if '128'in name]
    with bpy.data.libraries.load(str(old/'model.blend'),link=False)as(source,target):
        if set(names)-set(source.objects):raise ValueError('Missing approved source objects')
        target.objects=names
    copies=list(target.objects);records=[]
    for source in copies:
        destination=targets[source['source_node']];signature=geometry_signature(source)
        destination.data=source.data.copy();destination.matrix_world=prior_matrices[source['source_node']].copy()
        if geometry_signature(destination)!=signature:raise ValueError('Prior geometry transfer changed positions/faces/transforms')
        records.append({'source_node':source['source_node'],'prior_geometry_sha256':signature,'transferred_geometry_sha256':geometry_signature(destination),'prior_matrix_world':[list(row)for row in prior_matrices[source['source_node']]]})
        bpy.data.objects.remove(source,do_unlink=True)
    if asset.endswith('north-house'):
        masks=json.loads((workspace/'source-masks.json').read_text())
        assignment=next(a for a in masks['projections']['exterior']['assignments']if a['source_node']=='building-129')
        assignment.update(mask_indices=[88,90],review_evidence=str(WORK/'town-audit/building-129-grouping-diagnosis.json'),review_note='Visible stone chimney on northern house roof131; native cap footprint and source artwork place it here, not western house128. Existing northern-house silhouette domains88/90 cover the chimney cap; foreground remains depth-tested.')
        (workspace/'source-masks.json').write_text(json.dumps(masks,indent=2)+'\n')
    if prior_hash!=digest(old/'model.blend'):raise ValueError('Prior model was altered')
    report={'asset_id':asset,'prior_workspace':str(old),'prior_model_sha256':prior_hash,'catalog_revision':7,'preserved_prior_meshes':records,'membership_change':'Add chimney129 to northern house130..134'if asset.endswith('north-house')else'Remove chimney129; retain western house128 exactly','prior_revision_untouched':True,'geometry_approval':'pending','tooling':tooling,'recipe':str(Path(__file__).resolve())}
    (workspace/'membership-revision.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));print(modified(workspace),flush=True)
    # Projection may change UVs/materials, but must retain the transferred mesh.
    for record in records:
        if geometry_signature(targets[record['source_node']])!=record['transferred_geometry_sha256']:raise ValueError('Projection changed approved geometry')
    report['post_projection_geometry_preserved']=True
    report['maximum_transform_roundoff']=max(abs(a-b)for rec in records for row,old in zip(targets[rec['source_node']].matrix_world,rec['prior_matrix_world'])for a,b in zip(row,old))
    if report['maximum_transform_roundoff']>1e-5:raise ValueError('Unexpected transform drift')
    (workspace/'membership-revision.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
