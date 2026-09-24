"""Record provisional source-shadow landmarks and render isolated light comparisons."""
import hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement';OUT=R/'lighting-calibration'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def evidence():
 pairs=[{'caster':[786,1218],'shadow':[670,1298]},{'caster':[807,1215],'shadow':[695,1291]},{'caster':[839,1216],'shadow':[724,1297]}]
 h=436.54656982421875-122.07908630371094;s=math.sin(math.radians(35));c=math.cos(math.radians(35))
 def direction(dx,dy):
  v=[-dx/h,(dy/h-c)/s,1];length=sum(t*t for t in v)**.5;v=[t/length for t in v];return v,math.degrees(math.atan2(v[1],v[0])),math.degrees(math.asin(v[2]))
 dx=sum(p['shadow'][0]-p['caster'][0]for p in pairs)/3;dy=sum(p['shadow'][1]-p['caster'][1]for p in pairs)/3
 v,az,el=direction(dx,dy);bounds=[direction(dx+x,dy+y)for x in [-10,10]for y in [-10,10]]
 report=dict(status='PROVISIONAL-SOURCE-ESTIMATE',source_sha256=sha(R/'source-states/covered.png'),model_sha256=sha(R/'round-25/assets/nottingham-castle-gate-west-tower/model.blend'),pairs=pairs,confidence='medium: blurred edges and painted/model crown shape differences; each endpoint ±5 source pixels',caster_world_z=436.54656982421875,receiver_world_z=122.07908630371094,source_camera_elevation=35,mean_pixel_displacement=[dx,dy],toward_sun=v,azimuth_degrees=az,elevation_degrees=el,conservative_endpoint_bounds={'azimuth':[min(a[1]for a in bounds),max(a[1]for a in bounds)],'elevation':[min(a[2]for a in bounds),max(a[2]for a in bounds)]},limitations=['Three landmarks share one caster and receiver plane; not three independent structures.','Second east-gate caster casts leftward consistently, but crown/gallery occlusion prevents reliable independent endpoint measurement.','Foliage, reeds, AO, paving cracks, rock and painted facade shading excluded.','No directional vector recovered from inspected map light-sector loader; sector data describe gameplay shadow regions.','Finite point source remains underconstrained; cannot distinguish a distant point light from directional sunlight from this single caster.','Not a production-light validation. Receiver/caster geometry error adds uncertainty beyond endpoint bounds.','Preview contains isolated west tower and receiving courtyard only; neighboring architecture intentionally absent.'],production_defaults_changed=False)
 (OUT/'estimate.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 d=evidence()
 if '--render' in sys.argv:
  import bpy
  from mathutils import Vector
  sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
  from review_sunlight import render_solids,DEFAULT_LIGHTING
  sys.path.insert(0,str(Path(__file__).parent))
  from render_slots import acquire
  acquire()
  p=R/'round-25/assets/nottingham-castle-gate-west-tower';w=json.loads((p/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(p/'model.blend'));scene=bpy.context.scene
  objects=[o for o in bpy.data.collections[w['collection_name']].all_objects if o.type=='MESH' and (o.get('asset_group')=='nottingham-castle-gate-west-tower' or o.get('source_node')=='building-366')]
  scene.render.resolution_x=500;scene.render.resolution_y=520;scene.render.pixel_aspect_x=1;scene.render.pixel_aspect_y=1
  angle=math.radians(35);down=Vector((0,-math.sin(angle),-math.cos(angle)));toward=Vector((0,-math.cos(angle),math.sin(angle)));center=Vector((775,0,0))+down*1420
  cam=bpy.data.objects.new('Calibration camera',bpy.data.cameras.new('Calibration camera'));scene.collection.objects.link(cam);cam.data.type='ORTHO';cam.data.ortho_scale=520;cam.location=center+toward*10000;cam.rotation_euler=(-toward).to_track_quat('-Z','Y').to_euler();bpy.context.view_layer.update()
  for name,light in [('derby',DEFAULT_LIGHTING),('nottingham-estimate',{'toward_sun':d['toward_sun']})]:
   out=OUT/name;out.mkdir(exist_ok=True);render_solids(scene,[cam],objects,out,lighting=light)

  # No model save: comparison outputs cannot alter approved geometry or materials.
 else:
  from PIL import Image,ImageDraw
  src=Image.open(R/'source-states/covered.png').convert('RGB')
  box=(610,1190,905,1380);im=src.crop(box).resize((1180,760));draw=ImageDraw.Draw(im)
  for number,(pair,color) in enumerate(zip(d['pairs'],['cyan','magenta','lime']),1):
   points=[((pair[key][0]-box[0])*4,(pair[key][1]-box[1])*4)for key in ['caster','shadow']];draw.line(points,fill=color,width=2)
   for kind,(x,y)in zip(['C','S'],points):
    draw.ellipse((x-5,y-5,x+5,y+5),outline=color,width=2);draw.text((x+7,y),str(number)+kind,fill=color,stroke_width=1,stroke_fill='black')
  im.save(OUT/'provisional-pairs.png')
  if (OUT/'nottingham-estimate/view-0-solid.png').exists():
   sheet=Image.new('RGB',(1500,555),'white');draw=ImageDraw.Draw(sheet)
   panels=[('Original source',src.crop((525,1160,1025,1680))),('Derby default (-137.3 deg / 48 deg)',Image.open(OUT/'derby/view-0-solid.png')),('Nottingham estimate (-69.8 deg / 43.5 deg)',Image.open(OUT/'nottingham-estimate/view-0-solid.png'))]
   for i,(label,panel)in enumerate(panels):
    sheet.paste(panel.convert('RGB'),(i*500,35));draw.text((i*500+8,10),label,fill='black')
   sheet.save(OUT/'source-lighting-comparison.png')
