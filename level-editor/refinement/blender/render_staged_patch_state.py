"""Render a staged patch with the reviewed state's exact cameras, without saving."""
import json
from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]/'blender'))
from render_multiview_asset import render


def run(stage, handoff_path, state, output):
    handoff=json.loads(Path(handoff_path).read_text())
    packet=json.loads(Path(handoff['review_manifest']).read_text())
    source=Path(handoff_path).parent/state/'renders.json'
    cameras=json.loads(source.read_text())['renders']
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    manifest={'asset_id':handoff['asset_id'],'scene_name':packet['scene_name'],'views':[
        {'index':index,'camera_matrix_world':camera['camera_matrix'],'ortho_scale':camera['ortho_scale'],
         'crop':{'width':camera['resolution'][0],'height':camera['resolution'][1]}}
        for index,camera in enumerate(cameras)]}
    manifest_path=output/'views.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    stage_path=Path(stage)
    bpy.ops.wm.open_mainfile(filepath=str(stage_path if stage_path.suffix=='.blend' else stage_path/'worker.blend'))
    scene=bpy.data.scenes[manifest['scene_name']];bpy.context.window.scene=scene
    for obj in scene.objects:
        if obj.type!='MESH':continue
        if obj.get('reveal_material_states'):
            record=json.loads(obj['reveal_material_states'])
            if record['patch']==handoff['state_trigger']:
                for face,slot in zip(obj.data.polygons,record[state]):face.material_index=slot
        if handoff['state_trigger'] in obj.get('reveal_hide_when_applied',[]):
            obj.hide_render=(state=='revealed')
    render(manifest_path,output/'renders',width=cameras[0]['resolution'][0])


if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
