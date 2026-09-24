"""Bake complete independent hall appearances for covered and revealed source states."""
import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from correct_source_projection import geometry,geometry_sha
W=Path(sys.argv[sys.argv.index('--')+1]).resolve()if'--'in sys.argv else WORK/'round-41/assets/nottingham-castle-main-hall'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(d,indent=2)+'\n')
def main():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from refinement_workspace import validate
 from refinement_review import render_review
 from source_projection_bake import bake
 from asset_reference_views import state_objects
 sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'));from material_states import apply_material_state
 bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'));bpy.context.view_layer.update();cfg=json.loads((W/'workspace.json').read_text());l=json.loads((W/'projection-layers.json').read_text());visibility=l['projection_reviews']['patch-008']['render_visibility'];objs=[o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH'and not o.hide_render];owned=[o for o in objs if o.get('asset_group')==cfg['asset_id']];assert len(owned)in [37,38],len(owned);base_hidden={o.name:o.hide_render for o in list(bpy.data.objects)if o.type=='MESH'and o.get('asset_group')==cfg['asset_id']};assert len(base_hidden)-len(owned)==10;geometry_before=geometry();names={state:[o.name for o in state_objects(objs,cfg['asset_id'],'patch-008',visibility,state)]for state in ['covered','revealed']};present={o.get('source_node')for o in objs};layers={
 'covered':[{'source_path':l['sources']['exterior'],'projection_label':'exterior','receiver_nodes':cfg['part_ids'],'occluder_nodes':sorted(present)}],
 'revealed':[{'source_path':l['sources']['interior'],'projection_label':'interior-patch-008','receiver_nodes':cfg['part_ids'],'occluder_nodes':sorted(present-set(visibility['revealed']['hidden_nodes'])),'exclude_occluder_components':visibility['revealed']['hidden_components']}],}
 records={o.name:{'object':o.name,'source_node':o.get('source_node'),'projection_component':o.get('projection_component')}for o in owned}
 for state in ['covered','revealed']:
  d=layers[state][0];bake('nottingham',d['source_path'],W/f'inspection/{state}-complete-state-bake.json',receiver_nodes=cfg['part_ids'],occluder_nodes=d['occluder_nodes'],projection_label=d['projection_label'],source_mask_manifest=W/'source-masks.json',receiver_asset_id=cfg['asset_id'],receiver_object_names=names[state],exclude_occluder_components=d.get('exclude_occluder_components'),material_suffix='complete-'+state+'-state',preserve_authored=False)
  for o in owned:records[o.name][state+'_face_materials']={str(f.index):{'slot':f.material_index,'material':o.data.materials[f.material_index].name}for f in o.data.polygons}
 assert geometry()==geometry_before
 for r in records.values():apply_material_state(bpy.data.objects,r,'covered')
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(W/'model.blend'));write(W/'material-states.json',{'version':1,'model_sha256':sha(W/'model.blend'),'records':list(records.values()),'geometry_sha256':geometry_sha(geometry_before),'scope':f'All{len(owned)} active hall parts; ten superseded source meshes stay hidden; each state uses its original image, complete receiver masks and exact authored cover/foreground occlusion.'});write(W/'projection-state-layers.json',layers)
 render_review(W/'modified',scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],asset_id=cfg['asset_id'],source_path=cfg['source_path'],frame_manifest=W/'input/views.json',projection_layers=layers['covered'],source_mask_manifest=cfg['source_mask_manifest'],allow_projection_revision=True,allow_mask_revision=True)
 state_records=[];bindings=[]
 for state in ['covered','revealed']:
  bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'));bpy.context.view_layer.update()
  for r in records.values():apply_material_state(bpy.data.objects,r,state)
  for o in list(bpy.data.objects):
   if o.type=='MESH'and o.get('asset_group')==cfg['asset_id']:o.hide_render=o.name not in names[state]
  dst=W/'inspection/state-models'/state;dst.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(dst/'model.blend'));write(dst/'workspace.json',cfg)
  for o in list(bpy.data.objects):
   if o.type=='MESH'and o.get('asset_group')==cfg['asset_id']:o.hide_render=base_hidden[o.name]
  path=W/'states-final/patch-008'/state;frame=json.loads((W/'input/views.json').read_text());src=l['sources']['exterior'if state=='covered'else'interior'];frame['source_sha256']=sha(src)
  rr=render_review(path,scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],asset_id=cfg['asset_id'],source_path=src,frame_manifest=frame,projection_layers=layers[state],source_mask_manifest=cfg['source_mask_manifest'],render_object_names=names[state],allow_projection_revision=True,allow_mask_revision=True)
  write(dst/'modified/views.json',json.loads((path/'views.json').read_text()))
  for p in path.iterdir():
   if p.name!='views.json':(dst/'modified'/p.name).symlink_to(p.resolve(),target_is_directory=p.is_dir())
  state_records.append({'patch_id':'patch-008','state':state,'path':str(path),'visibility_review':visibility,'view_sha256':sha(path/'views.json'),'object_names':rr['object_names']});bindings.append({'state':state,'model':str(dst/'model.blend'),'model_sha256':sha(dst/'model.blend'),'frame_manifest':str(path/'views.json'),'frame_manifest_sha256':sha(path/'views.json'),'object_names':names[state]})
 write(W/'states-final/states.json',{'version':1,'asset_id':cfg['asset_id'],'states':state_records});write(W/'state-packet.json',{'version':1,'directory':str(W/'states-final'),'revealed_input':'input'});write(W/'inspection/state-models/manifest.json',{'version':1,'primary_model_sha256':sha(W/'model.blend'),'states':bindings,'material_states_sha256':sha(W/'material-states.json')})
 bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'))
 if '--authoring' in sys.argv:
  assert 'round-41' in W.parts
  write(W/'validation.json',{'status':'authoring-only-not-ready','reason':'Mask authority evolved after frozen input; final round42 must freeze final authority and pass ordinary validation.'})
 else:write(W/'validation.json',validate(W))
 print('HALL COMPLETE STATE PACKETS READY FOR QA',str(W),flush=True)
if __name__=='__main__':main()
