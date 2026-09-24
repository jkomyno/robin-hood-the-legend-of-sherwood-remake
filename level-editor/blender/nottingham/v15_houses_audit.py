"""Render exact saved V15 house materials and compare approved donor geometry/UVs."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from v15_houses_prepare import ROOT,WORK,sha,signature,write
from render_slots import acquire
from freeze_tooling import select_tooling
p=argparse.ArgumentParser();p.add_argument('asset',choices=['northwest-timber-house','north-dormer-house']);args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
from audit_stored_materials import run
asset='nottingham-'+args.asset;w=WORK/'round-38/assets'/asset;preserved=json.loads((w/'grouping-preservation.json').read_text());before={}
for donor,digest in preserved['donor_sha256'].items():
 assert sha(donor)==digest
 bpy.ops.wm.open_mainfile(filepath=donor);bpy.context.view_layer.update()
 for obj in bpy.data.collections['nottingham Working'].all_objects:
  if obj.type=='MESH' and obj.get('source_node')in{r['source_node']for r in preserved['parts']} and obj.get('asset_group')==Path(donor).parent.name:before[obj['source_node']]=signature(obj)
bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();rows=[]
for obj in bpy.data.collections['nottingham Working'].all_objects:
 if obj.type!='MESH'or obj.get('asset_group')!=asset:continue
 old=before[obj['source_node']];new=signature(obj)
 for field in ['vertices','faces','appearance','hidden']:assert old[field]==new[field],(obj.name,field)
 drift=max(abs(a-b)for v,z in zip(old['world'],new['world'])for a,b in zip(v,z));assert drift<=1e-5
 rows.append(dict(source_node=obj['source_node'],world_drift=drift))
report=run(w,w/'inspection/v15-saved-materials',render=True,export=False);assert not report['problems'],report['problems']
write(w/'inspection/v15-preservation-reopened.json',dict(status='PASS',model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),parts=rows,material_uv_preserved=True,donor_sha256=preserved['donor_sha256']))
print('V15_REOPENED_PRESERVATION_PASS',asset,flush=True)
