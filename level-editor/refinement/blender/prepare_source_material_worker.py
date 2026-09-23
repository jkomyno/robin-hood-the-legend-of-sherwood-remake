"""Bake source-owned materials into a clone without changing reviewed geometry."""
import sys
import json
import hashlib
from pathlib import Path
from array import array
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_projection_bake import bake
from refinement_workspace import _geometry
from render_multiview_asset import render
from refinement_review import _tile

def prepare(frames_path, output):
    frames_path, output = Path(frames_path).resolve(), Path(output).resolve()
    frames = json.loads(frames_path.read_text())
    source = Path(bpy.data.filepath)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if output.exists(): raise FileExistsError(output)
    output.mkdir(parents=True)
    scene=bpy.data.scenes[frames['scene_name']]
    bpy.context.window.scene=scene
    geometry={o.name:_geometry(o) for o in scene.objects}
    reports=[]
    for index, layer in enumerate(frames['projection_layers']):
        reports.append(bake(frames['asset_id'],layer['source_path'],output/f'layer-{index}.json',
            collection_name=frames['collection_name'],receiver_nodes=layer['receiver_nodes'],
            occluder_nodes=layer['occluder_nodes'],projection_label=layer['projection_label'],
            source_mask_manifest=frames['source_mask_manifest'],texels_per_unit=2,
            preserve_authored=False,receiver_object_names=frames['object_names']))
    if geometry!={o.name:_geometry(o) for o in scene.objects}: raise RuntimeError('Source material preparation changed geometry')
    for name in frames['object_names']:
        obj=scene.objects[name]
        for face in obj.data.polygons:
            material=obj.data.materials[face.material_index]
            if not material.get('source_ownership_bake'): raise RuntimeError('Unbaked source material')
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'model.blend'))
    for view in frames['views']:
        view['crop']={'left':view['index']%4*frames['tile_size'][0],
                      'top':view['index']//4*frames['tile_size'][1],
                      'width':frames['tile_size'][0],'height':frames['tile_size'][1]}
    (output/'render-frames.json').write_text(json.dumps(frames,indent=2)+'\n')
    render(output/'render-frames.json',output/'actual',width=frames['tile_size'][0])
    buffers=[]
    for index in range(8):
        image=bpy.data.images.load(str(output/'actual'/f'view-{index}-textured.png'),check_existing=False)
        pixels=array('f',[0])*len(image.pixels);image.pixels.foreach_get(pixels);buffers.append(pixels)
        bpy.data.images.remove(image)
    _tile(buffers,*frames['tile_size'],output/'actual/textured.png')
    report={'source_model':str(source),'source_model_sha256':source_hash,
        'derived_model_sha256':hashlib.sha256((output/'model.blend').read_bytes()).hexdigest(),
        'geometry_unchanged':True,'stored_material_validation':'PASS','layers':reports,
        'scope':'Source-mask constrained material preparation only; original geometry approval remains authoritative.'}
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    if len(args)!=2: raise ValueError('Expected -- frames.json new-output-directory')
    prepare(*args)
