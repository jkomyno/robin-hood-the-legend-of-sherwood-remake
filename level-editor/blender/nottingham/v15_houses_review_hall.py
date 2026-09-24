"""Independent read-only donor comparison of the regrouped V15 main hall."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from v15_houses_prepare import ROOT,WORK,sha,signature,write
from freeze_tooling import select_tooling
from render_slots import acquire
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
w=WORK/'round-38/assets/nottingham-castle-main-hall';asset=w.name;expected={}
for donor,mode in [(WORK/'approval-evidence'/asset/'93e9c6135584/model.blend','hall'),(WORK/'round-26/assets/nottingham-castle-west-stair-tower/model.blend','parapet')]:
 bpy.ops.wm.open_mainfile(filepath=str(donor));bpy.context.view_layer.update()
 for o in bpy.data.collections['nottingham Working'].all_objects:
  if o.type=='MESH' and (o.get('asset_group')==asset if mode=='hall' else o.get('source_node')=='building-497'):
   key=o.get('source_node')+'|'+o.get('projection_component','');assert key not in expected;expected[key]=signature(o)
bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();actual={o.get('source_node')+'|'+o.get('projection_component',''):signature(o)for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==asset};assert set(actual)==set(expected)
for key in actual:assert actual[key]==expected[key],key
write(w/'inspection/independent-v15-donor-comparison.json',dict(status='PASS',model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),exact_mesh_count=len(actual),world_vertices_uv_material_graph_packed_images_unchanged=True,method='Independent direct comparison of donor and final datablocks keyed by source node and projection component.'))
print('INDEPENDENT_V15_HALL_DONOR_PASS',len(actual),flush=True)
