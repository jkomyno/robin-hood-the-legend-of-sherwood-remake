"""Apply source-reviewed floor, parapet and ridge fixes to the hall authoring file."""
import sys,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
from hall_floor_source_boundary import apply
from hall_stair_parapet import apply as parapet
from hall_ridge_source_threshold import apply as ridge
from v15_houses_prepare import signature
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
w=WORK/'round-41/assets/nottingham-castle-main-hall';path=w/'model.blend';old=sha(path);history=w/'history'/('before-floor-boundary-'+old[:16]);history.mkdir(parents=True,exist_ok=True);shutil.copy2(path,history/'model.blend');shutil.copy2(w/'source-masks.json',history/'source-masks.json');bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update();owned={'castle-hall-floor','castle-hall-floor-support'}
objects=list(bpy.data.collections['nottingham Working'].all_objects);outside={o.name:signature(o) for o in objects if o.type=='MESH' and not(o.get('source_node')=='building-501' and o.get('projection_component') in owned)}
report=apply();report['parapet']=parapet();report['ridge']=ridge();bpy.context.view_layer.update();assert outside=={o.name:signature(o) for o in objects if o.name in outside};bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(path));report.update(status='PASS-GEOMETRY-AWAITING-STATE-BAKE',previous_model_sha256=old,model_sha256=sha(path),outside_meshes_preserved=len(outside),history=str(history));(w/'floor-boundary-correction.json').write_text(json.dumps(report,indent=2)+'\n');print('HALL41_FLOOR_APPLIED',report['model_sha256'],flush=True)
