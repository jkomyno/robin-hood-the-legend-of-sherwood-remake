"""Refine the prepared watermill; keep packet generation and approval explicit."""
import argparse
import json
from pathlib import Path
import shutil
import sys

import bpy


def run(workspace, render=False):
    workspace = Path(workspace).resolve()
    config = json.loads((workspace/'workspace.json').read_text())
    if config['asset_id'] != 'leicester-watermill' or Path(bpy.data.filepath).resolve() != workspace/'model.blend':
        raise ValueError('Open the isolated watermill model')
    helpers = next(p/'level-editor/blender' for p in workspace.parents if (p/'level-editor/blender/refinement_workspace.py').exists())
    support = Path(__file__).parent/'recipe_support'
    sys.path.insert(0,str(support if support.exists() else helpers/'leicester'))
    sys.path.insert(0,str(helpers))
    from refinement_workspace import validate, modified, _geometry
    from village_shells import repair
    from village_watermill import wheel, rails, finish, SINE, COSINE
    validate(workspace)
    collection = bpy.data.collections[config['collection_name']]
    targets = [o for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id'] and not o.get('projection_component')]
    bynode = {o['source_node']:o for o in targets}
    if set(bynode) != {f'building-{n:03}' for n in range(76,88)}:
        raise ValueError('Watermill canonical node ownership changed')
    root=next(p for p in workspace.parents if p.name=='leicester-refinement')
    native=json.loads((root/'source-audit/Leicester.rhp.json').read_text())
    restored=[]
    for index in (77,78,79,80,81):
        obj=bynode[f'building-{index:03}'];points=native['sight_obstacles'][index]['points'];n=len(points)
        vertices=[(p['x'],-p['y']/SINE,p[z]/COSINE) for z in ('z_bottom','z_top') for p in points]
        faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        restored.append({'source_node':obj['source_node'],**finish(obj,vertices,faces,f'Closed native mill shell {index}'),
                         'reason':'Restore deterministic native closed wall/roof slab before seam reconciliation; imported080/081 had missing internal cut faces.'})
    reports = [repair(o) for o in targets if o['source_node'] not in {f'building-{n:03}' for n in (77,78,79,80,81,84,85,86,87)}]
    mask_path=Path(config['source_mask_manifest']);contract=json.loads(mask_path.read_text())
    for row in contract['projections']['exterior']['assignments']:
        if row.get('source_node') in ('building-079','building-080'):
            row['exclude_mask_indices']=[172,173,175]
            row['exclusion_reason']='Wheel, chimney and railing are separate foreground components. Native174 is a broad actor-occlusion silhouette overlapping intact roof artwork, so it is not a semantic roof exclusion; actual bay geometry supplies first-hit ownership.'
    mask_path.write_text(json.dumps(contract,indent=2)+'\n')
    seams=[]
    for left,right,tolerance in [(77,78,.8),(79,80,3.)]:
        a,b=bynode[f'building-{left:03}'],bynode[f'building-{right:03}']
        va=[a.matrix_world@v.co for v in a.data.vertices]
        vb=[b.matrix_world@v.co for v in b.data.vertices]
        matches=[(i,j) for i,x in enumerate(va) for j,y in enumerate(vb) if (x-y).length<tolerance]
        if len({i for i,j in matches})!=len(matches) or len({j for i,j in matches})!=len(matches):
            raise ValueError('Ambiguous mill roof seam correspondence')
        maximum=0.
        for i,j in matches:
            point=(va[i]+vb[j])/2
            maximum=max(maximum,(point-va[i]).length)
            a.data.vertices[i].co=a.matrix_world.inverted()@point
            b.data.vertices[j].co=b.matrix_world.inverted()@point
        a.data.update();b.data.update()
        seams.append(dict(nodes=[left,right],pairs=len(matches),maximum_movement_world=maximum))
    wheel_objects=[bynode[f'building-{n:03}'] for n in range(84,88)]
    wheel_report=wheel(wheel_objects)
    rail_report=rails(workspace,config)
    # Verify deterministic replacement rather than accumulating components.
    first={o.name:_geometry(o) for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']}
    wheel(wheel_objects);rails(workspace,config)
    second={o.name:_geometry(o) for o in collection.all_objects if o.type=='MESH' and o.get('asset_group')==config['asset_id']}
    if first!=second:raise ValueError('Watermill detail recipe is not idempotent')
    outside=validate(workspace)
    report=dict(asset_id=config['asset_id'],shell_repairs=reports,native_shell_restoration=restored,shared_roof_seams=seams,
                wheel=wheel_report,railings=rail_report,idempotence='PASS',outside_validation=outside,
                limitations=['Wheel lower semicircle, spoke/paddle continuation and axial depth are inferred.',
                             'Attached hut closed plank door and wall joinery remain source artwork; window depth is not reconstructed.',
                             'Stone flume/channel lip geometry remains the imported channel hypothesis, not a hydraulic reconstruction.',
                             'No running wheel animation or water flow is authored.'])
    (workspace/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    if render:
        modified(workspace)
        from leicester.verify_candidate import verify
        verify(workspace)
    if Path(__file__).resolve()!=workspace/'recipe.py':
        shutil.copy2(__file__,workspace/'recipe.py')
        destination=workspace/'recipe_support';destination.mkdir(exist_ok=True)
        for name in ('village_watermill.py','village_shells.py','village_details.py'):
            shutil.copy2(helpers/'leicester'/name,destination/name)
    if render:
        ownership=max((p for p in (workspace/'projection').glob('*/ownership.json') if p.parent.name!='input'),key=lambda p:p.stat().st_mtime_ns)
        handoff=dict(status='validation-pending',all_eight_views_inspected=False,recipe='recipe.py',
                     ownership=str(ownership.relative_to(workspace)),geometry_approval='pending',texture_generation='not-started',
                     has_revealed_state=False,notes=report['limitations'])
        (workspace/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace',type=Path)
    parser.add_argument('--render',action='store_true')
    parser.add_argument('--check-repeat',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.check_repeat:
        run(args.workspace,False)
        from refinement_workspace import _geometry
        def snapshot():
            return {o.name:_geometry(o) for o in bpy.data.objects if o.type=='MESH' and o.get('asset_group')=='leicester-watermill'}
        first=snapshot()
        run(args.workspace,False)
        if first!=snapshot():
            raise ValueError('Full watermill recipe changes geometry on repetition')
        (args.workspace/'recipe-idempotence.json').write_text(json.dumps({'status':'PASS','meshes':len(first),'scope':'All asset geometry across two complete recipe applications'},indent=2)+'\n')
    run(args.workspace,args.render)
