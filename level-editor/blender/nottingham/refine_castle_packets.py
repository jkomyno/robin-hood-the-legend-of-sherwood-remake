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
            if row['source_node'] not in owned:
                continue
            values = masks['projections'][label]['assignments']
            identity = (row['source_node'], row.get('projection_component'))
            values[:] = [v for v in values if (v['source_node'], v.get('projection_component')) != identity]
            values.append(row)
    write(path, masks)


def hall(workspace, mask_override=None):
    import bpy
    from refine_castle import refine
    from refinement_workspace import modified, initialize_working_masks
    from asset_reference_views import render_states
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    report = refine('nottingham-castle-main-hall')
    if report.get('status') != 'already-refined':
        write(workspace / 'geometry-report.json', report)
    config = json.loads((workspace / 'workspace.json').read_text())
    path = Path(config['projection_manifest'])
    layers = json.loads(path.read_text())
    review = layers['projection_reviews']['patch-008']
    review['receiver_nodes'] = ['building-505', 'building-506', 'building-530', 'building-533', 'building-534', 'building-535']
    review['receiver_components'] = {
        'exterior': [{'source_node': 'building-530', 'projection_components': ['castle-hall-ceiling-cover'], 'patch_id': 'patch-008'}],
        'interior-patch-008': [{'source_node': 'building-530', 'projection_components': ['castle-hall-floor'], 'patch_id': 'patch-008'}]}
    for number in (505, 506):
        review['receiver_components']['exterior'].append({'source_node': f'building-{number}', 'projection_components': ['castle-hall-removable-cover'], 'patch_id': 'patch-008'})
        review['receiver_components']['interior-patch-008'].append({'source_node': f'building-{number}', 'projection_components': ['castle-hall-retained-roof'], 'patch_id': 'patch-008'})
    visibility = review['render_visibility']
    visibility['covered']['hidden_components'] = [
        {'source_node': 'building-530', 'projection_component': 'castle-hall-floor', 'patch_id': 'patch-008'}]
    visibility['revealed']['hidden_components'] = review['exclude_occluder_components']
    visibility['evidence'] += ' Authored roof and upper-wall cover components are absent in the revealed display; the room floor is absent in the covered display.'
    write(path, layers)
    initialize_working_masks(workspace)
    if mask_override:
        apply_masks(workspace, mask_override)
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
