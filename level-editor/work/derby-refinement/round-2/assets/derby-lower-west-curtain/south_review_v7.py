"""Reproject and render the south-only corner fit without changing other assets."""
import sys,json
from pathlib import Path
root=Path(__file__).resolve().parent
scripts=root.parents[4]/'blender'
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages',str(scripts)]
import bpy
from refinement_workspace import _reproject,_review_layers,_mission_review_source
from refinement_review import render_review
from review_sunlight import DEFAULT_LIGHTING
from derby_round2_lower_west_split import apply_mapping
from derby_round2_lower_west_wall_partition import partition
out=root/'inspection/south-corner-fit-v7'
config=json.loads((root/'inspection/complete-wall-candidate-v4/review-workspace/workspace.json').read_text())
_reproject(config,out/'projection')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
apply_mapping(scripts/'derby-lower-west-split.json')
(out/'partition.json').write_text(json.dumps(partition(),indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'grouped-model.blend'))
render_review(out/'modified',scene_name=config['scene_name'],collection_name=config['collection_name'],
    asset_id='derby-lower-west-curtain-south',source_path=_mission_review_source(config) or config['source_path'],
    frame_manifest=root/'inspection/complete-wall-candidate-v5/south-48/views.json',
    projection_layers=_review_layers(config),source_mask_manifest=config['source_mask_manifest'],
    lighting={**DEFAULT_LIGHTING,'toward_sun':[-0.4916794601,-0.4538579920,0.7431448255]})
