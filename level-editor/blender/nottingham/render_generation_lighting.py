"""Immutable generation-only lighting, preserving approved packet identity."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--asset',action='append');p.add_argument('--state-proof',type=Path);p.add_argument('--approve-inspected',action='store_true');args=p.parse_args(sys.argv[sys.argv.index('--')+1:]if '--'in sys.argv else None)
 audit=json.loads((WORK/'texture-generation/lighting-audit/audit.json').read_text());config=WORK/'lighting-calibration/map-lighting.json';light=json.loads(config.read_text())['lighting'];out=WORK/'texture-generation/lighting'
 if args.approve_inspected:
  from PIL import Image,ImageChops
  assert args.asset,'Explicit visually inspected assets required'
  for aid in args.asset:
   report=out/aid/'review.json';d=json.loads(report.read_text());assert d['status']!='blocked-missing-state-proof'
   assert sha(config)==d['lighting_config_sha256']
   source=next(r for r in audit['packets']if r['asset_id']==aid);workspace=Path(source['workspace'])
   assert sha(workspace/'model.blend')==d['model_sha256']
   assert sha(workspace/'modified/views.json')==d['modified_views_sha256']
   for packet in d['packets']:
    for key in ['frame_manifest','source_blend','solid','original_solid']:assert sha(packet[key])==packet[key+'_sha256']
    for key in ['state_binding','material_audit']:
     if packet.get(key):assert sha(packet[key])==packet[key+'_sha256']
    original=Image.open(packet['original_solid']).convert('RGBA');solid=Image.open(packet['solid']).convert('RGBA');assert original.size==solid.size
    assert ImageChops.difference(original.getchannel('A'),solid.getchannel('A')).getbbox()is None,'Silhouette drift'
    tilew,tileh=json.loads(Path(packet['frame_manifest']).read_text())['tile_size']
    for i,v in enumerate(packet['solid_view_paths']):
     assert sha(v)==packet['solid_view_sha256'][i]
     tile=Image.open(v).convert('RGBA');expected=solid.crop(((i%4)*tilew,(i//4)*tileh,(i%4+1)*tilew,(i//4+1)*tileh));assert ImageChops.difference(tile,expected).getbbox()is None,'Sheet tile mismatch'
    packet['inspected_views']=list(range(8));packet['alpha_preserved_exactly']=True
   d['status']='PASS';write(report,d)
  return
 rows=[r for r in audit['packets']if any(k!='primary'and not k.endswith('-full-height')for k in r['roles'])and(not args.asset or r['asset_id']in args.asset)]
 assets={}
 for r in rows:assets.setdefault(r['asset_id'],[]).append(r)
 import bpy
 from mathutils import Matrix
 sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'));sys.path.insert(0,str(Path(__file__).parent))
 from review_sunlight import render_solids
 from refinement_review import _tile
 from generation_material_audits import existing as existing_material_audit, run_loaded
 from render_slots import acquire
 acquire()
 proof=json.loads(args.state_proof.read_text())if args.state_proof else None
 for aid,packets in assets.items():
  dest=out/aid;report=dest/'review.json';w=Path(packets[0]['workspace']);primary=w/'model.blend';primarysha=sha(primary);assert primarysha==packets[0]['model_sha256'],'Approved model drift'
  result=dict(version=1,status='awaiting-technical-visual-inspection',asset_id=aid,model_sha256=primarysha,modified_views_sha256=sha(w/'modified/views.json'),lighting_config=str(config),lighting_config_sha256=sha(config),lighting=light,authorization_scope='generation-only derived lighting; geometry approval unchanged',packets=[])
  if report.exists():
   previous=json.loads(report.read_text());assert previous['model_sha256']==primarysha and previous['lighting_config_sha256']==sha(config)
   for r in previous['packets']:
    assert sha(r['frame_manifest'])==r['frame_manifest_sha256']and sha(r['solid'])==r['solid_sha256']and sha(r['source_blend'])==r['source_blend_sha256']
   if len(previous['packets'])==len(packets) and all(existing_material_audit(r) for r in packets if r.get('saved_state_model')) and all(r.get('saved_state_model') for r in packets):print('REUSE',aid,flush=True);continue
  for row in packets:
   frame=Path(row['frame_manifest']);f=json.loads(frame.read_text());assert sha(frame)==row['frame_manifest_sha256'],'Approved frame drift'
   model=Path(row['saved_state_model'])if row['saved_state_model']else None
   binding_file=None;binding=None
   if model is None:
    binding_file=args.state_proof or WORK/'texture-generation/state-proof'/aid/'state-bindings.json'
    if binding_file.exists():
     binding=next((s for s in json.loads(binding_file.read_text())['states']if s['frame_manifest']==str(frame)),None)
    if binding is None:
     print('WAIT-STATE-PROOF',aid,str(frame),flush=True);continue
    assert binding['status']=='PASS'and binding['frame_manifest_sha256']==sha(frame)
    assert set(binding['render_object_names'])==set(f['object_names'])
    model=Path(binding['source_blend'])
   modelsha=sha(model);assert modelsha==(binding['source_blend_sha256']if binding else row['saved_state_model_sha256']);tag='--'.join(frame.parent.relative_to(w).parts);target=dest/tag
   original=frame.parent/'solid.png';originalsha=sha(original)
   material_row=dict(row,saved_state_model=str(model),saved_state_model_sha256=modelsha)
   material_audit=existing_material_audit(material_row)
   loaded=False
   if material_audit is None:
    bpy.ops.wm.open_mainfile(filepath=str(model));loaded=True
    material_audit=Path(run_loaded(material_row))

   if row['effective_nottingham_lighting']:
    solid=Path(row['existing_nottingham_solid']);viewpaths=[solid.parent/f'view-{i}-solid.png'for i in range(8)];reuse=True
   else:
    target.mkdir(parents=True,exist_ok=True);solid=target/'solid.png';viewpaths=[target/f'view-{i}-solid.png'for i in range(8)];reuse=False
    if not solid.exists():
     if not loaded:bpy.ops.wm.open_mainfile(filepath=str(model))
     scene=bpy.data.scenes[f['scene_name']];bpy.context.window.scene=scene
     names=set(f['object_names']);objects=[o for o in bpy.data.collections[f['collection_name']].all_objects if o.type=='MESH'and o.name in names];assert {o.name for o in objects}==names
     width,height=f['tile_size'];scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.pixel_aspect_x=scene.render.pixel_aspect_y=1;cameras=[]
     for i,v in enumerate(f['views']):
      assert i==v['index'];cam=bpy.data.objects.new('Generation light camera',bpy.data.cameras.new('Generation light camera'));scene.collection.objects.link(cam);cam.data.type='ORTHO';cam.data.ortho_scale=v['ortho_scale']
      if 'camera_location'in v:cam.location=v['camera_location'];cam.rotation_euler=v['camera_rotation_euler']
      else:cam.matrix_world=Matrix(v['camera_matrix_world'])
      cameras.append(cam)
     bpy.context.view_layer.update();buffers=render_solids(scene,cameras,objects,target,lighting=light);_tile(buffers,width,height,solid)
   assert all(v.exists()for v in viewpaths)
   assert sha(frame)==row['frame_manifest_sha256']and sha(model)==modelsha and sha(original)==originalsha
   result['packets'].append(dict(original_solid=str(original),original_solid_sha256=originalsha,frame_manifest=str(frame),frame_manifest_sha256=sha(frame),source_blend=str(model),source_blend_sha256=modelsha,solid=str(solid),solid_sha256=sha(solid),solid_view_paths=[str(v)for v in viewpaths],solid_view_sha256=[sha(v)for v in viewpaths],inspected_views=[],reused_approved_lighting=reuse,object_names=f['object_names'],state_binding=str(binding_file)if binding else None,state_binding_sha256=sha(binding_file)if binding else None,material_audit=str(material_audit),material_audit_sha256=sha(material_audit)))
  if len(result['packets'])!=len(packets):result['status']='blocked-missing-state-proof'
  assert sha(primary)==primarysha;write(report,result);print('FINISHED',aid,len(result['packets']),result['status'],flush=True)
if __name__=='__main__':main()
