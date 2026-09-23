"""Replace an approved planar atlas in a separate worker; preserve geometry/UVs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import hashlib,json
from array import array
import bpy
import numpy as np
from PIL import Image
from planar_texture_guards import validate_fill
from refinement_workspace import _geometry
from bake_reviewed_asset import _materials
from refinement_review import _tile
from render_multiview_asset import render


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bake_planar(experiment,generated,output):
    experiment,generated,output=map(lambda p:Path(p).resolve(),(experiment,generated,output))
    if output.exists():raise FileExistsError(output)
    manifest=json.loads((experiment/'views.json').read_text());approval=json.loads((experiment/'approval.json').read_text())
    if manifest.get('projection_kind')!='planar-atlas' or approval.get('status')!='approved':raise ValueError('Expected approved planar packet')
    preparation=json.loads((experiment/'preparation.json').read_text())
    for name,digest in preparation['files'].items():
        if sha(experiment/name)!=digest:raise ValueError('Planar packet evidence changed: '+name)
    if sha(bpy.data.filepath)!=approval['saved_model_sha256']:raise ValueError('Loaded model differs from approved model')
    for pathkey,hashkey in [('atlas_source','atlas_sha256'),('audited_glb','audited_glb_sha256'),('ownership_report','ownership_sha256'),('known_mask','known_mask_sha256')]:
        if sha(manifest[pathkey])!=manifest[hashkey]:raise ValueError('Planar source evidence changed: '+pathkey)
    original=np.array(Image.open(experiment/'input.png').convert('RGBA'));result=np.array(Image.open(generated).convert('RGBA'))
    editable=validate_fill(original,result,np.array(Image.open(experiment/'mask.png').convert('RGBA')),np.array(Image.open(experiment/'surface.png').convert('L'))>0)
    scene=bpy.data.scenes[manifest['scene_name']];bpy.context.window.scene=scene
    objects=[o for o in scene.objects if o.type=='MESH' and o.get('asset_group')==manifest['asset_id']]
    if len(objects)!=1:raise ValueError('Planar atlas requires one receiver')
    obj=objects[0];used={f.material_index for f in obj.data.polygons}
    if len(used)!=1:raise ValueError('Expected one planar material')
    slot=next(iter(used));material=obj.data.materials[slot]
    nodes=[n for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    if len(nodes)!=1:raise ValueError('Expected exactly one planar image')
    atlas=nodes[0].image
    reference=bpy.data.images.load(str(experiment/'input.png'),check_existing=False)
    try:
        if tuple(atlas.size)!=tuple(reference.size) or not np.array_equal(np.array(atlas.pixels[:]),np.array(reference.pixels[:])):
            raise ValueError('Packed model atlas differs from approved input pixels')
    finally:bpy.data.images.remove(reference)
    geometry={o.name:_geometry(o) for o in scene.objects}
    uv={layer.name:[list(v.uv) for v in layer.data] for layer in obj.data.uv_layers}
    outside={o.name:_materials(o) for o in scene.objects if o.type=='MESH' and o!=obj}
    replacement=material.copy();obj.data.materials[slot]=replacement
    image=bpy.data.images.load(str(generated),check_existing=False);image.pack()
    next(n for n in replacement.node_tree.nodes if n.type=='TEX_IMAGE').image=image
    if geometry!={o.name:_geometry(o) for o in scene.objects} or uv!={l.name:[list(v.uv) for v in l.data] for l in obj.data.uv_layers}:
        raise ValueError('Planar texture replacement changed geometry or UVs')
    if outside!={o.name:_materials(o) for o in scene.objects if o.name in outside}:raise ValueError('Outside material changed')
    output.mkdir(parents=True)
    frames_path=Path(manifest['reviewed_packet'])/'views.json'
    if sha(frames_path)!=manifest['reviewed_manifest_sha256']:raise ValueError('Approved QA cameras changed')
    frames=json.loads(frames_path.read_text());w,h=frames['tile_size'];frames['layout'].update(width=w*4,height=h*2)
    for v in frames['views']:v['crop']={'left':v['index']%4*w,'top':v['index']//4*h,'width':w,'height':h}
    (output/'qa-views.json').write_text(json.dumps(frames,indent=2)+'\n')
    report={'asset_id':manifest['asset_id'],'geometry_verified':True,'uv_verified':True,'outside_objects_unchanged':len(outside),
            'generated_sha256':sha(generated),'input_sha256':sha(experiment/'input.png'),'protected_changes':0,'editable_pixels':editable,
            'projection_kind':'planar-atlas','approved_model_sha256':approval['saved_model_sha256'],
            'preparation_sha256':sha(experiment/'preparation.json'),'frame_manifest_sha256':sha(frames_path)}
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(output/'worker.blend'))
    render(output/'qa-views.json',output/'actual',width=w)
    buffers=[]
    for i in range(8):
        image=bpy.data.images.load(str(output/'actual'/f'view-{i}-textured.png'),check_existing=False)
        pixels=array('f',[0])*len(image.pixels);image.pixels.foreach_get(pixels);buffers.append(pixels);bpy.data.images.remove(image)
    _tile(buffers,w,h,output/'actual/textured.png')
    return report

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    if len(args)!=3:raise ValueError('Expected experiment generated-preserved.png new-output')
    print(json.dumps(bake_planar(*args)))
