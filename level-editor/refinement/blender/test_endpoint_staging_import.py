"""Synthetic Blender workers: exact imports, common pivot and hidden endpoint."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from endpoint_staging import import_endpoint_objects
from review_evidence import sha
from export_editor import export_asset_library, exported_pivot


def check():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        plan = {'asset_id': 'bridge', 'states': {}, 'protected_files': {},
                'standalone_pivot': [17., 23., 3.]}
        for state, name, node, offset in [('initial', 'Raised', 'building-001', 0),
                                         ('applied', 'Lowered', 'building-002', 10)]:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            collection = bpy.data.collections.new('Fixture Working')
            bpy.context.scene.collection.children.link(collection)
            parent = bpy.data.objects.new('Transform parent', None)
            collection.objects.link(parent)
            parent.location = (10, 20, 2)
            for label, hidden, shift in [(name, False, offset), ('Stale sibling', True, 500)]:
                mesh = bpy.data.meshes.new(label)
                mesh.from_pydata([(shift, 0, 0), (shift+4, 0, 0), (shift, 6, 2)], [], [(0, 1, 2)])
                obj = bpy.data.objects.new(label, mesh)
                collection.objects.link(obj)
                obj.parent = parent
                obj['asset_group'] = 'bridge'
                obj['asset_name'] = 'Fixture bridge'
                obj['source_node'] = node
                obj['part_name'] = label
                obj.hide_render = hidden
            bpy.context.view_layer.update()
            worker = root / state
            worker.mkdir()
            model = worker / 'model.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(model))
            plan['states'][state] = {'worker': str(worker), 'model_sha256': sha(model),
                'active_component_names': [name], 'source_nodes': [node],
                'default_hidden': state == 'applied'}
            plan['protected_files'][str(model)] = sha(model)
        result = import_endpoint_objects(plan, 'Fixture')
        assert result['pivot'] == [17., 23., 3.], result
        collection = bpy.data.collections['Fixture Working']
        assert set(obj.name for obj in collection.objects) == {'Raised', 'Lowered'}
        assert set(obj.name for obj in bpy.context.scene.objects) == {'Raised', 'Lowered'}
        assert all(obj.parent is None for obj in collection.objects)
        assert not bpy.data.objects['Raised'].hide_render
        assert bpy.data.objects['Lowered'].hide_render
        level = root / 'level.json'
        level.write_text(json.dumps({'sight_obstacles': [
            {'points': [{'x': 10, 'y': 20, 'z_bottom': 0, 'z_top': 4}]} for _ in range(3)]}))
        output = root / 'library'
        export_asset_library('Fixture', output, level, asset_ids=['bridge'],
            standalone_pivots={'bridge': plan['standalone_pivot']}, include_hidden_objects=['Lowered'])
        descriptor = json.loads((output / 'bridge/asset.json').read_text())
        assert exported_pivot(output, 'bridge') == plan['standalone_pivot']
        assert descriptor['source_origin_scene'] == plan['standalone_pivot']
        assert {p['node']: p['default_hidden'] for p in descriptor['parts']} == {
            'building-001': False, 'building-002': True}
        assert descriptor['bounds_local_scene'] == {'min': [-7., -3., -1.], 'max': [7., 3., 1.]}
        for mutation in ('pivot', 'missing', 'duplicate', 'model'):
            bad = copy.deepcopy(plan)
            if mutation == 'pivot':
                bad['standalone_pivot'][0] += 1
            elif mutation == 'missing':
                bad['states']['applied']['active_component_names'] = ['Missing']
            elif mutation == 'duplicate':
                bad['states']['applied']['active_component_names'] = ['Lowered', 'Lowered']
            else:
                bad['states']['applied']['model_sha256'] = '0' * 64
            try:
                import_endpoint_objects(bad, 'Fixture')
            except ValueError:
                pass
            else:
                raise AssertionError('Accepted changed ' + mutation)
        for filename, digest in plan['protected_files'].items():
            assert sha(Path(filename)) == digest
    print('PASS: isolated independent endpoint import, parent transforms, exact hidden whitelist, common pivot, export and tamper rejection')


if __name__ == '__main__':
    check()
