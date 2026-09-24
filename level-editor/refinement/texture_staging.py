"""Validate explicit texture approvals and select their exact baked workers.

This produces guarded import metadata, never publishes or changes a worker.
Blender callers must also run verify_baked_geometry before importing/exporting.
"""
import argparse
import hashlib
import json
from pathlib import Path
from review_evidence import sha
from texture_decisions import evidence, fields


def _json(path):
    return json.loads(Path(path).read_text())


def _unique(values, label):
    if (not isinstance(values, list) or not values or
            any(not isinstance(v, str) or not v for v in values) or len(set(values)) != len(values)):
        raise ValueError('Expected exact unique ' + label)
    return values


def _derived_packet(experiment, frames, item, protected):
    """Reconstruct immutable packet data when a reviewed retry lacks its receipt."""
    import numpy as np
    from PIL import Image
    source = Path(frames['reviewed_packet']).resolve(strict=True)
    frame_path = source/'views.json'
    if sha(frame_path) != frames.get('reviewed_manifest_sha256'):
        raise ValueError('Derived texture camera source changed')
    bound = {Path(entry['path']).resolve(): entry['sha256'] for entry in item['revision']['evidence'].values()}
    if bound.get(frame_path) != sha(frame_path):
        raise ValueError('Derived texture packet lacks directly approved camera evidence')
    original = _json(frame_path)
    additions = {'reviewed_packet', 'reviewed_manifest_sha256', 'source_blend', 'geometry_revision',
                 'input_sha256', 'texture_view_selection', 'texture_preferred_face_views'}
    for key, value in original.items():
        if key not in {'views', 'layout', 'source_blend', 'geometry_revision', 'input_sha256'} and frames.get(key) != value:
            raise ValueError('Derived texture packet changed approved camera/ownership: ' + key)
    if set(frames) - set(original) - additions:
        raise ValueError('Unsupported derived texture packet override')
    for key in ('input.png', 'solid.png'):
        authoritative = source/('textured.png' if key == 'input.png' else key)
        if sha(experiment/key) != sha(authoritative):
            raise ValueError('Derived texture input differs from approved source sheet')
        protected[authoritative] = sha(authoritative)
    width, height = original['tile_size']
    expected_mask = np.full((height*2, width*4, 4), 255, dtype=np.uint8)
    approved_solid = np.asarray(Image.open(source/'solid.png').convert('RGBA'))
    for old, actual in zip(original['views'], frames['views'], strict=True):
        expected = dict(old); index = old['index']
        expected.update(input=f'views/view-{index}-input.png', mask=f'views/view-{index}-mask.png',
                        crop={'left': index % 4 * width, 'top': index // 4 * height, 'width': width, 'height': height})
        if actual != expected:
            raise ValueError('Derived texture packet changed a frozen camera')
        known = source/'views'/f'view-{index}-known.png'
        solid = source/'views'/f'view-{index}-solid.png'
        if sha(known) != old['ownership_sha256']:
            raise ValueError('Derived source ownership buffer changed')
        top, left = index // 4 * height, index % 4 * width
        tile = np.asarray(Image.open(solid).convert('RGBA'))
        if not np.array_equal(tile, approved_solid[top:top+height, left:left+width]):
            raise ValueError('Derived solid tile differs from approved geometry sheet')
        unknown = (tile[:, :, 3] > 0) & (np.asarray(Image.open(known).convert('RGBA'))[:, :, 0] <= 127)
        expected_mask[top:top+height, left:left+width, 3][unknown] = 0
        protected[known] = sha(known); protected[solid] = sha(solid)
    if not np.array_equal(expected_mask, np.asarray(Image.open(experiment/'mask.png').convert('RGBA'))):
        raise ValueError('Derived texture mask differs from approved ownership')
    layout = dict(original['layout']); layout.update(width=width*4, height=height*2)
    if frames['layout'] != layout:
        raise ValueError('Derived texture canvas changed')
    protected[frame_path] = sha(frame_path)
    protected[experiment/'mask.png'] = sha(experiment/'mask.png')


def validate_texture_handoff(geometry_manifest, asset_id, texture_decisions_path, geometry_decisions=None, *, _state=None):
    from stage_approved_editor_asset import validate
    geometry_manifest = Path(geometry_manifest).resolve(strict=True)
    texture_decisions_path = Path(texture_decisions_path).resolve(strict=True)
    item, workspace, protected = validate(geometry_manifest, asset_id, geometry_decisions)
    data = _json(texture_decisions_path)
    if data.get('version') != 1 or not isinstance(data.get('decisions'), list):
        raise ValueError('Expected texture decisions version 1')
    records = [d for d in data['decisions'] if d.get('asset_id') == asset_id and d.get('scope') == 'texture']
    if not records or records[-1].get('decision') != 'approved':
        raise ValueError('Latest explicit texture decision must approve this asset')
    decision = records[-1]
    if not decision.get('exact_user_text', '').strip():
        raise ValueError('Texture decision requires exact user text')
    paths = {key: Path(value).resolve(strict=True) for key, value in decision['evidence_paths'].items()}
    record = {'id': asset_id, 'texture_states': decision.get('texture_states', [])}
    image_fields, report_fields = fields(record)
    record.update({key: str(paths[key]) for key in (*image_fields, *report_fields)})
    current_paths, hashes = evidence(record)
    if hashes != decision.get('evidence_sha256') or any(current_paths[k].resolve() != paths[k] for k in current_paths):
        raise ValueError('Texture decision differs from current baked evidence')
    binding = {'images': {key: hashes[key] for key in image_fields},
               'reports': {key: hashes[key] for key in report_fields}}
    if hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest() != decision['review_revision']:
        raise ValueError('Texture gallery revision does not match displayed evidence')
    all_paths = dict(paths)
    if _state is not None:
        state_records = [state for state in decision.get('texture_states', []) if state['id'] == _state]
        if len(state_records) != 1 or not state_records[0].get('model'):
            raise ValueError('Supplemental texture state requires an explicitly approved baked model')
        state = state_records[0]
        if set(state['image_fields']) != set(fields({'id': asset_id})[0]) or set(state['report_fields']) != {'validation', 'review'}:
            raise ValueError('Baked texture state requires complete image and validation evidence')
        prefix = 'texture_state_' + _state + '_'
        paths = {key: all_paths[prefix + key] for key in (*fields({'id': asset_id})[0], 'validation', 'review', 'model')}
        hashes = {key: sha(path) for key, path in paths.items()}
    experiment = paths['solid'].parent
    approval_path, frames_path = experiment/'approval.json', experiment/'views.json'
    approval, frames = _json(approval_path), _json(frames_path)
    review, validation = _json(paths['review']), _json(paths['validation'])
    endpoint_id = approval.get('endpoint_id')
    expected_model = item['revision']['model_sha256']
    if item.get('endpoint_reviews'):
        endpoints = {entry['id']: entry for entry in item['endpoint_reviews']}
        if len(item['endpoint_reviews']) != 2 or set(endpoints) != {'initial', 'applied'} or endpoint_id not in endpoints:
            raise ValueError('Paired texture handoff must select an approved initial/applied endpoint')
        endpoint = endpoints[endpoint_id]
        if endpoint.get('status') != 'ready-for-user' or approval.get('paired_model_sha256') != {key: value['model_sha256'] for key, value in endpoints.items()}:
            raise ValueError('Texture endpoint model pair differs from approved geometry')
        expected_model = endpoint['model_sha256']
        workspace = Path(endpoint['workspace']).resolve(strict=True)
        for field in ('model', 'frames', 'workspace_config'):
            target = Path(endpoint[field]).resolve(strict=True)
            if target not in {path.resolve() for path in protected}:
                raise ValueError('Endpoint source is absent from current approved geometry evidence')
        if _state is not None and endpoint_id != _state:
            raise ValueError('Texture endpoint identity differs from approved state identifier')
    elif endpoint_id is not None:
        raise ValueError('Texture endpoint is absent from geometry approval')
    config_path = workspace/'workspace.json'; config = _json(config_path)
    if (approval.get('status') != 'approved' or approval.get('approved_by') != 'user' or
            approval.get('asset_id') != asset_id or approval.get('geometry_revision') != item['revision']['sha256'] or
            approval.get('saved_model_sha256') != expected_model):
        raise ValueError('Texture experiment differs from currently approved geometry')
    if (review.get('status') != ('supplemental' if _state is not None else 'ready-for-user') or review.get('all_eight_actual_views_inspected') is not True or
            validation.get('geometry_verified') is not True or validation.get('geometry_changed', False)):
        raise ValueError('Texture handoff requires completed geometry and actual-view validation')
    if frames.get('asset_id') != asset_id or config.get('asset_id') != asset_id:
        raise ValueError('Texture frame/worker identity mismatch')
    if frames.get('geometry_revision') != item['revision']['sha256'] or frames.get('input_sha256') != approval['input_sha256']:
        raise ValueError('Texture frame revision/input differs from approved geometry')
    if (sha(experiment/'input.png') != approval['input_sha256'] or
            sha(paths['solid']) != approval['solid_sha256'] or
            sha(paths['source_comparison_secondary']) != validation['generated_sha256']):
        raise ValueError('Texture input or selected fill changed')
    if paths['source_comparison'] != experiment/'input.png':
        raise ValueError('Texture comparison is not the approved experiment input')
    approved_model = Path(frames['source_blend']).resolve(strict=True)
    if sha(approved_model) != expected_model:
        raise ValueError('Approved experiment model differs from geometry approval')
    planar = frames.get('projection_kind') == 'planar-atlas'
    if planar:
        if config['part_ids'] != ['ground'] or validation.get('projection_kind') != 'planar-atlas':
            raise ValueError('Planar ground requires exact ground ownership')
        if validation.get('uv_verified') is not True or validation.get('protected_changes') != 0:
            raise ValueError('Planar handoff must preserve exact UVs and protected pixels')
        qa_path = paths['validation'].parent/'qa-views.json'
        qa = _json(qa_path)
        names = _unique(qa.get('object_names'), 'planar receiver names')
        if len(names) != 1:
            raise ValueError('Planar ground requires one receiver')
        reviewed_frames = Path(frames['reviewed_packet'])/'views.json'
        if sha(reviewed_frames) != validation.get('frame_manifest_sha256'):
            raise ValueError('Planar review cameras changed')
        protected[qa_path] = sha(qa_path); protected[reviewed_frames] = sha(reviewed_frames)
    else:
        if config['part_ids'] == ['ground']:
            raise ValueError('Ground requires the planar texture branch')
        names = _unique(frames.get('object_names'), 'reviewed object names')
        if [v['index'] for v in frames.get('views', [])] != list(range(8)):
            raise ValueError('Texture bake requires eight approved views')
        for path, digest in validation.get('evidence_sha256', {}).items():
            path = Path(path).resolve(strict=True)
            if sha(path) != digest:
                raise ValueError('Guarded bake evidence changed: ' + str(path))
            protected[path] = digest
    preparation_path = experiment/'preparation.json'
    if preparation_path.exists():
        preparation = _json(preparation_path)
        for relative, digest in preparation['files'].items():
            path = (experiment/relative).resolve(strict=True)
            if not path.is_relative_to(experiment):
                raise ValueError('Prepared evidence escapes experiment: ' + relative)
            if sha(path) != digest:
                # A reviewed sampler-only retry retains its original preparation receipt.
                before = dict(frames); before.pop('texture_view_selection', None)
                if (relative != 'views.json' or frames.get('texture_view_selection') != 'best-facing-single' or
                        hashlib.sha256((json.dumps(before, indent=2)+'\n').encode()).hexdigest() != digest or
                        {str(Path(key).resolve()): value for key, value in validation.get('evidence_sha256', {}).items()}.get(str(path)) != sha(path)):
                    raise ValueError('Prepared texture evidence changed: ' + relative)
            protected[path] = sha(path)
    else:
        _derived_packet(experiment, frames, item, protected)
    for relative, digest in review.get('artifact_sha256', {}).items():
        path = (experiment/relative).resolve(strict=True)
        if not path.is_relative_to(experiment) or sha(path) != digest:
            raise ValueError('Reviewed artifact changed: ' + relative)
        protected[path] = digest
    generation_path = paths['source_comparison_secondary'].parent/'generation.json'
    if _json(generation_path).get('changedProtected') != 0:
        raise ValueError('Generated composite changed protected source pixels')
    reference = validation.get('reconciliation_reference')
    if reference and (Path(reference).resolve() != paths['source_trace'] or
                      sha(paths['source_trace']) != validation.get('reconciliation_reference_sha256')):
        raise ValueError('Texture reconciliation reference changed')
    for path in [*all_paths.values(), approval_path, frames_path, config_path,
                 approved_model, generation_path, texture_decisions_path, geometry_manifest]:
        protected[path.resolve()] = sha(path)
    if preparation_path.exists(): protected[preparation_path] = sha(preparation_path)
    geometry_decisions = Path(geometry_decisions).resolve() if geometry_decisions else geometry_manifest.parent/'decisions.json'
    protected[geometry_decisions] = sha(geometry_decisions)
    result = {'asset_id': asset_id, 'blend_path': str(paths['model']), 'blend_sha256': hashes['model'],
            'review_manifest': str(frames_path), 'object_names': names,
            'source_nodes': _unique(config['part_ids'], 'canonical source nodes'),
            'approved_source_blend': str(approved_model), 'workspace': str(workspace),
            'map_name': config['map_name'], 'collection_name': config['collection_name'],
            'scene_name': config['scene_name'], 'projection_kind': 'planar-atlas' if planar else 'multiview',
            'geometry_revision_sha256': item['revision']['sha256'], 'geometry_decision': item['user_decision'],
            'texture_decision': decision, 'geometry_manifest': str(geometry_manifest),
            'geometry_decisions': str(geometry_decisions), 'texture_decisions': str(texture_decisions_path),
            'protected_files': {str(p.resolve()): h for p, h in protected.items()},
            'endpoint_id': endpoint_id, 'review_state': frames.get('review_state', endpoint_id or 'covered'),
            'render_object_names': frames.get('render_object_names') or names}
    if not set(_unique(result['render_object_names'], 'reviewed displayed object names')) <= set(names):
        raise ValueError('Texture display state contains a foreign object')
    if _state is None:
        declared = review.get('texture_states', []) + review.get('material_states', [])
        if {state['id'] for state in declared} != {state['id'] for state in decision.get('texture_states', [])}:
            raise ValueError('Texture approval must bind every declared texture/material state')
        result['texture_states'] = []
        result['material_states'] = []
        for state in decision.get('texture_states', []):
            if state.get('model'):
                child = validate_texture_handoff(geometry_manifest, asset_id, texture_decisions_path,
                                                 geometry_decisions, _state=state['id'])
                declared_state = next(value for value in declared if value['id'] == state['id'])
                if Path(declared_state.get('experiment', '')).is_absolute():
                    declared_experiment = Path(declared_state['experiment']).resolve()
                else:
                    declared_experiment = (experiment/declared_state.get('experiment', '')).resolve()
                if declared_experiment != Path(child['review_manifest']).parent:
                    raise ValueError('Texture state experiment differs from primary approved review')
                child.update(id=state['id'], name=state['name'])
                result['texture_states'].append(child)
                result['protected_files'].update(child['protected_files'])
            else:
                prefix = 'texture_state_' + state['id'] + '_'
                if state['image_fields'] != ['textured'] or state['report_fields'] != ['validation']:
                    raise ValueError('Preserved material state requires exact render and validation evidence')
                check = _json(all_paths[prefix + 'validation'])
                declared_state = next(value for value in declared if value['id'] == state['id'])
                if (declared_state.get('actual_sheet_sha256') != sha(all_paths[prefix + 'textured']) or
                        declared_state.get('validation_sha256') != sha(all_paths[prefix + 'validation'])):
                    raise ValueError('Preserved material state render/report differs from reviewed hashes')
                if check.get('materials_preserved') is not True or check.get('baked_model_sha256') != result['blend_sha256']:
                    raise ValueError('Preserved material state differs from approved baked model')
                result['material_states'].append({'id': state['id'], 'name': state['name'],
                    'textured': str(all_paths[prefix + 'textured']), 'validation': str(all_paths[prefix + 'validation']),
                    'actual_sheet_sha256': sha(all_paths[prefix + 'textured']),
                    'validation_sha256': sha(all_paths[prefix + 'validation'])})
        if item.get('endpoint_reviews') and {result['endpoint_id'], *(s['endpoint_id'] for s in result['texture_states'])} != {'initial', 'applied'}:
            raise ValueError('Both approved texture endpoints are required for publication')
    return result


def validated_imports(geometry_manifest, texture_decisions_path, asset_ids, geometry_decisions=None):
    _unique(asset_ids, 'selected asset IDs')
    return [validate_texture_handoff(geometry_manifest, asset, texture_decisions_path, geometry_decisions)
            for asset in asset_ids]


def verify_baked_geometry(handoff):
    """Open the approved source then bake, compare owned meshes, leave bake open."""
    import bpy
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent/'blender'))
    from refinement_workspace import _geometry
    for path, digest in handoff['protected_files'].items():
        if sha(Path(path)) != digest:
            raise ValueError('Validated texture evidence changed before import: ' + path)
    def snapshot(path):
        bpy.ops.wm.open_mainfile(filepath=str(path))
        bpy.context.window.scene = bpy.data.scenes[handoff['scene_name']]
        bpy.context.view_layer.update()
        objects = [o for o in bpy.data.collections[handoff['collection_name']].all_objects
                   if o.type == 'MESH' and not o.hide_render and o.get('asset_group') == handoff['asset_id']]
        if {o.name for o in objects} != set(handoff['object_names']):
            raise ValueError('Baked worker differs from exact reviewed component names')
        if {o.get('source_node') for o in objects} != set(handoff['source_nodes']):
            raise ValueError('Baked worker differs from canonical source ownership')
        result = {o.name: {'geometry': _geometry(o)} for o in objects}
        if handoff['projection_kind'] == 'planar-atlas':
            for o in objects:
                result[o.name]['uv'] = {l.name: [list(v.uv) for v in l.data] for l in o.data.uv_layers}
        return result
    before = snapshot(handoff['approved_source_blend'])
    after = snapshot(handoff['blend_path'])
    if before != after:
        raise ValueError('Baked worker changed approved geometry, transforms, visibility or planar UVs')
    return {'geometry_verified': True, 'planar_uv_verified': handoff['projection_kind'] == 'planar-atlas',
            'object_names': handoff['object_names'], 'model_sha256': handoff['blend_sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('geometry_manifest', type=Path)
    parser.add_argument('texture_decisions', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('asset_ids', nargs='+')
    parser.add_argument('--geometry-decisions', type=Path)
    args = parser.parse_args()
    imports = validated_imports(args.geometry_manifest, args.texture_decisions, args.asset_ids, args.geometry_decisions)
    if args.output.exists(): raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'version': 1, 'scope': 'approval-validated imports; Blender geometry verification required', 'imports': imports}, indent=2)+'\n')
    print(json.dumps({'imports': len(imports), 'output': str(args.output)}))
