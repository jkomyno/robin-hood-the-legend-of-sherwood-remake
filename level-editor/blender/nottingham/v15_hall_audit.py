"""Reopen regrouped hall and inspect exact reviewed material graphs in both states."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from v15_hall_packet import OUT,WORK,ASSET,sha,write,ident,fingerprint,selected
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
bpy.ops.wm.open_mainfile(filepath=str(OUT/'model.blend'));bpy.context.view_layer.update()
r=json.loads((OUT/'regroup-preservation.json').read_text());assert r['model_sha256']==sha(OUT/'model.blend')
actual={ident(o):fingerprint(o)for o in selected(bpy.data.collections['nottingham Working'])};assert actual==r['objects']
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
from audit_stored_materials import run
states=json.loads((OUT/'states/states.json').read_text());results=[]
for state in states['states']:
 report=run(OUT,OUT/'inspection/actual-materials'/state['state'],render=True,render_object_names=state['object_names'],frame_manifest=Path(state['path'])/'views.json')
 assert not report['problems'],report['problems'];results.append({'state':state['state'],'audit_sha256':sha(OUT/'inspection/actual-materials'/state['state']/'audit.json')})
write(OUT/'inspection/actual-materials/validation.json',{'status':'PASS','model_sha256':sha(OUT/'model.blend'),'donor_snapshots_preserved':True,'states':results,'visual_review':'pending-independent-review'})
