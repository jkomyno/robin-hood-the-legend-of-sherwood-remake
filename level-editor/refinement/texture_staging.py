"""Validate explicit texture approvals and select their exact baked workers.

This produces guarded import metadata, never publishes or changes a worker.
Blender callers must also run verify_baked_geometry before importing/exporting.
"""
import argparse
import hashlib
import json
from pathlib import Path
from review_evidence import sha
from texture_decisions import IMAGE_FIELDS, evidence


def _json(path):
    return json.loads(Path(path).read_text())


def _unique(values, label):
    if (not isinstance(values, list) or not values or
            any(not isinstance(v, str) or not v for v in values) or len(set(values)) != len(values)):
        raise ValueError('Expected exact unique ' + label)
    return values


def validate_texture_handoff(geometry_manifest, asset_id, texture_decisions_path, geometry_decisions=None):
    from stage_approved_editor_asset import validate
    geometry_manifest = Path(geometry_manifest).resolve(strict=True)
    texture_decisions_path = Path(texture_decisions_path).resolve(strict=True)
    item, workspace, protected = validate(geometry_manifest, asset_id, geometry_decisions)
    if item.get('endpoint_reviews'):
        raise ValueError('Paired texture endpoints require separate approved endpoint handoffs')
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
    record = {'id': asset_id, **{key: str(paths[key]) for key in (*IMAGE_FIELDS, 'validation', 'review')}}
    current_paths, hashes = evidence(record)
    if hashes != decision.get('evidence_sha256') or any(current_paths[k].resolve() != paths[k] for k in current_paths):
        raise ValueError('Texture decision differs from current baked evidence')
    binding = {'images': {key: hashes[key] for key in IMAGE_FIELDS},
               'reports': {key: hashes[key] for key in ('validation', 'review')}}
    if hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest() != decision['review_revision']:
        raise ValueError('Texture gallery revision does not match displayed evidence')
    experiment = paths['solid'].parent
    approval_path, frames_path = experiment/'approval.json', experiment/'views.json'
    approval, frames = _json(approval_path), _json(frames_path)
    review, validation = _json(paths['review']), _json(paths['validation'])
    config_path = workspace/'workspace.json'; config = _json(config_path)
    if (approval.get('status') != 'approved' or approval.get('approved_by') != 'user' or
            approval.get('asset_id') != asset_id or approval.get('geometry_revision') != item['revision']['sha256'] or
            approval.get('saved_model_sha256') != item['revision']['model_sha256']):
        raise ValueError('Texture experiment differs from currently approved geometry')
    if (review.get('status') != 'ready-for-user' or review.get('all_eight_actual_views_inspected') is not True or
            validation.get('geometry_verified') is not True or validation.get('geometry_changed', False)):
        raise ValueError('Texture handoff requires completed geometry and actual-view validation')
    if frames.get('asset_id') != asset_id or config.get('asset_id') != asset_id:
        raise ValueError('Texture frame/worker identity mismatch')
    if (sha(experiment/'input.png') != approval['input_sha256'] or
            sha(paths['solid']) != approval['solid_sha256'] or
            sha(paths['source_comparison_secondary']) != validation['generated_sha256']):
        raise ValueError('Texture input or selected fill changed')
    if paths['source_comparison'] != experiment/'input.png':
        raise ValueError('Texture comparison is not the approved experiment input')
    approved_model = Path(frames['source_blend']).resolve(strict=True)
    if sha(approved_model) != item['revision']['model_sha256']:
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
    preparation_path = experiment/'preparation.json'; preparation = _json(preparation_path)
    for relative, digest in preparation['files'].items():
        path = (experiment/relative).resolve(strict=True)
        if not path.is_relative_to(experiment) or sha(path) != digest:
            raise ValueError('Prepared texture evidence changed: ' + relative)
        protected[path] = digest
    generation_path = paths['source_comparison_secondary'].parent/'generation.json'
    if _json(generation_path).get('changedProtected') != 0:
        raise ValueError('Generated composite changed protected source pixels')
    reference = validation.get('reconciliation_reference')
    if reference and (Path(reference).resolve() != paths['source_trace'] or
                      sha(paths['source_trace']) != validation.get('reconciliation_reference_sha256')):
        raise ValueError('Texture reconciliation reference changed')
    for path in [*paths.values(), approval_path, frames_path, preparation_path, config_path,
                 approved_model, generation_path, texture_decisions_path, geometry_manifest]:
        protected[path.resolve()] = sha(path)
    geometry_decisions = Path(geometry_decisions).resolve() if geometry_decisions else geometry_manifest.parent/'decisions.json'
    protected[geometry_decisions] = sha(geometry_decisions)
    return {'asset_id': asset_id, 'blend_path': str(paths['model']), 'blend_sha256': hashes['model'],
            'review_manifest': str(frames_path), 'object_names': names,
            'source_nodes': _unique(config['part_ids'], 'canonical source nodes'),
            'approved_source_blend': str(approved_model), 'workspace': str(workspace),
            'map_name': config['map_name'], 'collection_name': config['collection_name'],
            'scene_name': config['scene_name'], 'projection_kind': 'planar-atlas' if planar else 'multiview',
            'geometry_revision_sha256': item['revision']['sha256'], 'geometry_decision': item['user_decision'],
            'texture_decision': decision, 'geometry_manifest': str(geometry_manifest),
            'geometry_decisions': str(geometry_decisions), 'texture_decisions': str(texture_decisions_path),
            'protected_files': {str(p.resolve()): h for p, h in protected.items()}}


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
