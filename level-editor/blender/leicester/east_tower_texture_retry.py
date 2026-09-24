"""Bake a material-specific tower retry into its exact reviewed revealed scope.

Run with -- REVEALED_EXPERIMENT COVERED_EXPERIMENT GENERATION OUTPUT.
Keeps original source layers/atlases and every nonselected material unchanged.
"""
import sys,json,hashlib
from pathlib import Path
from array import array
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from architecture_texture_packets import original_layers
from tower_texture_scope import capture,verify
from bake_reviewed_asset import stage
from render_multiview_asset import render
from refinement_review import _tile


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(revealed,covered,generation,output):
    e,c,g,out=map(lambda p:Path(p).resolve(),(revealed,covered,generation,output))
    if out.exists():raise FileExistsError(out)
    source=e/'bake-gray-v4/worker.blend'
    handoff=json.loads((source.parent/'handoff.json').read_text())
    if digest(source)!=handoff['final_model_sha256']:raise ValueError('Held reviewed worker changed')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    manifest=json.loads((e/'views.json').read_text())
    displayed=set(manifest.get('render_object_names') or manifest['object_names'])
    selected={name:[p.index for p in bpy.data.objects[name].data.polygons] for name in sorted(displayed)}
    _,protected=capture(manifest,labels=['__no_selected_label__'])
    for name,indices in selected.items():
        for i in indices:del protected[name][str(i)]
    manifest.update(texture_receiver_object_names=sorted(selected),texture_receiver_face_indices=selected,
                    texture_projection_labels=[x['projection_label'] for x in manifest['projection_layers']],
                    texture_material_suffix='openrouter-timber-single-v1',texture_view_selection='best-facing-single',
                    texture_two_sided_object_names=sorted(handoff['scope']))
    frames=e/'views-openrouter-timber-v1.json'
    if frames.exists():raise FileExistsError(frames)
    frames.write_text(json.dumps(manifest,indent=2)+'\n')
    original=original_layers(manifest)
    stage(frames,g/'generated-preserved.png',out,texels_per_unit=2)
    preservation=verify(manifest,protected)
    if original!=original_layers(manifest,original):raise ValueError('Original UVs or atlases changed')
    preservation.update(status='PASS',source_model=str(source),source_model_sha256=digest(source),
        baked_model_sha256=digest(out/'worker.blend'),original_uv_and_packed_atlases_preserved=True,
        selected_faces=selected,generation=str(g),generation_sha256=digest(g/'generation.json'))
    (out/'protected-materials.json').write_text(json.dumps(preservation,indent=2)+'\n')
    width,height=json.loads((c/'views.json').read_text())['tile_size']
    render(c/'views.json',out/'actual-covered',width=width)
    buffers=[]
    for index in range(8):
        image=bpy.data.images.load(str(out/'actual-covered'/f'view-{index}-textured.png'),check_existing=False)
        values=array('f',[0])*len(image.pixels);image.pixels.foreach_get(values);buffers.append(values);bpy.data.images.remove(image)
    _tile(buffers,width,height,out/'actual-covered/textured.png')
    (out/'paired-state-handoff.json').write_text(json.dumps({
        'status':'awaiting-actual-view-inspection','asset_id':manifest['asset_id'],
        'model':str(out/'worker.blend'),'model_sha256':digest(out/'worker.blend'),
        'revealed_manifest':str(frames),'covered_manifest':str(c/'views.json'),
        'revealed_sheet':str(out/'actual/textured.png'),'covered_sheet':str(out/'actual-covered/textured.png'),
        'preservation':str(out/'protected-materials.json')},indent=2)+'\n')
    print('PASS guarded paired-state bake',flush=True)


def validate_covered_state(model, frame_path, output):
    """Bind a covered render of the same immutable material/geometry worker."""
    from verify_staged_handoffs import snapshot
    model, frame_path, output = map(Path, (model, frame_path, output))
    frame = json.loads(frame_path.read_text())
    bpy.ops.wm.open_mainfile(filepath=str(model))
    selected = lambda obj: obj.get('asset_group') == frame['asset_id']
    before = snapshot(frame['collection_name'], True, select=selected)
    render(frame_path, output/'actual', width=frame['tile_size'][0])
    if before != snapshot(frame['collection_name'], True, select=selected):
        raise ValueError('Covered state render changed model/material/UV state')
    width, height = frame['tile_size']; buffers = []
    for index in range(8):
        image = bpy.data.images.load(str(output/'actual'/f'view-{index}-textured.png'), check_existing=False)
        values = array('f', [0]) * len(image.pixels); image.pixels.foreach_get(values)
        buffers.append(values); bpy.data.images.remove(image)
    _tile(buffers, width, height, output/'actual/textured.png')
    report = {'status':'PASS', 'materials_preserved':True, 'geometry_verified':True,
              'baked_model_sha256':digest(model), 'frame_manifest':str(frame_path.resolve()),
              'frame_manifest_sha256':digest(frame_path),
              'object_names':frame.get('render_object_names') or frame['object_names'],
              'actual_sheet_sha256':digest(output/'actual/textured.png'),
              'method':'All asset mesh world geometry, assigned material graphs/images, UV layers and visibility compared exactly before/after rendering this immutable worker.'}
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
