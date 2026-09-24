"""Render hash-bound supplemental solid sheets without changing frozen packets."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('workspace',type=Path);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--approve-inspected',action='store_true');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]if '--'in sys.argv else None)
 w=args.workspace.resolve();config=args.config.resolve();out=w/'lighting-review';report=out/'review.json';model=w/'model.blend';frames=w/'modified/views.json';c=json.loads(config.read_text());lighting=c['lighting']
 bindings=dict(version=1,asset_id=json.loads(frames.read_text())['asset_id'],model_sha256=sha(model),modified_views_sha256=sha(frames),lighting_config_sha256=sha(config),lighting_config=str(config),lighting=lighting)
 if args.approve_inspected:
  d=json.loads(report.read_text())
  for key,value in bindings.items():assert d[key]==value,(key,'changed since rendering')
  for packet in d['packets']:
   for filekey,hashkey in [('frame_manifest','frame_manifest_sha256'),('solid','solid_sha256'),('source_blend','source_blend_sha256'),('original_solid','original_solid_sha256')]:assert sha(packet[filekey])==packet[hashkey],filekey
   packet['inspected_views']=list(range(8))
  d['status']='PASS';write(report,d);return
 import bpy
 from mathutils import Matrix
 sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'));sys.path.insert(0,str(Path(__file__).parent))
 from review_sunlight import render_solids
 from refinement_review import _tile
 from render_slots import acquire
 acquire();out.mkdir(exist_ok=True)
 if report.exists():raise FileExistsError(report)
 packets=[]
 for label,blend in [('input',w/'baseline.blend'),('modified',model)]:
  frame=w/label/'views.json';f=json.loads(frame.read_text());assert len(f['views'])==8
  bpy.ops.wm.open_mainfile(filepath=str(blend));scene=bpy.data.scenes[f['scene_name']];bpy.context.window.scene=scene
  all_objects=list(bpy.data.collections[f['collection_name']].all_objects)
  names=set(f['object_names']);objects=[o for o in all_objects if o.type=='MESH'and o.name in names]
  assert {o.name for o in objects}==names,'Exact frame object selection absent in supplied saved state'
  if f.get('render_object_names') is not None:assert names==set(f['render_object_names']),'State selection differs'
  width,height=f['tile_size'];scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.pixel_aspect_x=scene.render.pixel_aspect_y=1
  cameras=[]
  for i,v in enumerate(f['views']):
   assert v['index']==i;camera=bpy.data.objects.new('Supplement camera',bpy.data.cameras.new('Supplement camera'));scene.collection.objects.link(camera);camera.data.type='ORTHO';camera.data.ortho_scale=v['ortho_scale']
   if 'camera_location'in v:camera.location=v['camera_location'];camera.rotation_euler=v['camera_rotation_euler']
   else:camera.matrix_world=Matrix(v['camera_matrix_world'])
   cameras.append(camera)
  bpy.context.view_layer.update();target=out/label;target.mkdir();buffers=render_solids(scene,cameras,objects,target,lighting=lighting);solid=target/'solid.png';_tile(buffers,width,height,solid)
  packets.append(dict(original_solid=str(w/label/'solid.png'),original_solid_sha256=sha(w/label/'solid.png'),frame_manifest=str(frame),frame_manifest_sha256=sha(frame),solid=str(solid),solid_sha256=sha(solid),source_blend=str(blend),source_blend_sha256=sha(blend),inspected_views=[],object_names=sorted(names),camera_contract='Exact stored frame location, rotation, scale, tile size and ordered eight views'))
 assert sha(model)==bindings['model_sha256'];assert sha(frames)==bindings['modified_views_sha256'];assert sha(config)==bindings['lighting_config_sha256']
 write(report,{**bindings,'status':'awaiting-independent-visual-inspection','packets':packets,'scope':'Only input/modified main solid sheets. State variants require separately verified saved state geometry; never substituted by main scene.'})
if __name__=='__main__':main()
