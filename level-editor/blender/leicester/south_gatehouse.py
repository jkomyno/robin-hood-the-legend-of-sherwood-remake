"""Constrain the gatehouse front wall to its measured roof eave.

Run on an immutable-input worker copy, then regenerate its projection packet.
The cutaway chamber and native gate state require separate review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import uuid

import bpy

TAG = 'leicester-gatehouse-front-eave-v1'
EAVE_Z = 344.26


def refine():
    collection = bpy.data.collections['Leicester Working']
    if any(o.get('south_gatehouse_refinement') == TAG for o in collection.all_objects):
        return {'reused': True, 'source_node': 'building-139'}
    targets = [o for o in collection.all_objects if o.type == 'MESH'
               and o.get('asset_group') == 'leicester-south-gatehouse'
               and o.get('source_node') == 'building-139' and not o.hide_render]
    if len(targets) != 1:
        raise RuntimeError('Expected exactly one visible front wall component')
    obj = targets[0]
    if obj.get('south_gatehouse_refinement') == TAG:
        return {'reused': True, 'source_node': 'building-139'}
    transform = obj.matrix_world.copy()
    inverse = transform.inverted()
    world = [transform @ vertex.co for vertex in obj.data.vertices]
    high = [(i, p.copy()) for i, p in enumerate(world) if p.z > 430]
    if not high or max(p.z for p in world) > 436:
        raise RuntimeError('Front wall anchor topology differs from frozen inventory')
    changes = []
    for index, point in high:
        before = list(point)
        point.z = EAVE_Z
        obj.data.vertices[index].co = inverse @ point
        changes.append({'vertex': index, 'before': before, 'after': list(point)})
    obj.data.update()
    obj['south_gatehouse_refinement'] = TAG
    obj['todo'] = 'Review chamber cutaway, front embrasures and gate-state ownership separately.'
    bpy.context.view_layer.update()
    drift = max(abs(obj.matrix_world[i][j] - transform[i][j])
                for i in range(4) for j in range(4))
    if drift:
        raise RuntimeError('Object transform changed')
    return {'reused': False, 'source_node': 'building-139', 'eave_z': EAVE_Z,
            'changes': changes, 'vertices': len(obj.data.vertices),
            'faces': len(obj.data.polygons), 'world_transform_drift': drift,
            'topology_changed': False, 'uv_coordinates_changed_before_reprojection': False,
            'source_evidence': {'front_eave_pixel_anchors': [[675.3, 1144.4], [858.1, 1204.9]],
                                'roof_apex_z': 415.06},
            'limitations': ['Chamber cutaway receivers require independent state validation.',
                            'Three upper front embrasures remain represented in source projection.',
                            'Gate leaf belongs to a separate stateful asset.']}


def refine_masks(workspace):
    """Retain separate native pier ownership and the visible chamber coping."""
    path = Path(workspace) / 'source-masks.json'
    masks = json.loads(path.read_text())
    exterior = masks['projections']['exterior']['assignments']
    pier = next(a for a in exterior if a.get('source_node') == 'building-146')
    pier['mask_indices'] = [203, 204]
    pier['evidence'] = ('Native203 stops at the left portal opening; native204 owns '
                        'the separately occluding left arch/pier. Both remain gated by receiver geometry.')
    interior = masks['projections']['interior-patch-004']['assignments']
    floor = next(a for a in interior if a.get('source_node') == 'building-138')
    floor['exclude_mask_indices'] = [269]
    floor['exclusions_reviewed'] = True
    floor['exclusion_reason'] = ('Exclude separate winch269. The floor receiver includes the exposed '
                                 'stone coping beside the timber, so subtracting rim268 incorrectly '
                                 'discarded known source pixels from this physical top surface.')
    floor['evidence'] = ('Native267 upper-tower silhouette, native268 revealed coping/roof rim, '
                         'and native269 winch were checked against both state sheets. '
                         'Actual mesh depth and retained shell determine visible floor ownership.')
    for assignment in interior:
        if assignment.get('source_node') not in ('building-141', 'building-147'):
            continue
        assignment['exclude_mask_indices'] = [269]
        assignment['exclusions_reviewed'] = True
        assignment['exclusion_reason'] = (
            'The exposed masonry wall coping belongs to the physical chamber wall. '
            'Native268 also contains this coping, so subtracting it removes known '
            'revealed pixels. Separate retained shell geometry occludes roof and '
            'front-wall pixels; native269 remains the independent winch receiver.')
        assignment['evidence'] = 'Paired revealed source and actual-material sheets; native267/268/269.'
    path.write_text(json.dumps(masks, indent=2) + '\n')
    return {'left_pier': [203, 204], 'floor': [267], 'floor_excludes': [269]}


def refine_visibility(workspace):
    from refinement_workspace import initialize_working_projection
    path = Path(initialize_working_projection(workspace))
    manifest = json.loads(path.read_text())
    visibility = manifest['projection_reviews']['patch-004']['render_visibility']
    # Rear and side masonry retains its physical exterior face in both states.
    # Only the removable cover and dedicated chamber props change visibility.
    visibility['covered']['hidden_components'] = [
        selector for selector in visibility['covered']['hidden_components']
        if not (selector['source_node'] in ('building-141', 'building-147')
                and selector['projection_component'] == 'interior-wall')]
    visibility['covered']['hidden_nodes'] = [
        node for node in visibility['covered']['hidden_nodes'] if node != 'building-138']
    evidence = ('Reverse-view material inspection confirms that shared rear/side '
                'wall pieces and physical floor remain present in the covered state; their interior '
                'source faces are concealed by the cover.')
    if evidence not in visibility['evidence']:
        visibility['evidence'] += ' ' + evidence
    path.write_text(json.dumps(manifest, indent=2) + '\n')


def refine_coping(workspace):
    """Split the measured exposed lower-body top from its exterior piers."""
    from refinement_workspace import initialize_working_projection
    from south_structures import topology
    collection=bpy.data.collections['Leicester Working']
    if any(o.get('projection_component')=='chamber-coping' for o in collection.all_objects):
        return {'reused':True}
    source=next(o for o in collection.all_objects if o.type=='MESH' and o.get('source_node')=='building-137' and not o.hide_render)
    highest=max((source.matrix_world@v.co).z for v in source.data.vertices)
    if abs(highest-250.26)>.05:raise RuntimeError('Unexpected gatehouse lower-body elevation')
    bpy.ops.mesh.primitive_cube_add(size=1,location=(800,-2500,highest+498.5))
    cutter=bpy.context.object;cutter.dimensions=(2000,2000,1003);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    records=[]
    for operation,role in [('DIFFERENCE','lower-exterior'),('INTERSECT','chamber-coping')]:
        obj=source.copy();obj.data=source.data.copy();obj.name=source.name+' / '+role;collection.objects.link(obj)
        modifier=obj.modifiers.new('Measured coping separation','BOOLEAN');modifier.operation=operation;modifier.solver='EXACT';modifier.object=cutter
        bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=modifier.name)
        obj['projection_component']=role;obj['reveal_component_patch_id']='patch-004';obj['reveal_component_role']=role
        records.append({'component':role,**topology(obj)})
    bpy.data.objects.remove(cutter,do_unlink=True);source.hide_render=True;source.hide_set(True)
    path=Path(initialize_working_projection(workspace));manifest=json.loads(path.read_text());review=manifest['projection_reviews']['patch-004']
    review['receiver_nodes']=sorted(set(review['receiver_nodes']+['building-137']))
    for label,role in [('exterior','lower-exterior'),('interior-patch-004','chamber-coping')]:
        review['receiver_components'][label].append({'source_node':'building-137','projection_components':[role],'patch_id':'patch-004'})
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    masks_path=workspace/'source-masks.json';masks=json.loads(masks_path.read_text())
    masks['projections']['interior-patch-004']['assignments'].append({
        'source_node':'building-137','mask_indices':[267,268],'exclude_mask_indices':[269],
        'reviewed':True,'exclusions_reviewed':True,'exclusion_reason':'Independent winch269.',
        'evidence':'Native coping pixels8651245 and8701240 raycast to lower-body top250.26 beneath notched floor138; dedicated closed3-unit cap retains this physical receiver.'})
    masks_path.write_text(json.dumps(masks,indent=2)+'\n')
    return {'top_world_z':highest,'cap_thickness':3,'components':records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--cutaway', action='store_true')
    parser.add_argument('--states', action='store_true')
    parser.add_argument('--apertures', action='store_true')
    parser.add_argument('--states-only', action='store_true')
    parser.add_argument('--coping', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    workspace = args.workspace.resolve()
    if not (workspace / 'input' / 'views.json').is_file():
        raise RuntimeError('Frozen input packet must exist before refining')
    if Path(bpy.data.filepath).resolve() != workspace / 'model.blend':
        raise RuntimeError('Open the worker model.blend, never the baseline')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if args.states_only:
        from asset_reference_views import render_states
        from refinement_workspace import validate
        refine_visibility(workspace)
        target = workspace / 'inspection/states'
        if target.exists():
            history = workspace / 'inspection/state-history'
            history.mkdir(exist_ok=True)
            target.rename(history / uuid.uuid4().hex[:12])
        render_states(workspace, target)
        validate(workspace)
        return
    report_path = workspace / 'geometry-report.json'
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    eave = refine()
    if not eave.get('reused') or 'eave' not in report:
        report['eave'] = eave
    if args.cutaway:
        import south_cutaway
        cutaway = south_cutaway.refine(workspace)
        if not cutaway.get('reused') or 'cutaway' not in report:
            report['cutaway'] = cutaway
    if args.apertures:
        import south_apertures
        apertures = south_apertures.refine()
        if not apertures.get('reused') or 'apertures' not in report:
            report['apertures'] = apertures
    if args.coping:
        coping=refine_coping(workspace)
        if not coping.get('reused'):report['coping']=coping
    report['native_masks'] = refine_masks(workspace)
    refine_visibility(workspace)
    report['recipe_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    (workspace / 'geometry-report.json').write_text(json.dumps(report, indent=2) + '\n')
    # Reload removes stale collection-cache entries left by replaced components.
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'), load_ui=False)
    from refinement_workspace import modified
    modified(workspace)
    if args.states:
        from asset_reference_views import render_states
        target = workspace / 'inspection/states'
        if target.exists():
            history = workspace / 'inspection/state-history'
            history.mkdir(exist_ok=True)
            target.rename(history / uuid.uuid4().hex[:12])
        render_states(workspace, target)


if __name__ == '__main__':
    main()
