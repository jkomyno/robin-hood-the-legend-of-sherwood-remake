"""Transfer cached appearance across an approved source-node ownership change."""
import hashlib
import json
from pathlib import Path
import sys
from array import array
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render_multiview_asset import render
from refinement_review import _tile
from refinement_workspace import _geometry


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def topology(obj):
    return ([list(v.co) for v in obj.data.vertices], [list(p.vertices) for p in obj.data.polygons])


def run(experiment, donors):
    experiment = Path(experiment).resolve()
    frames = json.loads((experiment/'views.json').read_text())
    source = experiment/'approved-model.blend'
    bpy.ops.wm.open_mainfile(filepath=str(source))
    objects = [o for o in bpy.data.collections[frames['collection_name']].all_objects
               if o.type == 'MESH' and o.get('asset_group') == frames['asset_id']]
    before = {o.name: _geometry(o) for o in objects}
    all_before = {o.name: _geometry(o) for o in bpy.data.objects if o.type == 'MESH'}
    record = []
    for donor_path, target_names in donors:
        donor_path = Path(donor_path).resolve()
        if target_names == '*':
            target_names = {o.name:o.name for o in objects}
        elif target_names == 'except-canopy':
            target_names = {o.name:o.name for o in objects if o.get('source_node') != 'building-221'}
        with bpy.data.libraries.load(str(donor_path), link=False) as (available, selected):
            if set(target_names.values()) - set(available.objects):
                raise ValueError('Missing appearance donor')
            selected.objects = list(target_names.values())
        loaded = dict(zip(target_names.values(), selected.objects))
        for target_name, donor_name in target_names.items():
            obj = next(o for o in objects if o.name == target_name)
            donor = loaded[donor_name]
            if topology(obj) != topology(donor):
                raise ValueError('Cached appearance topology differs: '+target_name)
            obj.data = donor.data.copy()
            record.append({'object': target_name, 'source_node': obj.get('source_node'),
                           'donor': str(donor_path), 'donor_sha256': sha(donor_path), 'donor_object': donor_name})
        for donor in loaded.values():
            bpy.data.objects.remove(donor, do_unlink=True)
    if set(before) != {v['object'] for v in record}:
        raise ValueError('Appearance transfer must cover every exact owned mesh')
    if before != {o.name: _geometry(o) for o in objects}:
        raise ValueError('Appearance transfer changed approved geometry')
    if all_before != {o.name: _geometry(o) for o in bpy.data.objects if o.type == 'MESH'}:
        raise ValueError('Appearance transfer changed outside geometry')
    output = experiment/'bake-reuse-v1'
    output.mkdir()
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'worker.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(output/'worker.blend'))
    w,h=frames['tile_size'];render(experiment/'views.json',output/'actual',width=w)
    buffers=[]
    for i in range(8):
        image=bpy.data.images.load(str(output/'actual'/f'view-{i}-textured.png'),check_existing=False)
        pixels=array('f',[0])*len(image.pixels);image.pixels.foreach_get(pixels);buffers.append(pixels);bpy.data.images.remove(image)
    _tile(buffers,w,h,output/'actual/textured.png')
    (output/'appearance-transfer.json').write_text(json.dumps({'status':'PASS','geometry_verified':True,
        'all_owned_meshes':len(objects),'all_scene_meshes_unchanged':len(all_before),'source_model_sha256':sha(source),
        'baked_model_sha256':sha(output/'worker.blend'),'donors':record,'method':'Exact mesh topology match; copy stored UVs and packed materials from existing reviewed appearance workers. No generation or rebaking.'},indent=2)+'\n')
    print('APPEARANCE_TRANSFER_PASS',experiment.name,flush=True)


if __name__ == '__main__':
    config = json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
    for job in config['jobs']:
        run(job['experiment'], job['donors'])
