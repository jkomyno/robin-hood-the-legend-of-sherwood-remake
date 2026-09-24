"""Regroup the west terrace parapet into the hall without altering reviewed mesh data."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
ASSET='nottingham-castle-main-hall';OLD=WORK/'round-3/assets'/ASSET;OUT=WORK/'round-38/assets'/ASSET
DONOR=WORK/'approval-evidence'/ASSET/'93e9c6135584/model.blend';STAIR=WORK/'round-26/assets/nottingham-castle-west-stair-tower/model.blend'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,indent=2)+'\n')
def ident(o):return o.get('source_node')+'|'+o.get('projection_component','')
def fingerprint(o):
 from array import array
 def scalar(v):
  try:return list(v) if not isinstance(v,(str,int,float,bool)) else v
  except TypeError:return str(v)
 def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,default=str).encode()).hexdigest()
 mats=[]
 for m in o.data.materials:
  if m is None:mats.append(None);continue
  nodes=[]
  for n in m.node_tree.nodes if m.use_nodes else []:
   d={'type':n.bl_idname,'name':n.name,'inputs':[(s.name,scalar(s.default_value))for s in n.inputs if hasattr(s,'default_value')]}
   for attr in ['uv_map','interpolation','extension','operation','blend_type']:
    if hasattr(n,attr):d[attr]=getattr(n,attr)
   if n.type=='TEX_IMAGE' and n.image:
    im=n.image;a=array('f',[0])*(im.size[0]*im.size[1]*4);im.pixels.foreach_get(a)
    d['image']={'size':list(im.size),'pixels':hashlib.sha256(a.tobytes()).hexdigest(),'colorspace':im.colorspace_settings.name,'alpha':im.alpha_mode,'packed_bytes':hashlib.sha256(im.packed_file.data).hexdigest()if im.packed_file else None}
   nodes.append(d)
  mats.append({'diffuse':list(m.diffuse_color),'use_nodes':m.use_nodes,'properties':{k:str(m[k])for k in m.keys()},'nodes':nodes,'links':[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name)for l in m.node_tree.links]if m.use_nodes else []})
 return {'geometry':digest({'vertices':[list(v.co)for v in o.data.vertices],'faces':[list(p.vertices)for p in o.data.polygons],'matrix':[list(r)for r in o.matrix_world]}),'uv':digest({u.name:[list(x.uv)for x in u.data]for u in o.data.uv_layers}),'materials':digest({'slots':mats,'indices':[p.material_index for p in o.data.polygons]}),'properties':digest({k:str(o[k])for k in o.keys()if k not in ['asset_group','asset_group_name']}),'visibility':[o.hide_render,o.hide_viewport]}
def selected(collection):return [o for o in collection.all_objects if o.type=='MESH'and o.get('asset_group')==ASSET]
def main():
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from mathutils import Matrix
 from refinement_workspace import prepare,modified,validate
 from asset_reference_views import render_states
 assert sha(DONOR)=='93e9c61355841152c5538e70a45e39b9498cf7507851751794fb82cbe36894f5'
 expected={};imports=[]
 for path,mode in [(DONOR,'hall'),(STAIR,'parapet')]:
  bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update()
  objects=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and (o.get('asset_group')==ASSET if mode=='hall'else o.get('source_node')=='building-497')]
  assert objects
  for o in objects:
   k=ident(o);assert k not in expected;kf=fingerprint(o);expected[k]=kf
  imports.append((path,[{'name':o.name,'key':ident(o),'matrix':[list(r)for r in o.matrix_world]}for o in objects]))
 bpy.ops.wm.open_mainfile(filepath=str(WORK/'grouped/nottingham-grouped-v15.blend'));bpy.context.view_layer.update()
 collection=bpy.data.collections['nottingham Working'];old=selected(collection);parents=[o.parent for o in old if o.parent];parent=parents[0]if parents else None
 for o in old:bpy.data.objects.remove(o,do_unlink=True)
 for path,rows in imports:
  with bpy.data.libraries.load(str(path),link=False)as(src,dst):dst.objects=[r['name']for r in rows]
  for o,row in zip(dst.objects,rows):
   assert o;collection.objects.link(o);o.parent=parent;o.matrix_world=Matrix(row['matrix']);o['asset_group']=ASSET;o['asset_group_name']='Castle main hall'
 bpy.context.view_layer.update();actual={ident(o):fingerprint(o)for o in selected(collection)};assert actual==expected,{k:[x for x in expected[k]if expected[k][x]!=actual.get(k,{}).get(x)]for k in expected if expected[k]!=actual.get(k)}
 # Native context objects lacking materials get a neutral display material before freeze.
 neutral=bpy.data.materials.new('V15 context neutral');neutral.diffuse_color=(.45,.45,.45,1);neutral.use_nodes=True
 for o in collection.all_objects:
  if o.type=='MESH'and not o.data.materials and o.get('asset_group')!=ASSET:o.data.materials.append(neutral)
 evidence=WORK/'grouped/nottingham-grouped-v15.evidence'
 prepare(OUT,asset_id=ASSET,scene_name='nottingham Refinement',collection_name=collection.name,source_path=WORK/'source-states/covered.png',grouping_manifest=WORK/'grouping/catalog-v15.json',inventory_path=evidence/'inventory.json',review_path=WORK/'grouping/grouping-review-v15.json',projection_manifest=OLD/'projection-layers.json',source_mask_manifest=OLD/'source-masks.json',width=256,height=320,context_padding=24,framing_padding=1.04)
 modified(OUT)
 # Preparation produces diagnostic projections. The reviewed saved material graphs
 # remain authoritative; restore the untouched, pre-projection baseline exactly.
 bpy.ops.wm.open_mainfile(filepath=str(OUT/'baseline.blend'));bpy.context.view_layer.update();bpy.context.preferences.filepaths.save_version=0
 actual={ident(o):fingerprint(o)for o in selected(bpy.data.collections['nottingham Working'])};assert actual==expected
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'model.blend'))
 write(OUT/'validation.json',validate(OUT))
 states=render_states(OUT,OUT/'states')
 write(OUT/'state-packet.json',{'version':1,'directory':str(OUT/'states'),'revealed_input':'input','baseline_note':'Fresh V15 baseline retains exact approved hall and transferred parapet.'})
 write(OUT/'regroup-preservation.json',{'version':1,'status':'PASS','model_sha256':sha(OUT/'model.blend'),'modified_views_sha256':sha(OUT/'modified/views.json'),'donor_model_sha256':sha(DONOR),'parapet_donor_sha256':sha(STAIR),'objects':expected,'geometry_uv_material_graphs_images_transforms_preserved':True,'state_ownership_preserved':json.loads((OLD/'projection-layers.json').read_text())['projection_reviews']==json.loads((OUT/'projection-layers.json').read_text())['projection_reviews'],'canonical_change':'building-497 transferred from west stair tower to main hall; no mesh edits.'})
 c=json.loads((OLD/'candidate.json').read_text());c.update(status='refinement-in-progress',geometry_reviewed=False,inspected_views=[],model_sha256=sha(OUT/'model.blend'),modified_views_sha256=sha(OUT/'modified/views.json'),recipe=str(Path(__file__).resolve()),changes=['Added western upper-terrace parapet497 to the main-hall group. Approved geometry, UVs, materials, packed source pixels and state ownership are unchanged.'])
 for state in ['covered','revealed']:
  for kind in ['solid','textured','context']:c[state+'_'+kind]=f'states/patch-008/{state}/{kind}.png'
 c.pop('geometry_audit',None);write(OUT/'candidate.json',c)
 print('V15 HALL PACKET READY FOR INDEPENDENT AUDIT',flush=True)
if __name__=='__main__':main()
