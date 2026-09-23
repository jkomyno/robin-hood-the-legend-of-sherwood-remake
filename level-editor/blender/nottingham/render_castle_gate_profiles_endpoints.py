"""Render independent initial/applied gateway endpoint evidence without mutating its model."""
import sys,json,copy,hashlib
from pathlib import Path
import bpy
root=Path(__file__).resolve().parents[3]/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(root/'tooling/58744eeaf71a21e9'))
sys.path.insert(0,str(Path.cwd()/'level-editor/blender/nottingham'))
from render_slots import acquire
acquire()
from refinement_workspace import _review_layers,validate
from refinement_review import render_review
from source_projection_bake import bake
asset=sys.argv[sys.argv.index('--')+1];w=root/'round-23/assets'/asset
bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'))
config=json.loads((w/'workspace.json').read_text());tower=asset.endswith('east-tower');node='building-337' if tower else 'building-333';patch='patch-005' if tower else 'patch-003';stem='mechanism' if tower else 'portcullis'
objects=list(bpy.data.collections[config['collection_name']].all_objects);owned=[o for o in objects if o.type=='MESH' and o.get('asset_group')==asset]
for o in owned:
 if o.get('source_node')==node:
  o['reveal_component_patch_id']=patch
  if not o.get('projection_component'):o['projection_component']='gate-masonry'
original={o:o.hide_render for o in owned}
records=[]
for state in ['initial','applied']:
 label=stem+'-'+state
 for o in owned:
  o.hide_render= bool(o.get('animation_state') and o['animation_state']!=state) or (tower and o.get('projection_component')=='mechanism-removable-cover')
 bpy.context.view_layer.update()
 defs=_review_layers(config)
 for d in defs:
  if node in d['receiver_nodes']:
   components=[o.get('projection_component') for o in owned if o.get('source_node')==node and not o.get('animation_state')]
   selectors=d.setdefault('receiver_components',[])
   existing=next((s for s in selectors if s['source_node']==node),None)
   if existing:existing['projection_components']=[c for c in existing['projection_components'] if not c.startswith(stem+'-initial') and not c.startswith(stem+'-applied')]
   else:selectors.append({'source_node':node,'projection_components':components,'patch_id':patch})
 source=root/'state-review/owned-masks'/(label+'-source.png')
 endpoint={'source_path':str(source),'projection_label':label,'receiver_nodes':[node],'occluder_nodes':[node], 'receiver_components':[{'source_node':node,'projection_components':[label],'patch_id':patch}]}
 defs.append(endpoint)
 out=w/'inspection/endpoints-v5'/label
 result=bake('nottingham',source,w/'inspection/endpoints-v5'/(label+'-ownership.json'),receiver_nodes=[node],occluder_nodes=[node],projection_label=label,source_mask_manifest=config['source_mask_manifest'],receiver_components=endpoint['receiver_components'],preserve_authored=False)
 frame=copy.deepcopy(json.loads((w/'input/views.json').read_text()));frame['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
 names=[o.name for o in owned if not o.hide_render]
 render_review(out,scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=asset,source_path=source,frame_manifest=frame,projection_layers=defs,source_mask_manifest=config['source_mask_manifest'],render_object_names=names,allow_projection_revision=True,allow_mask_revision=True)
 # Full-height supplement supplements, rather than replaces, fixed input cameras.
 render_review(out/'full-height',scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=asset,source_path=source,width=320,height=480,projection_layers=defs,source_mask_manifest=config['source_mask_manifest'],render_object_names=names)
 records.append({'state':state,'path':str(out),'source_sha256':frame['source_sha256'],'ownership':result})
for o,hidden in original.items():o.hide_render=hidden
# Endpoint projection is disposable; retain the base covered model material.
(w/'inspection/endpoints-v5/states.json').write_text(json.dumps({'asset_id':asset,'states':records,'approval':'pending','limitation':'Discrete source silhouettes; hidden extrusion depth inferred; no 3D transitional motion or collision claim.'},indent=2)+'\n')
print(validate(w),flush=True)
