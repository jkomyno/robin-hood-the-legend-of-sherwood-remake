"""One authoritative source-camera crop, using the standard review sampler."""
import sys,json,math
from pathlib import Path
root=Path(__file__).resolve().parent;scripts=root.parents[4]/'blender'
sys.path[:0]=['/usr/lib/python3.14','/usr/lib/python3.14/lib-dynload','/usr/lib/python3.14/site-packages',str(scripts)]
import bpy
from mathutils import Vector
from refinement_workspace import _review_layers,_mission_review_source
from review_sunlight import DEFAULT_LIGHTING
import refinement_review
out=root/'inspection/north-corner-v7'
config=json.loads((root/'inspection/complete-wall-candidate-v4/review-workspace/workspace.json').read_text())
frame=json.loads((out/'north-48/views.json').read_text())
box=[310,1525,412,1770];scale=4
cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
sn,cs=math.sin(math.radians(35)),math.cos(math.radians(35))
target=Vector((cx,-cy/sn,0));camera=target+Vector((0,-cs,sn))*10000
frame['tile_size']=[(box[2]-box[0])*scale,(box[3]-box[1])*scale]
frame['context_crop']=dict(zip(('left','top','right','bottom'),box))
frame['views'][0].update(camera_location=list(camera),camera_rotation_euler=list((target-camera).to_track_quat('-Z','Y').to_euler()),ortho_scale=box[3]-box[1])
# Run the same ownership/material-free ray sampler with one camera. The normal
# eight-camera function and files are untouched; only this diagnostic is single-view.
namespace={'__file__':refinement_review.__file__}
code=Path(refinement_review.__file__).read_text().replace('for index in range(8):','for index in range(1):')
exec(compile(code,refinement_review.__file__,'exec'),namespace)
namespace['render_review'](out/'source-camera',scene_name=config['scene_name'],collection_name=config['collection_name'],asset_id=frame['asset_id'],
 source_path=_mission_review_source(config) or config['source_path'],frame_manifest=frame,
 projection_layers=_review_layers(config),source_mask_manifest=config['source_mask_manifest'],
 lighting={**DEFAULT_LIGHTING,'toward_sun':[-0.4916794601,-0.4538579920,0.7431448255]},allow_mask_revision=True)
