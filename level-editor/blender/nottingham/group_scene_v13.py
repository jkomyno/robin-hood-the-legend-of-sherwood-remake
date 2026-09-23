"""Apply gate pier ownership to the complete grouped scene without changing meshes."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from freeze_tooling import select_tooling
from render_slots import acquire


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def signature(obj):
 return {'vertices':[list(v.co)for v in obj.data.vertices],'faces':[list(p.vertices)for p in obj.data.polygons],'uv':{layer.name:[list(v.uv)for v in layer.data]for layer in obj.data.uv_layers},'matrix':[list(row)for row in obj.matrix_world],'hidden':obj.hide_render}


def main():
 tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9');acquire()
 import bpy
 from group_assets import reconcile_asset_groups
 source=WORK/'grouped/nottingham-grouped-v11.blend';output=WORK/'grouped/nottingham-grouped-v13.blend';catalog=WORK/'grouping/catalog-v13.json';review=WORK/'grouping/grouping-review-v13.json';inventory=WORK/'inventory/inventory-v2.json'
 if output.exists():raise FileExistsError(output)
 binding=json.loads(review.read_text())
 if binding['catalog_sha256']!=sha(catalog)or binding['inventory_sha256']!=sha(inventory):raise ValueError('Review binding changed')
 for record in binding['evidence']:
  if sha(WORK/record['path'])!=record['sha256']:raise ValueError('Ownership evidence changed')
 bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.view_layer.update();objects=[obj for obj in bpy.data.collections['nottingham Working'].all_objects if obj.type=='MESH'];before={obj.as_pointer():signature(obj)for obj in objects}
 result=reconcile_asset_groups(catalog);bpy.context.view_layer.update();maximum=0
 for obj in objects:
  previous=before[obj.as_pointer()];current=signature(obj)
  for field in ('vertices','faces','uv','hidden'):
   if previous[field]!=current[field]:raise ValueError(('Grouping changed mesh',obj.name,field))
  delta=max(abs(a-b)for ra,rb in zip(previous['matrix'],current['matrix'])for a,b in zip(ra,rb));maximum=max(maximum,delta)
  if delta>1e-5:raise ValueError(('Grouping changed transform',obj.name,delta))
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(output));evidence=output.with_suffix('.evidence');evidence.mkdir()
 for name,path in [('catalog.json',catalog),('inventory.json',inventory),('grouping-review.json',review)]:shutil.copy2(path,evidence/name)
 report={'status':'PASS','version':1,'tooling':tooling,'source_sha256':sha(source),'grouped_sha256':sha(output),'catalog_sha256':sha(catalog),'grouping':result,'preserved_meshes':len(objects),'maximum_transform_drift':maximum,'geometry_uv_visibility_mutations':0,'note':'Ownership baseline only. Workers import their already refined arch and tower geometry into fresh isolated workspaces.','recipe_sha256':sha(__file__)}
 output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2)+'\n');print('V13_GROUPING_PASS',len(objects),maximum,flush=True)


if __name__=='__main__':main()
