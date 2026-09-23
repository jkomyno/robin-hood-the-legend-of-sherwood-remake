"""Expand source-only terrain coverage without changing reviewed clearance geometry."""
import hashlib,json,shutil,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
from refinement_workspace import _files,_freeze_masks,validate
from refinement_review import render_review
from prepare_terrain import install_ground_source_material
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=WORK/'round-18/assets/nottingham-terrain-ground';new=WORK/'round-27/assets/nottingham-terrain-ground'
if new.exists() and '--resume' not in sys.argv:raise FileExistsError(new)
new.mkdir(parents=True,exist_ok=True);shutil.copytree(old/'reference',new/'reference',dirs_exist_ok=True);shutil.copytree(old/'modified',new/'input',dirs_exist_ok=True);shutil.copy2(old/'model.blend',new/'baseline.blend')
config=json.loads((old/'workspace.json').read_text());config.update(source_path=str(new/'reference/source.png'),source_blend=str(old/'model.blend'),source_blend_sha256=sha(old/'model.blend'),baseline_sha256=sha(new/'baseline.blend'),source_mask_manifest=str(new/'source-masks.json'))
maskdir=WORK/'mask-review/inventory-terrain-complete-v7';masks=json.loads((maskdir/'source-masks.json').read_text());(new/'source-masks.json').write_text(json.dumps(masks,indent=2)+'\n');config['source_mask_parent_manifest']=str(maskdir/'source-masks.json');config['source_mask_parent_sha256']=sha(maskdir/'source-masks.json')
bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));bpy.context.window.scene=bpy.data.scenes[config['scene_name']];ground=next(o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and o.get('source_node')=='ground')
def geometry(o):return dict(vertices=[list(v.co) for v in o.data.vertices],faces=[list(p.vertices) for p in o.data.polygons],uv={l.name:[list(v.uv) for v in l.data] for l in o.data.uv_layers},matrix=[list(r) for r in o.matrix_world])
before=geometry(ground);material=install_ground_source_material(ground,new/'reference/source.png',masks,new);assert before==geometry(ground)
config['input_files']=_files(new/'input');config['reference_files']=_files(new/'reference')
if (new/'mask-reference').exists():
 archive=new/('mask-reference-previous-'+sha(new/'mask-reference/assignments.json')[:12]+'-'+str(len(list(new.glob('mask-reference-previous-*')))))
 (new/'mask-reference').rename(archive)
_freeze_masks(new,config);(new/'workspace.json').write_text(json.dumps(config,indent=2)+'\n');bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'))
frames=json.loads((new/'input/views.json').read_text());layers=frames['projection_layers']
# Keep the frozen layer source paths; their image bytes are unchanged.
if (new/'modified').exists():
 (new/'modified').rename(new/('modified-previous-'+sha(new/'modified/views.json')[:12]+'-'+str(len(list(new.glob('modified-previous-*'))))))
report=render_review(new/'modified',scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=config['asset_id'],source_path=Path(config['source_path']),projection_layers=layers,source_mask_manifest=new/'source-masks.json',frame_manifest=new/'input/views.json',allow_mask_revision=True)
validation=validate(new);(new/'validation.json').write_text(json.dumps(validation,indent=2)+'\n');(new/'projection-correction.json').write_text(json.dumps(dict(status='PASS-geometry-preserved',before_model_sha256=sha(old/'model.blend'),model_sha256=sha(new/'model.blend'),geometry_uv_world_matrix_unchanged=True,geometry_sha256=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),material=material,source_domain_authoring=str(maskdir/'authoring.json')),indent=2)+'\n');shutil.copy2(maskdir/'source-ownership.png',new/'source-ownership.png');print('Terrain packet rendered',new,flush=True)
