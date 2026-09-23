"""Restore foreign UV schema after workspace preparation adds projection layers.

Only layers absent from the immutable workspace baseline are removed. Existing
coordinates, target UVs, geometry, transforms and material assignments must match.
"""
import hashlib,json,sys
from pathlib import Path
import bpy
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def uv(obj):
 return {layer.name:[list(v.uv)for v in layer.data] for layer in obj.data.uv_layers}
def invariant(obj):
 return {'matrix':[list(row)for row in obj.matrix_world],'vertices':[list(v.co)for v in obj.data.vertices],'faces':[list(p.vertices)for p in obj.data.polygons],'materials':[m.name if m else None for m in obj.data.materials],'material_indices':[p.material_index for p in obj.data.polygons],'hidden':obj.hide_render,'owner':obj.get('asset_group')}

def restore_foreign_uv_schema(workspace, *, apply=True):
 """Reopen baseline/model, validate, remove added foreign layers and optionally save.

 The caller owns the render lease. This leaves the model scene open. Call after
 final projection; packet pixels remain valid because target geometry and UVs do
 not change. Bind candidate metadata to the returned final model hash.
 """
 workspace=Path(workspace).resolve()
 asset=json.loads((workspace/'workspace.json').read_text())['asset_id']
 baseline_sha=sha(workspace/'baseline.blend');model_before=sha(workspace/'model.blend')
 bpy.ops.wm.open_mainfile(filepath=str(workspace/'baseline.blend'));bpy.context.view_layer.update()
 baseline={o.name:uv(o)for o in bpy.data.objects if o.type=='MESH' and o.get('asset_group')!=asset}
 bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'));bpy.context.view_layer.update()
 before={o.name:invariant(o)for o in bpy.data.objects if o.type=='MESH'}
 owned_uv={o.name:uv(o)for o in bpy.data.objects if o.type=='MESH' and o.get('asset_group')==asset}
 plan=[]
 # Validate every preexisting layer before making any in-memory change.
 for name,expected in baseline.items():
  obj=bpy.data.objects.get(name);assert obj is not None and obj.type=='MESH',name
  current=uv(obj);assert expected.keys()<=current.keys(),('Missing baseline layer',name)
  for layer,values in expected.items():assert current[layer]==values,('Modified preexisting UV',name,layer)
  extras=[layer for layer in current if layer not in expected]
  if extras:plan.append({'object':name,'remove_layers':extras})
 for item in plan:
  obj=bpy.data.objects[item['object']]
  # Shared datablocks cannot safely be repaired on behalf of only one owner.
  sharing=[o for o in bpy.data.objects if o.type=='MESH' and o.data==obj.data]
  assert all(o.get('asset_group')!=asset for o in sharing),('UV data shared with target',item['object'])
  for name in item['remove_layers']:
   layer=obj.data.uv_layers.get(name)
   if layer is not None:obj.data.uv_layers.remove(layer)
 for name,expected in baseline.items():assert uv(bpy.data.objects[name])==expected,name
 assert before=={o.name:invariant(o)for o in bpy.data.objects if o.type=='MESH'},'Non-UV state changed'
 assert owned_uv=={o.name:uv(o)for o in bpy.data.objects if o.type=='MESH' and o.get('asset_group')==asset},'Target UV changed'
 assert sha(workspace/'baseline.blend')==baseline_sha
 report={'status':'DRY_RUN_PASS','baseline_sha256':baseline_sha,'model_before_sha256':model_before,'objects_restored':len(plan),'layers_removed':sum(len(x['remove_layers'])for x in plan),'plan':plan,'scope':'Only foreign UV layers absent from frozen baseline; all existing layer values, target UV, geometry, transforms, materials and visibility preserved.'}
 if apply:
  if plan:
   bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
  report.update(status='RESTORED' if plan else 'UNCHANGED',model_after_sha256=sha(workspace/'model.blend'))
  (workspace/'inspection/foreign-uv-schema-restoration.json').write_text(json.dumps(report,indent=2)+'\n')
 return report

if __name__=='__main__':
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 args=sys.argv[sys.argv.index('--')+1:]
 result=restore_foreign_uv_schema(args[0],apply='--apply' in args)
 print(json.dumps({k:v for k,v in result.items()if k!='plan'},indent=2),flush=True)
