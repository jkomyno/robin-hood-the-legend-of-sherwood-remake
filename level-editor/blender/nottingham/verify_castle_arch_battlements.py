"""Check retained gate geometry, saved source-corner fits, and all endpoint RGB."""
import json,sys,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';W=WORK/'round-30/assets/nottingham-castle-gate-arch'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy,bmesh
from refine_church import fingerprint,SIN,COS
from correct_source_projection import geometry
bpy.ops.wm.open_mainfile(filepath=str(W/'baseline.blend'));bpy.context.view_layer.update();before=geometry();foreign={o.name:fingerprint(o)for o in bpy.data.objects if o.type=='MESH'and o.get('asset_group')!=W.name}
bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'));bpy.context.view_layer.update();after=geometry();allowed={o.name for o in bpy.data.objects if o.type=='MESH'and o.get('asset_group')==W.name and not o.get('animation_state') and o.get('source_node')in ['building-333','building-335','building-336']};drift=[n for n in before if n not in allowed and before[n]!=after[n]];foreign_drift=[n for n,v in foreign.items()if fingerprint(bpy.data.objects[n])!=v];assert not drift,drift;assert not foreign_drift,foreign_drift
bodyname=next(o.name for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==W.name and o.get('source_node')=='building-333'and not o.get('animation_state'));oldbody=before[bodyname];newbody=after[bodyname];assert oldbody['vertices']==newbody['vertices'][:len(oldbody['vertices'])];assert oldbody['faces']==newbody['faces'][:len(oldbody['faces'])]
rows=[];report=json.loads((W/'battlement-report.json').read_text())
bodyobj=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==W.name and o.get('source_node')=='building-333'and not o.get('animation_state'));added=[bodyobj.matrix_world@v.co for v in list(bodyobj.data.vertices)[len(oldbody['vertices']):]];assert len(added)==8
expected=[(x,y,z)for z in [271,275]for x,y in report['walkway']['native_footprint']];errors=[math.dist((p.x,-p.y*SIN,p.z*COS),q)for p,q in zip(added,expected)];assert max(errors)<.001;assert abs(max(p.x for p in added)-975.8945)<.001
report['walkway']['actual_saved_corner_maximum_error']=max(errors);report['walkway']['old_vault_vertices_and_faces_preserved']=True
(W/'inspection/walkway-contact-proof.json').write_text(json.dumps(report['walkway'],indent=2)+'\n')
for row in report['corners']:
 o=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('source_node')==f"building-{row['node']}");x,y=row['source_pixel'];ps=[o.matrix_world@v.co for v in o.data.vertices];p=min(ps,key=lambda p:math.hypot(p.x-x,-p.y*SIN-p.z*COS-y));actual=[p.x,-p.y*SIN-p.z*COS];rows.append(dict(**row,actual=actual,residual=math.hypot(actual[0]-x,actual[1]-y)))
assert max(r['residual']for r in rows)<.01
(W/'inspection/battlement-preservation.json').write_text(json.dumps(dict(status='PASS',foreign_geometry_uv_preserved=len(foreign),protected_geometry_preserved=len(before)-len(allowed),corner_construction_check=rows,model_sha256=hashlib.sha256((W/'model.blend').read_bytes()).hexdigest(),limitations=['Exact fitted-corner residuals are construction checks, not independent evidence for the artwork observations.']),indent=2)+'\n')
from audit_stored_materials import run
run(W,W/'inspection/stored-materials',render=True)
code=(Path(__file__).parent/'verify_workspace_known_rgb.py').read_text().replace("select_tooling(root/'tooling/94116d984f92dbae')","select_tooling(root/'tooling/58744eeaf71a21e9')").replace("packets=[w/'modified']","packets=[w/'modified']+[p.parent for p in sorted((w/'inspection/endpoints-v5').glob('*/views.json'))]+[p.parent for p in sorted((w/'inspection/endpoints-v5').glob('*/full-height/views.json'))]")
code=code.replace('cache={};reports=[]',"assert len(packets)==5, 'Incomplete final endpoint review packet'\ncache={};reports=[]")
sys.argv=['verify_workspace_known_rgb.py','--',str(W)];exec(compile(code,str(Path(__file__).parent/'verify_workspace_known_rgb.py'),'exec'))
