import bpy,json,sys
from pathlib import Path
W=Path(__file__).parent
name=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'front-review'
O=W/'next-zigzag-v3'/name
sys.path.insert(0,str(W.parents[4]/'blender'))
from refinement_workspace import _reproject,_render,initialize_working_masks
from occlusion_constraints import evidence_record
from review_sunlight import DEFAULT_LIGHTING
config=json.loads((W/'workspace.json').read_text())
config['source_mask_manifest']=str(W/'next-casement/source-masks-reviewed.json')
# This asset's original input predates mask evidence. Start a new isolated
# checkpoint from the accepted casement review, whose hashes cover these masks.
accepted=json.loads((W/'next-casement/verified/modified/views.json').read_text())
assert accepted['source_mask_evidence']==evidence_record(Path(config['source_mask_manifest']))
authority=W/'next-zigzag-v3/authority-checkpoint'
if not authority.exists():
    (authority/'input').mkdir(parents=True)
    (authority/'input/views.json').write_text(json.dumps(accepted,indent=2))
    (authority/'workspace.json').write_text(json.dumps(config,indent=2))
initialize_working_masks(authority)
frozen=json.loads((authority/'workspace.json').read_text())
config.update({key:frozen[key] for key in ['mask_reference','mask_reference_files']})
working=json.loads(Path(config['source_mask_manifest']).read_text())
assignments=working['projections']['exterior']['assignments']
for node in ['building-192','building-194','building-198']:
    if not any(entry.get('source_node')==node for entry in assignments):
        assignments.append(dict(reviewed=True,source_node=node,mask_indices=[146],
          reason='Reviewed source-traced Hall parapet or stair-turret part lies within native whole-Hall mask146; ray ownership remains required'))
working_path=W/'next-zigzag-v3/source-masks-reviewed.json'
working_path.write_text(json.dumps(working,indent=2))
config['source_mask_manifest']=str(working_path)
config['source_blend']=str(Path(bpy.data.filepath).resolve())
frame=json.loads((W/'input/views.json').read_text());frame['lighting']=DEFAULT_LIGHTING
O.mkdir(exist_ok=True)
(O/'frame-48.json').write_text(json.dumps(frame,indent=2))
_reproject(config,O/'projection')
bpy.ops.wm.save_as_mainfile(filepath=str(O/'model.blend'))
_render(config,O/'modified',O/'frame-48.json')
