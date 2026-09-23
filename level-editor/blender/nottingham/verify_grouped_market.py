"""Reopen both files and compare the grouped market against approved partition meshes."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire

def main():
 acquire()
 import bpy
 def load(path):
  bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update();result={}
  for o in bpy.data.collections['nottingham Working'].all_objects:
   if o.type!='MESH' or not str(o.get('asset_group','')).startswith('nottingham-market-'):continue
   key=(o['source_node'],o.get('projection_component',''));value={'vertices':[tuple(o.matrix_world@v.co)for v in o.data.vertices],'faces':[tuple(p.vertices)for p in o.data.polygons],'uv':{u.name:[tuple(v.uv)for v in u.data]for u in o.data.uv_layers},'hidden':o.hide_render}
   if key in result:raise ValueError('Duplicate market identity')
   result[key]=value
  return result
 original=load(WORK/'market-partitions-v9/components.blend');grouped=load(WORK/'grouped/nottingham-grouped-v9.blend')
 if set(original)!=set(grouped) or len(original)!=27:raise ValueError('Market mesh membership changed')
 maximum=0
 for key,first in original.items():
  second=grouped[key]
  for field in ('faces','uv','hidden'):
   if first[field]!=second[field]:raise ValueError((key,field))
  if len(first['vertices'])!=len(second['vertices']):raise ValueError('Vertex count changed')
  delta=max(abs(a-b)for va,vb in zip(first['vertices'],second['vertices'])for a,b in zip(va,vb));maximum=max(maximum,delta)
  if delta>0.001:raise ValueError((key,'World-space geometry changed',delta))
 report={'status':'PASS','market_meshes':len(original),'maximum_world_coordinate_drift':maximum,'source_sha256':hashlib.sha256((WORK/'market-partitions-v9/components.blend').read_bytes()).hexdigest(),'grouped_sha256':hashlib.sha256((WORK/'grouped/nottingham-grouped-v9.blend').read_bytes()).hexdigest(),'scope':'Reopened approved partition source and grouped result; exact topology, UVs, visibility and bounded world-position comparison.'}
 (WORK/'grouped/nottingham-grouped-v9.market-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
