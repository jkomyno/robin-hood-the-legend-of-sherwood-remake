"""Frame the unchanged saved crown closely at all eight original view directions."""
import sys,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement';W=R/'round-38/assets/nottingham-castle-gate-west-tower';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(R/'tooling/58744eeaf71a21e9')
import bpy
from mathutils import Vector,Matrix
from refinement_review import _tile
from experiment_multiview_texture import _solid_views
from review_sunlight import configuration
bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'));c=json.loads((W/'workspace.json').read_text());scene=bpy.data.scenes[c['scene_name']];bpy.context.window.scene=scene;objects=[o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH'and o.get('asset_group')==W.name];co=math.cos(math.radians(35));points=[o.matrix_world@v.co for o in objects for v in o.data.vertices if (o.matrix_world@v.co).z*co>=330];target=sum(points,Vector())/len(points);frames=json.loads((W/'modified/views.json').read_text());scene.render.resolution_x=scene.render.resolution_y=384;scene.render.resolution_percentage=100;output=W/'inspection/crown-closeup';output.mkdir(exist_ok=True);cameras=[]
for f in frames['views']:
 cam=bpy.data.objects.new('Crown closeup camera',bpy.data.cameras.new('Crown closeup camera'));scene.collection.objects.link(cam);cam.data.type='ORTHO';cam.data.clip_end=100000;mat=Matrix(f['camera_matrix_world']);direction=mat.to_3x3()@Vector((0,0,-1));cam.matrix_world=mat;cam.location=target-direction*10000;bpy.context.view_layer.update();inverse=cam.matrix_world.inverted();screen=[inverse@p for p in points];cx=(max(p.x for p in screen)+min(p.x for p in screen))/2;cy=(max(p.y for p in screen)+min(p.y for p in screen))/2;cam.location+=cam.matrix_world.to_3x3()@Vector((cx,cy,0));cam.data.ortho_scale=max(max(p.x for p in screen)-min(p.x for p in screen),max(p.y for p in screen)-min(p.y for p in screen))*1.16;cameras.append(cam)
bpy.context.view_layer.update();buffers=_solid_views(scene,cameras,objects,output,lighting=configuration(frames.get('lighting')));_tile(buffers,384,384,output/'solid.png');(output/'manifest.json').write_text(json.dumps(dict(model_sha256=hashlib.sha256((W/'model.blend').read_bytes()).hexdigest(),geometry_unchanged=True,lighting=frames.get('lighting'),framing='Supplemental camera fit to saved vertices at native height330 and above; original eight yaw directions. Complete meshes unchanged, lower geometry extends below close-up frame.'),indent=2)+'\n')
