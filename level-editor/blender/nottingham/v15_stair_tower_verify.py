"""Reopen the regrouped stair asset, compare approved data, and render stored materials."""
import sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from v15_stair_tower import ASSET,NODES,sha,digest,signature,append_donor
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
w=WORK/'round-41/assets'/ASSET;donor=WORK/'round-26/assets'/ASSET;bpy.ops.wm.open_mainfile(filepath=str(donor/'model.blend'));bpy.context.view_layer.update();golden={o['source_node']:signature(o)for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and not o.hide_render and o.get('asset_group')==ASSET and o.get('source_node')in NODES};bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();targets={o['source_node']:o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and not o.hide_render and o.get('asset_group')==ASSET};assert set(targets)==NODES;report=json.loads((w/'regrouping-preservation.json').read_text())
for node in NODES:
 assert signature(targets[node])==golden[node],node
 assert digest(signature(targets[node]))==report['signatures'][node],node
report.update(reopened_status='PASS',model_sha256=sha(w/'model.blend'));(w/'regrouping-preservation.json').write_text(json.dumps(report,indent=2)+'\n')
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from audit_stored_materials import run
run(w,w/'inspection/v15-stored-materials',render=True)
path=Path(__file__).with_name('verify_workspace_known_rgb.py');source=path.read_text().replace("select_tooling(root/'tooling/94116d984f92dbae')","");sys.argv=[str(path),'--',str(w)];exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
