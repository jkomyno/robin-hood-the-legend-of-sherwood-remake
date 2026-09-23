"""Reopen gate sources and fresh ownership packets to verify exact mesh preservation."""
import hashlib,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def meshes(path):
 bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update();result={}
 for obj in bpy.data.collections['nottingham Working'].all_objects:
  if obj.type!='MESH' or obj.hide_render:continue
  key=(obj.get('source_node'),obj.get('projection_component',''))
  if key in result:raise ValueError(('Duplicate source component',key))
  result[key]={'owner':obj.get('asset_group'),'vertices':[list(obj.matrix_world@v.co)for v in obj.data.vertices],'faces':[list(p.vertices)for p in obj.data.polygons]}
 return result


def main():
 acquire();cache={}
 for asset in ('nottingham-south-gate-arch','nottingham-south-gate-east-tower'):
  w=WORK/'round-15/assets'/asset;record=json.loads((w/'membership-revision.json').read_text());current=meshes(w/'model.blend');checks=[]
  expected={(r['source_node'],r['projection_component'])for r in record['source_imports']};actual={key for key,item in current.items()if item['owner']==asset}
  if expected!=actual:raise ValueError('Fresh gate selector mismatch')
  if (('building-212','')in actual)!=(asset=='nottingham-south-gate-arch'):raise ValueError('Pier212 belongs only to arch')
  for item in record['source_imports']:
   source=item['source_blend'];key=(item['source_node'],item['projection_component'])
   if sha(source)!=item['source_blend_sha256']:raise ValueError('Frozen geometry source changed')
   if source not in cache:cache[source]=meshes(source)
   before=cache[source][key];after=current[key]
   if before['faces']!=after['faces']or len(before['vertices'])!=len(after['vertices']):raise ValueError(('Topology changed',key))
   delta=max(abs(a-b)for va,vb in zip(before['vertices'],after['vertices'])for a,b in zip(va,vb))
   if delta>0.001:raise ValueError(('World geometry changed',key,delta))
   checks.append({'source_node':key[0],'component':key[1],'maximum_world_coordinate_drift':delta,'exact_topology':True})
  report={'status':'PASS','method':'Independent reopened frozen source and final model comparison; all world vertices and polygon indices, exact active ownership selectors.','asset_id':asset,'model_sha256':sha(w/'model.blend'),'ownership_212':'arch-only','checks':checks}
  (w/'independent-import-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(asset,'IMPORT_PASS',checks,flush=True)


if __name__=='__main__':main()
