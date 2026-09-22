import sys,json
from pathlib import Path
workspace=Path(__file__).resolve().parent
scripts=workspace.parents[4]/'blender'
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages',str(scripts)]
import bpy
from refinement_workspace import _reproject,_review_layers,_mission_review_source
from refinement_review import render_review
from review_sunlight import DEFAULT_LIGHTING
from derby_round2_lower_west_split import apply_mapping
from derby_round2_lower_west_wall_partition import partition,SECTIONS
config=json.loads((workspace/'workspace.json').read_text())
output=workspace/'inspection'/'complete-wall-candidate-v3'
output.mkdir(parents=True,exist_ok=True)
_reproject(config,output/'projection')
bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
apply_mapping(scripts/'derby-lower-west-split.json')
report=partition()
(output/'partition.json').write_text(json.dumps(report,indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(output/'grouped-model.blend'))
for side,(identifier,name,numbers) in SECTIONS.items():
 frame=workspace/'wall-partition'/'review'/identifier/'views.json'
 render_review(output/side,scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=identifier,
     source_path=_mission_review_source(config) or config['source_path'],frame_manifest=frame if frame.exists() else None,
     projection_layers=_review_layers(config),source_mask_manifest=config['source_mask_manifest'],width=512,height=512,
     lighting={**DEFAULT_LIGHTING,'toward_sun':[-0.4916794601,-0.4538579920,0.7431448255]})
