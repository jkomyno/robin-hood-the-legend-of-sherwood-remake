"""Verify a staged revealed material/cover state against the original worker."""
import json
import hashlib
import tempfile
from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_staged_handoffs import snapshot, compare_handoff
from texture_state_roles import partition_texture_states, validate_texture_state_role_evidence
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from asset_scenes import scene_identity
from bundle_publication_states import verify_bundled_reference


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _reference(item):
    if _sha(item['blend_path']) != item['blend_sha256']:
        raise ValueError('Reviewed state model hash changed')
    bpy.ops.wm.open_mainfile(filepath=item['blend_path'])
    if item.get('scene_name'):
        bpy.context.window.scene = bpy.data.scenes[item['scene_name']]
    bpy.context.view_layer.update()
    collection = item['collection_name']
    names = item.get('render_object_names') or item['object_names']
    if not names or len(names) != len(set(names)):
        raise ValueError('Reviewed state names must be nonempty and unique')
    records = snapshot(collection, True, select=lambda obj: obj.name in names)
    if {r['name'] for r in records} != set(names):
        raise ValueError('Reviewed state reference is incomplete')
    if any(r['group'] != item['asset_id'] or r['source'] not in item['source_nodes'] for r in records):
        raise ValueError('Reviewed state reference escapes asset ownership')
    return records


def _patches(obj, key):
    value = obj.get(key, [])
    if hasattr(value, 'to_list'):
        value = value.to_list()
    if (not isinstance(value, (list, tuple)) or len(value) != len(set(value))
            or any(not isinstance(p, str) or not p for p in value)):
        raise ValueError('Invalid patch state visibility: ' + obj.name)
    return set(value)


def activate_reviewed_state(collection, asset_id, applied):
    """Evaluate actual authored visibility, independently of reported bindings."""
    applied = set(applied)
    for obj in list(bpy.data.collections[collection].all_objects):
        if obj.type != 'MESH' or obj.get('asset_group') != asset_id:
            continue
        show = _patches(obj, 'reveal_show_when_applied')
        hide = _patches(obj, 'reveal_hide_when_applied')
        visible = (bool(show & applied) if show else not obj.hide_render) and not bool(hide & applied)
        obj.hide_render = obj.hide_viewport = not visible
        if obj.get('reveal_material_states'):
            from patch_material_export import state_record
            record = state_record(obj)
            slots = record['revealed' if record['patch'] in applied else 'covered']
            for face, slot in zip(obj.data.polygons, slots):
                face.material_index = slot
    bpy.context.view_layer.update()


def verify_reviewed_states(stage, item, bindings, collection):
    """Check both activated compiled states against immutable reviewed workers."""
    children, _standalone = partition_texture_states(item)
    validate_texture_state_role_evidence(item)
    primary_id = item.get('endpoint_id') or 'covered'
    expected = {primary_id: item, **{s['id']: s for s in children}}
    if len(bindings) != len(expected) or {b['id'] for b in bindings} != set(expected):
        raise ValueError('Compiled state coverage differs from reviewed states')
    _reference(item)
    covered_names = set(item.get('render_object_names') or item['object_names'])
    patches_by_state = {primary_id: set()}
    for child in children:
        child_names = set(child.get('render_object_names') or child['object_names'])
        patches = set()
        for name in (covered_names if item.get('endpoint_id') else covered_names - child_names):
            obj = bpy.data.objects[name]
            component_patch = (obj.get('drawbridge_patch_id') or obj.get('native_patch')
                               if item.get('endpoint_id') else obj.get('reveal_component_patch_id'))
            patches.update([component_patch] if component_patch else _patches(obj, 'reveal_patch_ids'))
        if not patches:
            raise ValueError('Reviewed revealed state has no authored patch trigger')
        patches_by_state[child['id']] = patches
    reports = []
    for binding in bindings:
        if set(binding['applied_patches']) != patches_by_state[binding['id']]:
            raise ValueError('Compiled state activation differs from reviewed cover triggers')
        source = expected[binding['id']]
        for declared, key in (('source_blend', 'blend_path'), ('source_blend_sha256', 'blend_sha256'),
                              ('review_manifest', 'review_manifest')):
            if binding[declared] != source[key]:
                raise ValueError('Compiled state is not bound to reviewed evidence: ' + declared)
        reference = _reference(source)
        rows = binding['objects']
        if (len(rows) != len(reference) or {row['source_name'] for row in rows} != {r['name'] for r in reference}
                or len({row['staged_name'] for row in rows}) != len(rows)):
            raise ValueError('Compiled state object mapping is incomplete or duplicated')
        bpy.ops.wm.open_mainfile(filepath=str(Path(stage) / 'worker.blend'))
        for row in rows:
            obj = bpy.data.objects.get(row['staged_name'])
            if obj is None or obj.get('asset_group') != item['asset_id']:
                raise ValueError('Compiled state references absent or foreign object')
            if (_patches(obj, 'reveal_show_when_applied') != set(row['show_patches'])
                    or _patches(obj, 'reveal_hide_when_applied') != set(row['hide_patches'])):
                raise ValueError('Compiled visibility differs from state binding')
        activate_reviewed_state(collection, item['asset_id'], binding['applied_patches'])
        actual = snapshot(collection, True, select=lambda obj:
                          obj.get('asset_group') == item['asset_id'] and not obj.hide_render)
        if {r['name'] for r in actual} != {row['staged_name'] for row in rows}:
            raise ValueError('Activated state exposes missing or unreviewed meshes: ' + item['asset_id']
                             + ' expected=' + repr(sorted(row['staged_name'] for row in rows))
                             + ' actual=' + repr(sorted(r['name'] for r in actual)))
        drift = compare_handoff(reference, actual, reviewed_state=True)
        reports.append({'asset_id': item['asset_id'], 'id': binding['id'], 'status': 'PASS',
                        'source_blend_sha256': source['blend_sha256'], 'meshes': len(actual),
                        'reviewed_source_nodes': sorted({r['source'] for r in reference}),
                        'applied_patches': binding['applied_patches'],
                        'maximum_world_coordinate_drift': drift,
                        'comparison': 'Exact topology, assigned material graphs, packed image bytes and every UV layer; independently activated visible mesh inventory.'})
    return reports


def verify_inactive_states(stage, item, bindings, collection):
    """Account only for canonical parts absent from both active map appearances."""
    children, endpoints = partition_texture_states(item)
    references = [_reference(source) for source in [item, *children]]
    active_sources = {row['source'] for reference in references for row in reference}
    missing = set(item['source_nodes']) - active_sources
    if not missing and not bindings:
        return []
    if not endpoints or {row['source_node'] for row in bindings} != missing:
        raise ValueError('Inactive canonical inventory is not the exact missing reviewed subset')
    initial = endpoints['initial']
    wanted = [row for row in _reference(initial) if row['source'] in missing]
    if len(bindings) != len(wanted) or {row['source_name'] for row in bindings} != {row['name'] for row in wanted}:
        raise ValueError('Inactive bindings differ from exact reviewed initial components')
    for row in bindings:
        if (row['source_blend'], row['source_blend_sha256'], row['reviewed_state_id']) != (initial['blend_path'], initial['blend_sha256'], initial['id']):
            raise ValueError('Inactive binding substituted another endpoint')
    bpy.ops.wm.open_mainfile(filepath=str(Path(stage) / 'worker.blend'))
    objects = [obj for obj in bpy.data.collections[collection].all_objects
               if obj.type == 'MESH' and obj.get('asset_group') == item['asset_id'] and obj.get('publication_inactive')]
    if {obj.name for obj in objects} != {row['staged_name'] for row in bindings}:
        raise ValueError('Inactive staged inventory differs from proof')
    forbidden = ('native_patch', 'drawbridge_patch_id', 'reveal_show_when_applied', 'reveal_hide_when_applied',
                 'reveal_patch_ids', 'reveal_component_patch_id', 'reveal_material_states')
    if any(not obj.hide_render or not obj.hide_viewport or any(obj.get(key) for key in forbidden) for obj in objects):
        raise ValueError('Inactive canonical part is visible or has runtime activation')
    names = {obj.name for obj in objects}
    try:
        for obj in objects:
            obj.hide_viewport = False
        bpy.context.view_layer.update()
        actual = snapshot(collection, True, select=lambda obj: obj.name in names)
        drift = compare_handoff(wanted, actual, reviewed_state=True)
    finally:
        for obj in objects:
            obj.hide_viewport = True
        bpy.context.view_layer.update()
    return [{'asset_id': item['asset_id'], 'status': 'PASS', 'meshes': len(actual),
             'source_nodes': sorted(missing), 'source_blend_sha256': initial['blend_sha256'],
             'maximum_world_coordinate_drift': drift, 'inactive_object_names': sorted(names)}]


def verify_static_variants(plan, stage):
    """Verify independent endpoint workers as well as their exported file binding."""
    reports = []
    expected = {(entry['asset_id'], state): item for entry in plan.get('static_variants', [])
                for state, item in entry['states'].items()}
    appearances = {}
    for parent in plan['imports']:
        _, endpoints = partition_texture_states(parent)
        validate_texture_state_role_evidence(parent)
        appearances.update({(parent['asset_id'], state): child for state, child in endpoints.items()})
    if set(expected) & set(appearances):
        raise ValueError('Static and appearance endpoint identities overlap')
    expected.update(appearances)
    actual = {(r['asset_id'], r['state']): r for r in stage.get('static_variants', [])}
    if len(actual) != len(stage.get('static_variants', [])) or set(actual) != set(expected):
        raise ValueError('Static endpoint coverage differs from publication plan')
    for item in plan['imports']:
        endpoint_states = {s['endpoint_id'] for s in item.get('texture_states', []) if s.get('endpoint_id')}
        if item.get('endpoint_id'):
            endpoint_states.add(item['endpoint_id'])
        if endpoint_states != {state for asset, state in expected if asset == item['asset_id'] and (asset, state) not in appearances}:
            raise ValueError('Approved secondary endpoint was not exported: ' + item['asset_id'])
    for (asset_id, state), source in expected.items():
        report = actual[(asset_id, state)]
        approved = next(item for item in plan['imports'] if item['asset_id'] == asset_id)
        child = appearances.get((asset_id, state)) or (approved if approved.get('endpoint_id') == state else
                 next((s for s in approved.get('texture_states', []) if s.get('endpoint_id') == state), None))
        if child is None or (source['blend_path'], source['blend_sha256']) != (child['blend_path'], child['blend_sha256']):
            raise ValueError('Static variant substituted an unreviewed endpoint')
        reference = _reference(child)
        if (report['source_blend'], report['source_blend_sha256']) != (source['blend_path'], source['blend_sha256']):
            raise ValueError('Static endpoint source binding changed')
        if _sha(report['worker']) != report['worker_sha256'] or _sha(report['model']) != report['model_sha256']:
            raise ValueError('Static endpoint worker or exported model changed')
        bpy.ops.wm.open_mainfile(filepath=report['worker'])
        records = snapshot(plan['collection_name'], True, select=lambda obj:
                           obj.get('asset_group') == asset_id and not obj.hide_render)
        drift = compare_handoff(reference, records, reviewed_state=True)
        # Re-export the verified endpoint worker, rather than trusting a model
        # hash emitted by the staging code as proof of its actual contents.
        from export_editor import export_asset_library, exported_pivot
        descriptor = json.loads((Path(plan['output']) / 'assets' / asset_id / 'asset.json').read_text())
        variant = (descriptor.get('standalone_variants') or descriptor.get('state_variants') or {}).get(state)
        if (asset_id, state) in appearances:
            if not variant or Path(report['model']).name != variant['model'] or scene_identity(variant) == scene_identity(descriptor):
                raise ValueError('Isolated appearance descriptor binding changed')
        proof_parent = Path(plan['output']) / 'verification-exports' / asset_id
        proof_parent.mkdir(parents=True, exist_ok=True)
        proof_output = Path(tempfile.mkdtemp(prefix=state + '-', dir=proof_parent))
        export_asset_library(plan['map_name'], proof_output, plan['hackable_map'], asset_ids=[asset_id],
                             standalone_pivots={asset_id: exported_pivot(Path(plan['output'])/'assets', asset_id)})
        if (asset_id, state) in appearances:
            reference_descriptor = json.loads((proof_output / asset_id / 'asset.json').read_text())
            if any(variant.get(key) != reference_descriptor[key] for key in ('parts', 'components')):
                raise ValueError('Isolated appearance descriptor inventory differs from reviewed worker')
        reference_model = proof_output / asset_id / 'model.glb'
        if report.get('model_scene') is not None:
            if variant.get('model_scene') != report['model_scene']:
                raise ValueError('Bundled endpoint descriptor selects a different scene')
            verify_bundled_reference(report, reference_model)
        elif _sha(reference_model) != report['model_sha256']:
            raise ValueError('Static endpoint exported bytes differ from verified reviewed worker: ' + asset_id)
        reports.append({'asset_id': asset_id, 'state': state, 'status': 'PASS',
                        'meshes': len(records), 'maximum_world_coordinate_drift': drift,
                        'reviewed_source_nodes': sorted({r['source'] for r in reference}),
                        'reviewed_source_blend_sha256': child['blend_sha256'],
                        'reviewed_worker_reexport_matches': True,
                        'reference_export': str(reference_model),
                        'worker_sha256': report['worker_sha256'], 'model_sha256': report['model_sha256'],
                        **({'model_scene': report['model_scene'], 'original_model_sha256': report['original_model_sha256'],
                            'bundle_receipt_sha256': report['bundle_receipt_sha256']} if report.get('model_scene') is not None else {})})
    return reports


def verify(stage,handoff_path):
    handoff=json.loads(Path(handoff_path).read_text())
    collection=json.loads(Path(handoff['review_manifest']).read_text())['collection_name']
    group=handoff['asset_id'];patch=handoff['state_trigger']
    bpy.ops.wm.open_mainfile(filepath=handoff['revealed_worker'])
    reference=[r for r in snapshot(collection,True) if r['group']==group and not r['hidden']]
    if not reference:raise ValueError('Empty revealed reference')
    bpy.ops.wm.open_mainfile(filepath=str(Path(stage)/'worker.blend'))
    for obj in bpy.data.collections[collection].all_objects:
        if obj.get('asset_group')!=group or obj.type!='MESH':continue
        if obj.get('reveal_material_states'):
            record=json.loads(obj['reveal_material_states'])
            if record['patch']==patch:
                for face,slot in zip(obj.data.polygons,record['revealed']):face.material_index=slot
        if patch in obj.get('reveal_hide_when_applied',[]):obj.hide_render=True
    actual=[r for r in snapshot(collection,True) if r['group']==group and not r['hidden']]
    drift=compare_handoff(reference,actual)
    result={'status':'PASS','revealed_meshes':len(actual),'maximum_world_coordinate_drift':drift,
            'appearance':'Exact material graphs, assigned atlas bytes, UVs, topology and visibility'}
    (Path(stage)/'revealed-handoff-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':verify(*sys.argv[sys.argv.index('--')+1:])
