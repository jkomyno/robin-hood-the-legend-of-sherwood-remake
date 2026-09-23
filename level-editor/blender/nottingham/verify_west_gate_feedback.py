"""Independently bind west gate membership, immutable inputs and source RGB."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
from freeze_tooling import select_tooling
select_tooling(ROOT/'level-editor/work/nottingham-refinement/tooling/58744eeaf71a21e9')
import bpy
from refinement_workspace import validate
w=ROOT/'level-editor/work/nottingham-refinement/round-25/assets/nottingham-castle-gate-west-tower';bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));validation=validate(w);assert validation['status']=='PASS';assert set(validation['part_ids'])=={f'building-{i}'for i in [329,330,331,332]};owned=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==w.name];assert len(owned)==4;assert all(o['source_node'] not in ['building-349','building-350']for o in owned)
report=dict(status='PASS',validation=validation,model_sha256=hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),objects=[dict(name=o.name,source_node=o['source_node'],vertices=len(o.data.vertices),faces=len(o.data.polygons))for o in owned]);(w/'inspection/independent-gates-structure.json').write_text(json.dumps(report,indent=2)+'\n')
code=(Path(__file__).parent/'verify_workspace_known_rgb.py').read_text().replace("select_tooling(root/'tooling/94116d984f92dbae')","select_tooling(root/'tooling/58744eeaf71a21e9')").replace("w/'known-rgb-validation.json'","w/'inspection/independent-gates-source-rgb.json'");sys.argv=['verify_workspace_known_rgb.py','--',str(w)];exec(compile(code,str(Path(__file__).parent/'verify_workspace_known_rgb.py'),'exec'))
