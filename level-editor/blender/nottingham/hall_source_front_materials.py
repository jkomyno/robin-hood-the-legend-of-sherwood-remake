"""Compare actual saved hall materials with original art at the exact source camera."""
import sys,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
import bpy
from mathutils import Matrix,Vector
from PIL import Image,ImageDraw
args=sys.argv[sys.argv.index('--')+1:];w=Path(args[0]).resolve();out=w/'inspection'/args[1];out.mkdir(parents=True,exist_ok=True);states=Path(json.loads((w/'state-packet.json').read_text())['directory']);cfg=json.loads((w/'workspace.json').read_text());layers=json.loads((w/'projection-layers.json').read_text());box=(220,175,780,1320);width,height=box[2]-box[0],box[3]-box[1];s,c=math.sin(math.radians(35)),math.cos(math.radians(35))
bindings=[]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
for st in json.loads((states/'states.json').read_text())['states']:
 selected=w/'inspection/state-models'/st['state']/'model.blend'if(w/'material-states.json').exists()else w/'model.blend';bpy.ops.wm.open_mainfile(filepath=str(selected));scene=bpy.data.scenes.new('Hall exact source materials');bpy.context.window.scene=scene
 for name in st['object_names']:
  obj=bpy.data.objects[name];copy=obj.copy();mat=obj.matrix_world.copy();copy.parent=None;copy.matrix_world=mat;copy.hide_render=False;copy.hide_viewport=False;scene.collection.objects.link(copy);copy.hide_set(False)
 scene.render.engine='CYCLES';scene.cycles.samples=1;scene.cycles.use_denoising=False;scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';world=bpy.data.worlds.new('Source black');world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(0,0,0,1);scene.world=world
 camera=bpy.data.objects.new('Exact source camera',bpy.data.cameras.new('Exact source camera'));scene.collection.objects.link(camera);camera.data.type='ORTHO';camera.data.sensor_fit='VERTICAL';camera.data.ortho_scale=height;camera.data.clip_end=100000;center=Vector(((box[0]+box[2])/2,-(box[1]+box[3])/2*s,-(box[1]+box[3])/2*c))+Vector((0,-c,s))*10000;camera.matrix_world=Matrix(((1,0,0,center.x),(0,s,-c,center.y),(0,c,s,center.z),(0,0,0,1)));scene.camera=camera
 dest=out/(st['state']+'-actual.png');scene.render.filepath=str(dest);bpy.ops.render.render(write_still=True)
 src=Image.open(layers['sources']['exterior'if st['state']=='covered'else'interior']).convert('RGB').crop(box);actual=Image.open(dest).convert('RGB');sheet=Image.new('RGB',(width*2,height+22));sheet.paste(src,(0,22));sheet.paste(actual,(width,22));ImageDraw.Draw(sheet).text((5,4),st['state']+' source / actual saved materials (foreign assets omitted)',fill='white');sheet.save(out/(st['state']+'-comparison.png'))

 bindings.append({'state':st['state'],'model':str(selected),'model_sha256':sha(selected),'frame_manifest_sha256':sha(Path(st['path'])/'views.json'),'source_sha256':sha(layers['sources']['exterior'if st['state']=='covered'else'interior']),'actual_sha256':sha(dest),'comparison_sha256':sha(out/(st['state']+'-comparison.png'))})
(out/'manifest.json').write_text(json.dumps({'primary_model_sha256':sha(w/'model.blend'),'modified_views_sha256':sha(w/'modified/views.json'),'crop':box,'states':bindings},indent=2)+'\n')
