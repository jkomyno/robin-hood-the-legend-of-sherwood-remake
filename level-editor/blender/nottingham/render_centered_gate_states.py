"""Save and inspect both endpoint models for each member of the gate pair."""
import sys,json,copy,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from refinement_workspace import _review_layers
 from refinement_review import render_review
 from source_projection_bake import bake
 from audit_stored_materials import run
 for asset in ['nottingham-castle-gate-arch','nottingham-castle-gate-east-tower']:
  if '--' in sys.argv and sys.argv[sys.argv.index('--')+1] not in asset:continue
  tower=asset.endswith('east-tower');w=WORK/('round-42/assets' if tower else 'round-39/assets')/asset;config=json.loads((w/'workspace.json').read_text());node='building-337' if tower else 'building-333';patch='patch-005' if tower else 'patch-003';stem='mechanism' if tower else 'portcullis';records=[]
  for state in ['initial','applied']:
   bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();owned=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and o.get('asset_group')==asset]
   for o in owned:
    if o.get('source_node')==node:
     o['reveal_component_patch_id']=patch
     if not o.get('projection_component'):o['projection_component']='gate-masonry'
    o.hide_render=bool(o.get('animation_state') and o['animation_state']!=state) or (tower and o.get('projection_component')=='mechanism-removable-cover');o.hide_set(o.hide_render)
   bpy.context.view_layer.update();defs=_review_layers(config)
   for d in defs:
    if node not in d['receiver_nodes']:continue
    components=[o.get('projection_component')for o in owned if o.get('source_node')==node and not o.get('animation_state')];selectors=d.setdefault('receiver_components',[]);existing=next((s for s in selectors if s['source_node']==node),None)
    if existing:existing['projection_components']=[c for c in existing['projection_components']if c not in [stem+'-initial',stem+'-applied']]
    else:selectors.append(dict(source_node=node,projection_components=components,patch_id=patch))
   label=stem+'-'+state;source=WORK/'state-review/owned-masks'/(label+'-source.png');out=w/'inspection/endpoints-v6'/label;out.parent.mkdir(parents=True,exist_ok=True)
   endpoint=dict(source_path=str(source),projection_label=label,receiver_nodes=[node],occluder_nodes=[node],receiver_components=[dict(source_node=node,projection_components=[label],patch_id=patch)]);defs.append(endpoint)
   bake('nottingham',source,out.parent/(label+'-ownership.json'),receiver_nodes=[node],occluder_nodes=[node],projection_label=label,source_mask_manifest=config['source_mask_manifest'],receiver_components=endpoint['receiver_components'],preserve_authored=False)
   frame=copy.deepcopy(json.loads((w/'input/views.json').read_text()));frame['source_sha256']=sha(source);names=[o.name for o in owned if not o.hide_render]
   render_review(out,scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=asset,source_path=source,frame_manifest=frame,projection_layers=defs,source_mask_manifest=config['source_mask_manifest'],render_object_names=names,allow_projection_revision=True,allow_mask_revision=True)
   render_review(out/'full-height',scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=asset,source_path=source,width=320,height=480,projection_layers=defs,source_mask_manifest=config['source_mask_manifest'],render_object_names=names)
   bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));(out/'workspace.json').write_text(json.dumps(config,indent=2)+'\n')
   audit=run(out,out/'stored-materials',render=True,export=False,render_object_names=names,frame_manifest=out/'views.json')
   records.append(dict(id=label,directory=str(out),model=str(out/'model.blend'),model_sha256=sha(out/'model.blend'),views=str(out/'views.json'),views_sha256=sha(out/'views.json'),actual_materials=str(out/'stored-materials/materials.png'),actual_materials_sha256=sha(out/'stored-materials/materials.png'),audit_status=audit['status']))
  (w/'inspection/endpoints-v6/states.json').write_text(json.dumps(dict(base_model_sha256=sha(w/'model.blend'),states=records,limitation='Discrete source endpoint silhouettes retained exactly; no interpolated 3D motion is inferred.'),indent=2)+'\n');print('ENDPOINTS_COMPLETE',asset,flush=True)
if __name__=='__main__':main()
