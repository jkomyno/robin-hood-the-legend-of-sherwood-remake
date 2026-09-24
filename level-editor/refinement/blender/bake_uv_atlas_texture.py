"""Install a protected generated UV atlas without changing nonplanar geometry."""
import sys,json,shutil
from pathlib import Path
from array import array
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import bpy
import numpy as np
from PIL import Image
from uv_atlas import sha,validate_evidence,validate_uv_atlas_bake
from planar_texture_guards import validate_fill
from refinement_workspace import _geometry
from bake_reviewed_asset import _materials
from export_uv_atlas_evidence import export
from refinement_review import _tile
from render_multiview_asset import render

def bake_uv(experiment,generated,output):
    experiment,generated,output=map(lambda p:Path(p).resolve(),(experiment,generated,output))
    if output.exists():raise FileExistsError(output)
    manifest=json.loads((experiment/'views.json').read_text());approval=json.loads((experiment/'approval.json').read_text());prep=json.loads((experiment/'preparation.json').read_text());evidence=json.loads((experiment/'uv-evidence.json').read_text())
    if manifest.get('projection_kind')!='uv-atlas' or approval.get('status')!='approved':raise ValueError('Expected explicitly approved UV-atlas geometry')
    for name,digest in prep['files'].items():
        if sha(experiment/name)!=digest:raise ValueError('UV preparation evidence changed: '+name)
    validate_evidence(evidence)
    if sha(experiment/'approved-model.blend')!=approval['saved_model_sha256'] or evidence['model_sha256']!=approval['saved_model_sha256']:raise ValueError('Approved model or UV evidence changed')
    original=np.asarray(Image.open(experiment/'input.png').convert('RGBA'));result=np.asarray(Image.open(generated).convert('RGBA'));mask=np.asarray(Image.open(experiment/'mask.png').convert('RGBA'));surface=np.asarray(Image.open(experiment/'surface.png').convert('L'))>0
    editable=validate_fill(original,result,mask,surface)
    bpy.ops.wm.open_mainfile(filepath=str(experiment/'approved-model.blend'))
    scene=bpy.data.scenes[manifest['scene_name']];bpy.context.window.scene=scene;obj=bpy.data.objects.get(evidence['receiver'])
    if obj is None or obj.get('asset_group')!=manifest['asset_id']:raise ValueError('Actual approved UV receiver is absent')
    geometry={o.name:_geometry(o) for o in scene.objects};uv={l.name:[list(v.uv) for v in l.data] for l in obj.data.uv_layers};outside={o.name:_materials(o) for o in scene.objects if o.type=='MESH' and o!=obj}
    slot=evidence['material_slot'];material=obj.data.materials[slot]
    images=[n for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    if len(images)!=1 or tuple(images[0].image.size)!=tuple(evidence['atlas_dimensions']):raise ValueError('Saved atlas receiver changed')
    packed=np.asarray(images[0].image.pixels[:],np.float32)
    import hashlib
    if hashlib.sha256(packed.tobytes()).hexdigest()!=evidence['packed_pixel_sha256']:raise ValueError('Actual packed source atlas changed')
    output.mkdir(parents=True);shutil.copy2(generated,output/'atlas.png')
    replacement=material.copy();obj.data.materials[slot]=replacement
    image=bpy.data.images.load(str(output/'atlas.png'),check_existing=False);image.alpha_mode=evidence['alpha_mode'];image.reload();image.pack()
    next(n for n in replacement.node_tree.nodes if n.type=='TEX_IMAGE').image=image
    if geometry!={o.name:_geometry(o) for o in scene.objects} or uv!={l.name:[list(v.uv) for v in l.data] for l in obj.data.uv_layers}:raise ValueError('UV atlas replacement changed geometry or UVs')
    if outside!={o.name:_materials(o) for o in scene.objects if o.name in outside}:raise ValueError('UV atlas replacement changed outside materials')
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(output/'worker.blend'))
    # Export the actual saved result through the same read-only proof path.
    # The exporter consumes a workspace schema without changing the saved file.
    config=json.loads((Path(evidence['workspace'])/'workspace.json').read_text())
    audit_workspace=output/'audit-workspace';audit_workspace.mkdir();(audit_workspace/'workspace.json').write_text(json.dumps(config));(audit_workspace/'model.blend').symlink_to(output/'worker.blend');(audit_workspace/'modified').symlink_to(Path(manifest['reviewed_packet']))
    export(audit_workspace,output/'uv-evidence.json')
    frames_path=Path(manifest['reviewed_packet'])/'views.json'
    if sha(frames_path)!=manifest['reviewed_manifest_sha256']:raise ValueError('Frozen QA cameras changed')
    report=dict(asset_id=manifest['asset_id'],projection_kind='uv-atlas',geometry_verified=True,uv_verified=True,protected_changes=0,editable_pixels=editable,outside_objects_unchanged=len(outside),generated_sha256=sha(output/'atlas.png'),approved_model_sha256=approval['saved_model_sha256'],baked_model_sha256=sha(output/'worker.blend'),baked_uv_evidence_sha256=sha(output/'uv-evidence.json'),preparation_sha256=sha(experiment/'preparation.json'),frame_manifest_sha256=sha(frames_path),input_sha256=sha(experiment/'input.png'))
    validate_uv_atlas_bake(report,experiment,output)
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    frames=json.loads(frames_path.read_text());w,h=frames['tile_size'];frames['layout'].update(width=w*4,height=h*2)
    for v in frames['views']:v['crop']=dict(left=v['index']%4*w,top=v['index']//4*h,width=w,height=h)
    (output/'qa-views.json').write_text(json.dumps(frames,indent=2)+'\n');render(output/'qa-views.json',output/'actual',width=w)
    buffers=[]
    for i in range(8):
        image=bpy.data.images.load(str(output/'actual'/f'view-{i}-textured.png'),check_existing=False);pixels=array('f',[0])*len(image.pixels);image.pixels.foreach_get(pixels);buffers.append(pixels);bpy.data.images.remove(image)
    _tile(buffers,w,h,output/'actual/textured.png');return report

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    if len(args)!=3:raise ValueError('Expected experiment protected-generated.png new-output')
    print(json.dumps(bake_uv(*args)))
