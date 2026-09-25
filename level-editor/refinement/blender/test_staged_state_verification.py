"""Blender regression: staged alternatives must match both reviewed appearances."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compile_texture_states import compile_states
from verify_staged_handoffs import verify
from verify_staged_patch_state import verify_reviewed_states, verify_static_variants, _sha


def fixture_worker(path, revealed):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    collection = bpy.data.collections.new('Fixture Working')
    bpy.context.scene.collection.children.link(collection)
    for name, z in [('Body', 0), ('Cover', 2), ('Outside', 5)]:
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(0, 0, z), (4, 0, z), (0, 4, z)], [], [(0, 1, 2)])
        mesh.uv_layers.new(name='Reviewed UV')
        for entry, uv in zip(mesh.uv_layers[0].data, [(0, 0), (1, 0), (0, 1)]):
            entry.uv = (uv[0] * (.8 if revealed and name == 'Body' else 1), uv[1])
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        obj['asset_group'] = 'other' if name == 'Outside' else 'house'
        obj['asset_name'] = 'Fixture house'
        obj['part_name'] = name
        obj['source_node'] = 'building-002' if name == 'Outside' else 'building-001'
        material = bpy.data.materials.new(name)
        material.diffuse_color = (.8 if revealed and name == 'Body' else .2, .4, .6, 1)
        obj.data.materials.append(material)
        if name == 'Cover':
            obj['reveal_component_patch_id'] = 'patch-001'
            obj.hide_render = obj.hide_viewport = revealed
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    frame = path.with_suffix('.json')
    frame.write_text(json.dumps({'collection_name': collection.name}))
    return {'asset_id': 'house', 'blend_path': str(path), 'blend_sha256': _sha(path),
            'review_manifest': str(frame), 'collection_name': collection.name,
            'scene_name': bpy.context.scene.name, 'source_nodes': ['building-001'],
            'object_names': ['Body', 'Cover'], 'render_object_names': ['Body'] if revealed else ['Body', 'Cover'],
            'endpoint_id': None}


def check():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        primary = fixture_worker(root / 'covered.blend', False)
        child = fixture_worker(root / 'revealed.blend', True)
        child['id'] = 'revealed'
        primary['texture_states'] = [child]
        compiled = compile_states(primary, root / 'compiled.blend')
        stage = root / 'stage'
        stage.mkdir()
        shutil.copyfile(compiled['blend_path'], stage / 'worker.blend')
        bindings = compiled['state_bindings']
        result = verify_reviewed_states(stage, primary, bindings, 'Fixture Working')
        assert len(result) == 2 and all(r['status'] == 'PASS' for r in result)
        plan = {'imports': [primary], 'baseline': primary['blend_path'],
                'collection_name': 'Fixture Working', 'output': str(stage)}
        plan_path = root / 'plan.json'
        plan_path.write_text(json.dumps(plan))
        (stage / 'stage.json').write_text(json.dumps({'imports': [{'asset_id': 'house', 'state_bindings': bindings}]}))
        verify(plan_path)
        for mutation in ('uv', 'geometry', 'material', 'visibility', 'outside'):
            shutil.copyfile(compiled['blend_path'], stage / 'worker.blend')
            bpy.ops.wm.open_mainfile(filepath=str(stage / 'worker.blend'))
            obj = bpy.data.objects[bindings[1]['objects'][0]['staged_name']]
            if mutation == 'uv':
                obj.data.uv_layers[0].data[0].uv.x += .2
            elif mutation == 'geometry':
                obj.data.vertices[0].co.x += .2
            elif mutation == 'material':
                obj.data.materials[0].diffuse_color[0] += .1
            elif mutation == 'visibility':
                obj['reveal_show_when_applied'] = ['wrong-patch']
            else:
                bpy.data.objects['Outside'].data.vertices[0].co.x += .2
            bpy.ops.wm.save_as_mainfile(filepath=str(stage / 'worker.blend'))
            try:
                verify(plan_path)
            except ValueError:
                pass
            else:
                raise AssertionError('Accepted changed ' + mutation)
        print('PASS: both reviewed states, exact UV/material/geometry, authored visibility, outside preservation and five tamper rejections')
        from export_editor import export_asset_library
        level = root / 'level.json'
        level.write_text(json.dumps({'sight_obstacles': [
            {'points': [{'x': 0, 'y': 0, 'z_bottom': 0, 'z_top': 2}]} for _ in range(3)]}))
        bpy.ops.wm.open_mainfile(filepath=primary['blend_path'])
        export_asset_library('Fixture', stage / 'assets', level, asset_ids=['house'])
        descriptor = json.loads((stage / 'assets/house/asset.json').read_text())
        bpy.ops.wm.open_mainfile(filepath=child['blend_path'])
        variant_worker = stage / 'applied.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(variant_worker))
        export_asset_library('Fixture', stage / 'applied-export', level, asset_ids=['house'],
                             standalone_pivots={'house': descriptor['source_origin_scene']})
        variant_model = stage / 'applied-export/house/model.glb'
        child['endpoint_id'] = child['id'] = 'applied'
        plan.update(map_name='Fixture', hackable_map=str(level), static_variants=[{
            'asset_id': 'house', 'states': {'applied': child}}])
        state_report = {'static_variants': [{'asset_id': 'house', 'state': 'applied',
            'source_blend': child['blend_path'], 'source_blend_sha256': child['blend_sha256'],
            'worker': str(variant_worker), 'worker_sha256': _sha(variant_worker),
            'model': str(variant_model), 'model_sha256': _sha(variant_model)}]}
        assert verify_static_variants(plan, state_report)[0]['reviewed_worker_reexport_matches']
        # A correctly hashed but wrong endpoint export must not pass on metadata alone.
        shutil.copyfile(stage / 'assets/house/model.glb', variant_model)
        state_report['static_variants'][0]['model_sha256'] = _sha(variant_model)
        try:
            verify_static_variants(plan, state_report)
        except ValueError:
            pass
        else:
            raise AssertionError('Accepted a correctly hashed export of the wrong endpoint')
        print('PASS: applied endpoint reviewed worker and exact re-export; wrong endpoint payload rejected')
        # Three independently reviewed children must not become three OR-triggered map layers.
        initial = fixture_worker(root / 'door-initial.blend', True)
        applied = fixture_worker(root / 'door-applied.blend', True)
        initial['id'], applied['id'] = 'door-initial', 'door-applied'
        child['id'], child['endpoint_id'] = 'revealed', None
        primary['texture_states'] = [child, initial, applied]
        primary['texture_state_roles'] = {'revealed': 'map-reveal', 'door-initial': 'standalone-initial', 'door-applied': 'standalone-applied'}
        packet_records = []
        for state, endpoint in [('initial', initial), ('applied', applied)]:
            packet = str(root / ('packet-' + state))
            Path(endpoint['review_manifest']).write_text(json.dumps({'collection_name': 'Fixture Working', 'reviewed_packet': packet, 'source_sha256': state}))
            packet_records.append({'path': packet, 'source_sha256': state, 'object_names': endpoint['render_object_names']})
        states = root / 'states.json'
        states.write_text(json.dumps({'asset_id': 'house', 'states': packet_records}))
        primary['texture_state_role_evidence'] = {'states_json': str(states), 'states_sha256': _sha(states)}
        compiled_pair = compile_states(primary, root / 'compiled-three.blend')
        assert [binding['id'] for binding in compiled_pair['state_bindings']] == ['covered', 'revealed']
        shutil.copyfile(compiled_pair['blend_path'], stage / 'worker.blend')
        assert len(verify_reviewed_states(stage, primary, compiled_pair['state_bindings'], 'Fixture Working')) == 2
        from export_appearance_variants import export_appearance_variants
        plan.update(imports=[primary], static_variants=[])
        reports = export_appearance_variants(plan, stage)
        assert len(verify_static_variants(plan, {'static_variants': reports})) == 2
        descriptor = json.loads((stage / 'assets/house/asset.json').read_text())
        assert descriptor['model'] == 'model.glb' and set(descriptor['standalone_variants']) == {'initial', 'applied'}
        print('PASS: three-child prison roles retain two map appearances and exact separate door exports')



if __name__ == '__main__':
    check()
