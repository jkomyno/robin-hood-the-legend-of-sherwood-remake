"""Export complete reviewed appearances without replacing the covered model."""
import hashlib
import json
from pathlib import Path
import bpy
from export_editor import export_asset_library
from supplemental_parts import clean_static_metadata
from texture_state_roles import partition_texture_states, validate_texture_state_role_evidence


def export_appearance_variants(plan, output):
    reports = []
    for parent in plan['imports']:
        _, endpoints = partition_texture_states(parent)
        if not endpoints:
            continue
        validate_texture_state_role_evidence(parent)
        asset_id = parent['asset_id']
        destination = output / 'assets' / asset_id
        descriptor_path = destination / 'asset.json'
        descriptor = json.loads(descriptor_path.read_text())
        covered_hash = hashlib.sha256((destination / descriptor['model']).read_bytes()).hexdigest()
        variants = {}
        for state, item in endpoints.items():
            source = Path(item['blend_path'])
            if hashlib.sha256(source.read_bytes()).hexdigest() != item['blend_sha256']:
                raise ValueError('Reviewed appearance worker changed')
            bpy.ops.wm.open_mainfile(filepath=str(source))
            bpy.context.window.scene = bpy.data.scenes[item['scene_name']]
            displayed = set(item.get('render_object_names') or item['object_names'])
            active = []
            for obj in list(bpy.data.collections[plan['collection_name']].all_objects):
                if obj.type == 'MESH' and obj.get('asset_group') == asset_id:
                    obj.hide_render = obj.name not in displayed
                    if not obj.hide_render:
                        active.append(obj)
            if {obj.name for obj in active} != displayed:
                raise ValueError('Reviewed appearance inventory differs')
            clean_static_metadata(active)
            for obj in active:
                for key in ('native_patch', 'native_patch_preview', 'drawbridge_patch_id',
                            'reveal_hide_when_applied', 'reveal_show_when_applied', 'reveal_patch_ids',
                            'reveal_component_patch_id', 'reveal_material_states', 'reveal_material_patch',
                            'reveal_material_state'):
                    if key in obj:
                        del obj[key]
            variant_output = output / 'variant-staging' / asset_id / ('appearance-' + state)
            variant_output.mkdir(parents=True, exist_ok=False)
            worker = variant_output / 'worker.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(worker))
            export_asset_library(plan['map_name'], variant_output, plan['hackable_map'], asset_ids=[asset_id],
                                 standalone_pivots={asset_id: descriptor['source_origin_scene']})
            alternative = json.loads((variant_output / asset_id / 'asset.json').read_text())
            if alternative['source_origin_scene'] != descriptor['source_origin_scene']:
                raise ValueError('Appearance pivot drift')
            model_name = 'model-door-' + state + '.glb'
            (variant_output / asset_id / 'model.glb').replace(destination / model_name)
            variants[state] = {'name': 'Door ' + state, 'model': model_name,
                               'parts': alternative['parts'], 'components': alternative['components']}
            reports.append({'asset_id': asset_id, 'state': state, 'appearance_variant': True,
                            'source_blend': str(source), 'source_blend_sha256': item['blend_sha256'],
                            'worker': str(worker), 'worker_sha256': hashlib.sha256(worker.read_bytes()).hexdigest(),
                            'model': str(destination / model_name),
                            'model_sha256': hashlib.sha256((destination / model_name).read_bytes()).hexdigest()})
        descriptor['standalone_variants'] = variants
        descriptor['state_usage'] = 'Covered is the default map and library appearance. Map patches select the reviewed revealed appearance. Door initial/applied are complete isolated library appearances; no independent map door animation is validated.'
        if hashlib.sha256((destination / descriptor['model']).read_bytes()).hexdigest() != covered_hash:
            raise ValueError('Covered default model changed during appearance export')
        descriptor_path.write_text(json.dumps(descriptor, indent=2) + '\n')
        bpy.ops.wm.open_mainfile(filepath=str(output / 'worker.blend'))
    return reports
