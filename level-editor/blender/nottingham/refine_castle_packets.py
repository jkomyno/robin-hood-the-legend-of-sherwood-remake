"""Rebuild castle review packets and explicit hall display states.

Run in background Blender; geometry approval remains separate from this audit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

WORK = Path(__file__).resolve().parents[2] / 'work/nottingham-refinement'


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def apply_masks(workspace, mask_override):
    config = json.loads((workspace / 'workspace.json').read_text())
    side = json.loads(Path(mask_override).read_text())
    path = Path(config['source_mask_manifest'])
    masks = json.loads(path.read_text())
    owned = set(config['part_ids'])
    assignments = side.get('projections', {side.get('projection', 'exterior'): side.get('assignments', [])})
    for label, rows in assignments.items():
        for row in rows:
            row = dict(row)
            if workspace.name == 'nottingham-castle-main-hall' and row.get('projection_component') == 'castle-hall-floor':
                row['source_node'] = 'building-501'
            if row['source_node'] not in owned:
                continue
            values = masks['projections'][label]['assignments']
            identity = (row['source_node'], row.get('projection_component'))
            values[:] = [v for v in values if (v['source_node'], v.get('projection_component')) != identity]
            values.append(row)
    write(path, masks)


def repair_hall_floor(workspace):
    """Migrate the earlier duplicate ceiling-footprint floor to native floor501."""
    import bpy
    from refine_castle_secondary import native_prism
    working = bpy.data.collections['nottingham Working']
    native = json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles']
    old = [o for o in working.all_objects if o.get('source_node') == 'building-530'
           and o.get('projection_component') == 'castle-hall-floor']
    if not old:
        return
    primary = next(o for o in working.all_objects if o.get('source_node') == 'building-501'
                   and not o.get('castle_hall_generated'))
    rows = []
    for component, bottom, top in [('castle-hall-floor-support',0,418),('castle-hall-floor',418,420.001)]:
        obj = bpy.data.objects.new('building-501__'+component, primary.data.copy())
        working.objects.link(obj)
        obj.parent=primary.parent
        obj.matrix_parent_inverse=primary.matrix_parent_inverse.copy()
        obj.matrix_world=primary.matrix_world.copy()
        for key in primary.keys():
            obj[key]=primary[key]
        points=[dict(p,z_top=top) for p in native[501]['points']]
        result=native_prism(obj,points,bottom=bottom)
        obj['castle_hall_generated']=True
        obj['projection_component']=component
        obj['reveal_component_patch_id']='patch-008'
        obj['reveal_component_role']='interior-receiver' if component=='castle-hall-floor' else 'retained-shell'
        rows.append({'object':obj.name,'native_bottom':bottom,'native_top':top,**result})
    primary.hide_render=True
    primary.hide_set(True)
    for obj in old:
        bpy.data.objects.remove(obj,do_unlink=True)
    config=json.loads((workspace/'workspace.json').read_text())
    path=Path(config['source_mask_manifest'])
    masks=json.loads(path.read_text())
    for row in masks['projections']['interior-patch-008']['assignments']:
        if row.get('source_node')=='building-530' and row.get('projection_component')=='castle-hall-floor':
            row['source_node']='building-501'
            row['review_note']+=' Receiver corrected to actual native floor501 after source-camera first-hit diagnosis.'
    write(path,masks)
    write(workspace/'floor-correction.json',{'version':1,'changes':rows,
        'removed':'Duplicate floor under530 at420 was obscured by actual floor501 at420.001.',
        'evidence':'castle-audit/hall-rays.log','outside_objects_modified':False})


def hall(workspace, mask_override=None):
    import bpy
    from refine_castle import refine
    from refinement_workspace import modified, initialize_working_masks
    from asset_reference_views import render_states
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    repair_hall_floor(workspace)
    report = refine('nottingham-castle-main-hall')
    if report.get('status') != 'already-refined':
        write(workspace / 'geometry-report.json', report)
    from refine_castle_interior import refine as interior_details
    interior_details(workspace)
    config = json.loads((workspace / 'workspace.json').read_text())
    path = Path(config['projection_manifest'])
    layers = json.loads(path.read_text())
    review = layers['projection_reviews']['patch-008']
    if review.get('role') == 'deferred-interior':
        visibility = review['render_visibility']
        template = json.loads((WORK/'state-review/nottingham-castle-main-hall-layers.json').read_text())
        review = template['projection_reviews']['patch-008']
        review['render_visibility'] = visibility
        layers['projection_reviews']['patch-008'] = review
    for number in (502,527,528):
        node = f'building-{number}'
        if node not in review['partial_cover_nodes']:
            review['partial_cover_nodes'].append(node)
        selector = {'source_node':node,'projection_component':'castle-hall-removable-cover','patch_id':'patch-008'}
        if selector not in review['exclude_occluder_components']:
            review['exclude_occluder_components'].append(selector)
    review['evidence'] = 'Native501 is the room floor at420.001;530 is a separate ceiling cover near590. Source-camera first-hit diagnosis rejected the duplicate530 floor. Native461 after foreground, fixture and roof exclusions supports retained interior wall504; native466 owns the independently modeled hanging fixture.'
    review['receiver_nodes'] = ['building-501', 'building-504', 'building-505', 'building-506', 'building-533', 'building-534', 'building-535']
    review['receiver_components'] = {
        'exterior': [{'source_node': 'building-530', 'projection_components': ['castle-hall-ceiling-cover'], 'patch_id': 'patch-008'}],
        'interior-patch-008': [{'source_node': 'building-501', 'projection_components': ['castle-hall-floor'], 'patch_id': 'patch-008'}]}
    review['receiver_components']['exterior'].append({'source_node': 'building-501', 'projection_components': ['castle-hall-floor-support'], 'patch_id': 'patch-008'})
    for number in (505, 506):
        review['receiver_components']['exterior'].append({'source_node': f'building-{number}', 'projection_components': ['castle-hall-removable-cover'], 'patch_id': 'patch-008'})
        review['receiver_components']['interior-patch-008'].append({'source_node': f'building-{number}', 'projection_components': ['castle-hall-retained-roof'], 'patch_id': 'patch-008'})
    visibility = review['render_visibility']
    visibility['covered']['hidden_components'] = [{'source_node':'building-504','projection_component':'castle-hall-chandelier','patch_id':'patch-008'}]
    visibility['revealed']['hidden_components'] = review['exclude_occluder_components']
    visibility['evidence'] += ' Authored roof and upper-wall cover components are absent in the revealed display; the actual floor501 remains under the covered roof.'
    write(path, layers)
    initialize_working_masks(workspace)
    apply_masks(workspace, WORK/'mask-review/component-state-overrides-v11.json')
    if mask_override:
        apply_masks(workspace, mask_override)
    apply_masks(workspace, WORK/'mask-review/hall-wall-overrides-v11.json')
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    modified(workspace)
    index = 1
    while (workspace / f'states-{index}').exists():
        index += 1
    output = workspace / f'states-{index}'
    render_states(workspace, output)
    write(workspace / 'state-packet.json', {'version': 1, 'directory': str(output),
        'revealed_input': 'input', 'baseline_note': 'The immutable input predates authored cutaway geometry and is the opaque baseline.'})
    print('CASTLE HALL STATES COMPLETE ' + str(output), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--mask-override', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_slots import acquire
    acquire()
    from freeze_tooling import select_tooling
    select_tooling()
    workspace = args.workspace.resolve()
    if workspace.name == 'nottingham-castle-main-hall':
        hall(workspace, args.mask_override)
    else:
        import bpy
        from refinement_workspace import modified, initialize_working_masks
        bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
        initialize_working_masks(workspace)
        if args.mask_override:
            apply_masks(workspace, args.mask_override)
        modified(workspace)


if __name__ == '__main__':
    main()
