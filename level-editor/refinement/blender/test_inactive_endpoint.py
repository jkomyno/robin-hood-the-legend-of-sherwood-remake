"""Blender: exact dormant endpoint preserves canonical IDs without activation."""
import json
import sys
import tempfile
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_staged_state_verification import fixture_worker
from compile_texture_states import compile_states, _sha
from verify_staged_patch_state import verify_reviewed_states, verify_inactive_states
from import_reviewed_geometry import import_asset_geometry
from export_editor import export_asset_library


def check():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        covered = fixture_worker(root/'covered.blend', False)
        revealed = fixture_worker(root/'revealed.blend', True)
        initial = fixture_worker(root/'initial.blend', True)
        body = bpy.data.objects['Body']
        door = body.copy(); door.data = body.data.copy(); door.name = 'Door'
        door['source_node'] = 'building-003'
        bpy.data.collections['Fixture Working'].objects.link(door)
        asset_root = bpy.data.objects.new('Asset root', None)
        asset_root['asset_group'] = 'house'
        bpy.data.collections['Fixture Working'].objects.link(asset_root)
        asset_root.rotation_euler.x = -1.5707963267948966
        door.parent = asset_root
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=initial['blend_path'])
        initial['blend_sha256'] = _sha(initial['blend_path'])
        initial['object_names'].append('Door'); initial['render_object_names'].append('Door')
        applied = fixture_worker(root/'applied.blend', True)
        for item, state in [(revealed,'revealed'),(initial,'initial'),(applied,'applied')]:
            item['id'] = state
            item['source_nodes'] = ['building-001','building-003']
        covered['source_nodes'] = ['building-001','building-003']
        covered['texture_states'] = [revealed,initial,applied]
        covered['texture_state_roles'] = {'revealed':'map-reveal','initial':'standalone-initial','applied':'standalone-applied'}
        packets = []
        for item in [initial,applied]:
            packet = str(root/item['id'])
            Path(item['review_manifest']).write_text(json.dumps({'reviewed_packet':packet,'source_sha256':item['id']}))
            packets.append({'path':packet,'source_sha256':item['id'],'object_names':item['render_object_names']})
        states = root/'states.json'; states.write_text(json.dumps({'asset_id':'house','states':packets}))
        covered['texture_state_role_evidence'] = {'states_json':str(states),'states_sha256':_sha(states)}
        stage = root/'stage'; stage.mkdir()
        compiled = compile_states(covered,stage/'worker.blend')
        inactive = compiled['inactive_object_bindings']
        assert len(inactive)==1 and inactive[0]['source_node']=='building-003'
        assert len(verify_reviewed_states(stage,covered,compiled['state_bindings'],'Fixture Working'))==2
        assert verify_inactive_states(stage,covered,inactive,'Fixture Working')[0]['meshes']==1
        bpy.ops.wm.open_mainfile(filepath=initial['blend_path'])
        args = dict(asset_id='house',object_names=compiled['object_names'],collection_name='Fixture Working',source_nodes=covered['source_nodes'],replace_hidden_source_nodes=True)
        try:
            import_asset_geometry(compiled['blend_path'],**args)
        except ValueError: pass
        else: raise AssertionError('Hidden import accepted without exact proof')
        bpy.ops.wm.open_mainfile(filepath=initial['blend_path'])
        import_asset_geometry(compiled['blend_path'],inactive_object_bindings=inactive,**args)
        assert bpy.data.objects[inactive[0]['staged_name']].hide_render
        level=root/'level.json';level.write_text(json.dumps({'sight_obstacles':[{'points':[{'x':0,'y':0,'z_bottom':0,'z_top':2}]} for _ in range(4)]}))
        export_asset_library('Fixture',stage/'assets',level,asset_ids=['house'],include_hidden_objects=[row['staged_name'] for row in inactive])
        descriptor=json.loads((stage/'assets/house/asset.json').read_text())
        assert next(part for part in descriptor['parts'] if part['node']=='building-003')['default_hidden']
        print('PASS: dormant exact endpoint proof, hidden allowlist rejection, import and default-hidden export')


if __name__=='__main__':check()
