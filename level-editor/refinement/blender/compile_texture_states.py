"""Compile exact reviewed appearance states into patch-controlled mesh children.

Workers remain immutable. Copies preserve per-state UVs, materials and surfaces;
shared identical surfaces are reused. Canonical source-node ownership is unchanged.
"""
import hashlib
import json
from pathlib import Path
import bpy
from mathutils import Matrix
from verify_staged_handoffs import snapshot
from texture_state_roles import partition_texture_states, validate_texture_state_role_evidence


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _names(item):
    return item.get('render_object_names') or item['object_names']


def _capture(item):
    if _sha(item['blend_path']) != item['blend_sha256']:
        raise ValueError('Reviewed state worker changed')
    bpy.ops.wm.open_mainfile(filepath=item['blend_path'])
    bpy.context.window.scene = bpy.data.scenes[item['scene_name']]
    bpy.context.view_layer.update()
    names = set(_names(item))
    records = {r['name']: r for r in snapshot(item['collection_name'], True,
               select=lambda o: o.name in names)}
    if set(records) != names:
        raise ValueError('Reviewed state objects are absent')
    for record in records.values():
        if record['group'] != item['asset_id'] or record['source'] not in item['source_nodes']:
            raise ValueError('Reviewed state escapes asset ownership')
        record['triggers'] = _triggers(bpy.data.objects[record['name']])
        record['world_matrix'] = [list(row) for row in bpy.data.objects[record['name']].matrix_world]
        record['value'].pop('patch_state', None)
        record['value'].pop('visibility', None)
    return records


def _triggers(obj):
    patch = obj.get('drawbridge_patch_id') or obj.get('reveal_component_patch_id')
    if patch:
        return [patch]
    return list(obj.get('reveal_patch_ids', []))


def compile_states(item, output):
    children, standalone = partition_texture_states(item)
    validate_texture_state_role_evidence(item)
    if not children:
        return None
    child = children[0]
    covered_records = _capture(item)
    revealed_records = _capture(child)
    covered_names, revealed_names = set(covered_records), set(revealed_records)
    missing_sources = set(item['source_nodes']) - {record['source'] for record in [*covered_records.values(), *revealed_records.values()]}
    dormant_records = {}
    if missing_sources:
        if not standalone:
            raise ValueError('Reviewed map appearances omit canonical source parts')
        initial_records = _capture(standalone['initial'])
        dormant_records = {name: record for name, record in initial_records.items() if record['source'] in missing_sources}
        if {record['source'] for record in dormant_records.values()} != missing_sources:
            raise ValueError('Missing canonical parts are not present in reviewed initial endpoint')
    # Patch membership is explicit authored component metadata, never sight geometry.
    patches = sorted({patch for name in covered_names - revealed_names
                      for patch in covered_records[name]['triggers']})
    if not patches:
        raise ValueError('Revealed appearance lacks explicit reviewed cover patch triggers')
    bpy.ops.wm.open_mainfile(filepath=item['blend_path'])
    bpy.context.window.scene = bpy.data.scenes[item['scene_name']]
    collection = bpy.data.collections[item['collection_name']]
    original = {name: bpy.data.objects[name] for name in covered_names}
    bindings = [{'id': item.get('endpoint_id') or 'covered', 'source_blend': item['blend_path'],
                 'source_blend_sha256': item['blend_sha256'], 'review_manifest': item['review_manifest'],
                 'applied_patches': [], 'objects': []},
                {'id': child['id'], 'source_blend': child['blend_path'],
                 'source_blend_sha256': child['blend_sha256'], 'review_manifest': child['review_manifest'],
                 'applied_patches': patches, 'objects': []}]
    identical = {name for name in covered_names & revealed_names
                 if covered_records[name]['value'] == revealed_records[name]['value']}
    load_names = sorted(revealed_names - identical)
    before = set(bpy.data.objects)
    with bpy.data.libraries.load(child['blend_path'], link=False) as (src, dst):
        dst.objects = list(load_names)
    loaded = dict(zip(load_names, dst.objects))
    temporary = bpy.data.collections.new('Reviewed state transform capture')
    bpy.context.scene.collection.children.link(temporary)
    for obj in set(bpy.data.objects) - before:
        temporary.objects.link(obj)
    bpy.context.view_layer.update()
    for name, obj in loaded.items():
        world = obj.matrix_world.copy()
        obj.parent = original[name].parent if name in original else next(iter(original.values())).parent
        obj.matrix_world = world
        obj.name = name + ' / reviewed revealed texture'
        collection.objects.link(obj)
    bpy.context.view_layer.update()
    keep = set(loaded.values())
    bpy.data.collections.remove(temporary)
    for obj in set(bpy.data.objects) - before - keep:
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()
    for name, obj in original.items():
        hide = list(obj.get('reveal_hide_when_applied', [])) if name in identical else (_triggers(obj) or patches)
        if hide:
            obj['reveal_hide_when_applied'] = hide
        obj.hide_render = obj.hide_viewport = False
        bindings[0]['objects'].append({'source_name': name, 'staged_name': obj.name,
                                       'show_patches': list(obj.get('reveal_show_when_applied', [])), 'hide_patches': hide})
    for name in sorted(revealed_names):
        obj = original[name] if name in identical else loaded[name]
        show = list(obj.get('reveal_show_when_applied', [])) if name in identical else (_triggers(obj) or patches)
        if show:
            obj['reveal_show_when_applied'] = show
            if 'reveal_hide_when_applied' in obj:
                del obj['reveal_hide_when_applied']
        obj.hide_render = obj.hide_viewport = False
        bindings[1]['objects'].append({'source_name': name, 'staged_name': obj.name,
                                       'show_patches': show, 'hide_patches': list(obj.get('reveal_hide_when_applied', []))})
    names = sorted({row['staged_name'] for state in bindings for row in state['objects']})
    # Neutral review workers can retain extra visible state peers outside the
    # reviewed display inventory. They remain provenance only, never active.
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.get('asset_group') == item['asset_id'] and obj.name not in names:
            obj.hide_render = obj.hide_viewport = True
    inactive_bindings = []
    if dormant_records:
        before_dormant = set(bpy.data.objects)
        initial = standalone['initial']
        with bpy.data.libraries.load(initial['blend_path'], link=False) as (src, dst):
            dst.objects = sorted(dormant_records)
        dormant_loaded = dict(zip(sorted(dormant_records), dst.objects))
        temporary = bpy.data.collections.new('Reviewed inactive transform capture')
        bpy.context.scene.collection.children.link(temporary)
        for obj in set(bpy.data.objects) - before_dormant:
            temporary.objects.link(obj)
        bpy.context.view_layer.update()
        for source_name, obj in dormant_loaded.items():
            world = Matrix(dormant_records[source_name]['world_matrix'])
            obj.parent = next(iter(original.values())).parent
            obj.matrix_world = world
            obj.name = source_name + ' / reviewed inactive endpoint'
            collection.objects.link(obj)
            for key in ('native_patch', 'native_patch_preview', 'drawbridge_patch_id',
                        'drawbridge_hinge_matrix', 'drawbridge_pose_angles_degrees', 'drawbridge_pose',
                        'reveal_hide_when_applied', 'reveal_show_when_applied', 'reveal_patch_ids',
                        'reveal_component_patch_id', 'reveal_material_states', 'reveal_material_patch',
                        'reveal_material_state'):
                if key in obj:
                    del obj[key]
            obj['publication_inactive'] = True
            obj.hide_render = obj.hide_viewport = False
            inactive_bindings.append({'staged_name': obj.name, 'source_name': source_name,
                                      'source_node': dormant_records[source_name]['source'],
                                      'source_blend': initial['blend_path'], 'source_blend_sha256': initial['blend_sha256'],
                                      'reviewed_state_id': initial['id']})
        bpy.context.view_layer.update()
        keep_dormant = set(dormant_loaded.values())
        bpy.data.collections.remove(temporary)
        for obj in set(bpy.data.objects) - before_dormant - keep_dormant:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.context.view_layer.update()
        for obj in keep_dormant:
            obj.hide_render = obj.hide_viewport = True
        names = sorted([*names, *(obj.name for obj in keep_dormant)])
    path = Path(output).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    result = {'blend_path': str(path), 'blend_sha256': _sha(path), 'object_names': names,
              'state_bindings': bindings, 'inactive_object_bindings': inactive_bindings, 'shared_identical_objects': sorted(identical),
              'state_note': 'Only covered and combined revealed endpoints were reviewed; partial patch combinations were not separately reviewed.'}
    if standalone:
        result['standalone_texture_states'] = {key: {'id': value['id'], 'blend_path': value['blend_path'],
            'blend_sha256': value['blend_sha256'], 'review_manifest': value['review_manifest']} for key, value in standalone.items()}
        result['state_note'] += ' Separate door endpoint appearances are isolated library variants, not additional simultaneous map meshes.'
    path.with_suffix('.states.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
