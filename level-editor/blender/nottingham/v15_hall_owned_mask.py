"""Carry the transferred parapet's reviewed source domain into its new group."""
import json,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from v15_hall_packet import OUT,WORK,OLD,STAIR,sha,write,ident,fingerprint,selected
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
from refinement_workspace import modified,validate
from asset_reference_views import render_states
maskpath=OUT/'source-masks.json';m=json.loads(maskpath.read_text());donor=json.loads((STAIR.parent/'source-masks.json').read_text());assignment=next(x for x in donor['projections']['exterior']['assignments']if x['source_node']=='building-497')
for index,row in enumerate(m['projections']['exterior']['assignments']):
 if row['source_node']=='building-497':m['projections']['exterior']['assignments'][index]=copy.deepcopy(assignment)
write(maskpath,m)
bpy.ops.wm.open_mainfile(filepath=str(OUT/'model.blend'));modified(OUT)
bpy.ops.wm.open_mainfile(filepath=str(OUT/'baseline.blend'));bpy.context.view_layer.update();r=json.loads((OUT/'regroup-preservation.json').read_text());assert {ident(o):fingerprint(o)for o in selected(bpy.data.collections['nottingham Working'])}==r['objects']
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'model.blend'));write(OUT/'validation.json',validate(OUT))
render_states(OUT,OUT/'states-owned')
write(OUT/'state-packet.json',{'version':1,'directory':str(OUT/'states-owned'),'revealed_input':'input','baseline_note':'Fresh V15 input; working masks carry native428 from the transferred parapet donor.'})
r.update(model_sha256=sha(OUT/'model.blend'),modified_views_sha256=sha(OUT/'modified/views.json'),transferred_receiver_source_assignment=assignment,transferred_source_evidence=str(STAIR.parent/'inspection/building-497-added-source-pixels.json'),transferred_source_evidence_sha256=sha(STAIR.parent/'inspection/building-497-added-source-pixels.json'));write(OUT/'regroup-preservation.json',r)
c=json.loads((OUT/'candidate.json').read_text());c.update(model_sha256=sha(OUT/'model.blend'),modified_views_sha256=sha(OUT/'modified/views.json'))
for state in ['covered','revealed']:
 for kind in ['solid','textured','context']:c[state+'_'+kind]=f'states-owned/patch-008/{state}/{kind}.png'
write(OUT/'candidate.json',c)
