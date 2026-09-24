"""Keep distinct covered roof and revealed retained-surface material states."""
import sys,json,copy,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from correct_source_projection import geometry,geometry_sha

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(d,indent=2)+'\n')
def main():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from refinement_workspace import _review_layers,validate
 from refinement_review import render_review
 from reveal_components import filter_receivers
 from source_projection_bake import bake
 sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'));from material_states import apply_material_state
 w=WORK/'round-40/assets/nottingham-castle-main-hall';bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));cfg=json.loads((w/'workspace.json').read_text());original=geometry();layers=_review_layers(cfg);ls=json.loads((w/'projection-layers.json').read_text());objects=list(bpy.data.collections[cfg['collection_name']].all_objects)
 if '--resume-states' in sys.argv:
  record=json.loads((w/'material-states.json').read_text());assert record['model_sha256']==sha(w/'model.blend');records=record['records'];covered_layers=json.loads((w/'projection-state-layers.json').read_text())['covered']
 else:
  room_original=next(d for d in layers if d['projection_label']=='interior-patch-008')
  targets=[o for o in filter_receivers([o for o in objects if o.type=='MESH'and not o.hide_render and o.get('source_node')in room_original['receiver_nodes']],room_original.get('receiver_components'),available_objects=objects)if o.get('asset_group')==cfg['asset_id']]
  assert len(targets)==13
  def mapping(o):return {str(f.index):{'slot':f.material_index,'material':o.data.materials[f.material_index].name}for f in o.data.polygons}
  records=[{'object':o.name,'source_node':o.get('source_node'),'projection_component':o.get('projection_component'),'revealed_face_materials':mapping(o)}for o in targets]
  covered_layers=[copy.deepcopy(d)for d in layers if d['projection_label']!='interior-patch-008'];ex=next(d for d in covered_layers if d['projection_label']=='exterior');transferred=set(room_original['receiver_nodes']);ex['receiver_nodes']=sorted(set(ex['receiver_nodes'])|transferred);ex['occluder_nodes']=sorted(set(ex['occluder_nodes'])|transferred);ex['receiver_components']=[d for d in ex.get('receiver_components',[])if d['source_node']not in transferred]
  bake('nottingham',ls['sources']['exterior'],w/'inspection/covered-state-bake.json',receiver_nodes=room_original['receiver_nodes'],occluder_nodes=ex['occluder_nodes'],projection_label='exterior',source_mask_manifest=w/'source-masks.json',receiver_object_names=[o.name for o in targets],receiver_components=room_original.get('receiver_components'),receiver_asset_id=cfg['asset_id'],material_suffix='covered-state',preserve_authored=False)
  for r,o in zip(records,targets):r['covered_face_materials']=mapping(o)
  write(w/'projection-state-layers.json',{'covered':covered_layers,'revealed':layers})
  assert geometry()==original
  bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'));write(w/'material-states.json',{'version':1,'model_sha256':sha(w/'model.blend'),'records':records,'geometry_sha256':geometry_sha(original),'sources':{'covered':sha(ls['sources']['exterior']),'revealed':sha(ls['sources']['interior'])},'reason':'Source-visible retained roof, wall504, cut-edge526 and small landing/floor regions have different covered and revealed artwork. All thirteen room receivers retain separate state slots and UV atlases; state diagnostics select the matching source/occlusion layer.'})
  # Regenerate primary source diagnostic with the correct covered ownership.
  render_review(w/'modified-covered',scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],asset_id=cfg['asset_id'],source_path=cfg['source_path'],frame_manifest=w/'input/views.json',projection_layers=covered_layers,source_mask_manifest=cfg['source_mask_manifest'],allow_projection_revision=True,allow_mask_revision=True)
  history=w/'history/before-explicit-material-states';history.parent.mkdir(exist_ok=True);(w/'modified').rename(history);(w/'modified-covered').rename(w/'modified')
 old_states=json.loads((w/'states-room/states.json').read_text());new_states=[];bindings=[]
 for state in old_states['states']:
  label=state['state'];bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update()
  for r in records:apply_material_state(bpy.data.objects,r,label)
  names=set(state['object_names'])
  for o in list(bpy.data.objects):
   if o.type=='MESH'and o.get('asset_group')==cfg['asset_id']:o.hide_render=o.name not in names
  dst=w/'inspection/state-models'/label;dst.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(dst/'model.blend'));write(dst/'workspace.json',cfg)
  # Render_review requires hidden components still present as context; restore render
  # flags in memory and pass the exact reviewed display selection separately.
  for o in list(bpy.data.objects):
   if o.type=='MESH'and o.get('asset_group')==cfg['asset_id']:o.hide_render=False
  path=w/'states-final/patch-008'/label;frame=json.loads((w/'input/views.json').read_text());src=ls['sources']['exterior'if label=='covered'else'interior'];frame['source_sha256']=sha(src)
  result=render_review(path,scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],asset_id=cfg['asset_id'],source_path=src,frame_manifest=frame,projection_layers=covered_layers if label=='covered'else layers,source_mask_manifest=cfg['source_mask_manifest'],render_object_names=list(names),allow_projection_revision=True,allow_mask_revision=True)
  write(dst/'modified/views.json',json.loads((path/'views.json').read_text()));new_states.append({**state,'path':str(path),'view_sha256':sha(path/'views.json'),'object_names':result['object_names']});bindings.append({'state':label,'model':str(dst/'model.blend'),'model_sha256':sha(dst/'model.blend'),'frame_manifest':str(path/'views.json'),'frame_manifest_sha256':sha(path/'views.json'),'object_names':sorted(names)})
 write(w/'states-final/states.json',{**old_states,'states':new_states});write(w/'state-packet.json',{'version':1,'directory':str(w/'states-final'),'revealed_input':'input'});write(w/'inspection/state-models/manifest.json',{'version':1,'primary_model_sha256':sha(w/'model.blend'),'states':bindings,'material_states_sha256':sha(w/'material-states.json')})
 bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));write(w/'validation.json',validate(w));print('EXPLICIT MATERIAL STATES READY',flush=True)
if __name__=='__main__':main()
