"""Run in background Blender: foreign component geometry/material/UV guards."""
import hashlib,json,sys,tempfile
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from catalog_schema import parse_catalog
from workspace_components import scope_for
from refinement_workspace import _ownership,_sha,validate
from test_workspace_components import CATALOG

def main():
 scene=bpy.data.scenes.new('Scope Refinement');collection=bpy.data.collections.new('Scope Working');scene.collection.children.link(collection);bpy.context.window.scene=scene
 def mesh(name,component,owner,hidden=False):
  data=bpy.data.meshes.new(name);data.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)]);data.uv_layers.new();obj=bpy.data.objects.new(name,data);collection.objects.link(obj);obj['source_node']='building-000';obj['asset_group']=owner
  if component:obj['projection_component']=component
  obj.hide_render=hidden;mat=bpy.data.materials.new(name+' material');mat.use_nodes=True;data.materials.append(mat);return obj
 original=mesh('original',None,'left',True);left=mesh('left','left-part','left');right=mesh('right','right-part','right')
 with tempfile.TemporaryDirectory()as directory:
  work=Path(directory);ref=work/'reference';ref.mkdir();(work/'input').mkdir();(ref/'grouping.json').write_text(json.dumps(CATALOG));(work/'baseline.blend').write_bytes(b'fixture baseline')
  config={'asset_id':'left','part_ids':['building-000'],'source_path':str(ref/'source.png'),'scene_name':scene.name,'collection_name':collection.name,'grouping_manifest_sha256':_sha(ref/'grouping.json'),'component_ownership':scope_for(parse_catalog(CATALOG),'left'),'input_files':{},'reference_files':{'grouping.json':_sha(ref/'grouping.json')},'baseline_sha256':_sha(work/'baseline.blend')}
  _,config['outside_geometry']=_ownership(config);(work/'workspace.json').write_text(json.dumps(config));assert validate(work)['status']=='PASS'
  left.data.vertices[0].co.x+=.25;assert validate(work)['status']=='PASS'
  def rejected(change,restore):
   change()
   try:validate(work)
   except ValueError:pass
   else:raise AssertionError('Foreign mutation was accepted')
   restore();assert validate(work)['status']=='PASS'
  uv=right.data.uv_layers.active.data[0].uv.copy();rejected(lambda:setattr(right.data.uv_layers.active.data[0],'uv',(.4,.7)),lambda:setattr(right.data.uv_layers.active.data[0],'uv',uv))
  rgba=right.data.materials[0].diffuse_color[:];rejected(lambda:setattr(right.data.materials[0],'diffuse_color',(1,0,0,1)),lambda:setattr(right.data.materials[0],'diffuse_color',rgba))
  socket=right.data.materials[0].node_tree.nodes.get('Principled BSDF').inputs['Roughness'];roughness=socket.default_value;rejected(lambda:setattr(socket,'default_value',.99),lambda:setattr(socket,'default_value',roughness))
  rejected(lambda:right.__setitem__('asset_group','left'),lambda:right.__setitem__('asset_group','right'))
  coordinate=original.data.vertices[0].co.copy();rejected(lambda:setattr(original.data.vertices[0],'co',(8,8,8)),lambda:setattr(original.data.vertices[0],'co',coordinate))
  rejected(lambda:setattr(original,'hide_render',False),lambda:setattr(original,'hide_render',True))
 print('PASS component workspace guards: owned edit allowed; foreign UV, material, shader, owner and visible original rejected')
if __name__=='__main__':main()
