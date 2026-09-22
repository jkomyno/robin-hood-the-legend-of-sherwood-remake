"""Reproject both cap edges and make eight-view plus exact source-camera reviews."""
import sys,json,math
from pathlib import Path
root=Path(__file__).resolve().parent;scripts=root.parents[4]/'blender'
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages',str(scripts)]
import bpy
from mathutils import Vector
from refinement_workspace import _reproject,_review_layers,_mission_review_source
import refinement_review
from review_sunlight import DEFAULT_LIGHTING
from derby_round2_lower_west_split import apply_mapping
from derby_round2_lower_west_wall_partition import partition
out=root/'inspection/south-cap-fit-v9'
config=json.loads((root/'inspection/complete-wall-candidate-v4/review-workspace/workspace.json').read_text())
_reproject(config,out/'projection')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
apply_mapping(scripts/'derby-lower-west-split.json')
(out/'partition.json').write_text(json.dumps(partition(),indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'grouped-model.blend'))
kwargs=dict(scene_name=config['scene_name'],collection_name=config['collection_name'],
    asset_id='derby-lower-west-curtain-south',source_path=_mission_review_source(config) or config['source_path'],
    projection_layers=_review_layers(config),source_mask_manifest=config['source_mask_manifest'],
    lighting={**DEFAULT_LIGHTING,'toward_sun':[-0.4916794601,-0.4538579920,0.7431448255]})
refinement_review.render_review(out/'modified',frame_manifest=root/'inspection/complete-wall-candidate-v5/south-48/views.json',**kwargs)
# Use the same source-only ownership sampler for a one-camera diagnostic.
namespace={'__file__':refinement_review.__file__}
code=Path(refinement_review.__file__).read_text().replace('for index in range(8):','for index in range(1):')
exec(compile(code,refinement_review.__file__,'exec'),namespace)
for node,box in [('023',[320,1812,388,1978]),('042',[390,2118,531,2246])]:
    frame=json.loads((out/'modified/views.json').read_text());scale=4
    sn,cs=math.sin(math.radians(35)),math.cos(math.radians(35))
    cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
    target=Vector((cx,-cy/sn,0));camera=target+Vector((0,-cs,sn))*10000
    frame['tile_size']=[(box[2]-box[0])*scale,(box[3]-box[1])*scale]
    frame['context_crop']=dict(zip(('left','top','right','bottom'),box))
    frame['views'][0].update(camera_location=list(camera),camera_rotation_euler=list((target-camera).to_track_quat('-Z','Y').to_euler()),ortho_scale=box[3]-box[1])
    namespace['render_review'](out/f'source-camera-{node}',frame_manifest=frame,**kwargs)
