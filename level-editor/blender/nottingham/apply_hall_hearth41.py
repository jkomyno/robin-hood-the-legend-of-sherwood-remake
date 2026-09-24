"""Apply the independently checked local hearth fit to the fresh hall worker."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
from hall_hearth_boundary import apply
from v15_houses_prepare import signature
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
w=WORK/'round-41/assets/nottingham-castle-main-hall';path=w/'model.blend';old=sha(path);bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update();owned={'castle-hall-floor','castle-hall-floor-support'}
objects=list(bpy.data.collections['nottingham Working'].all_objects);outside={o.name:signature(o)for o in objects if o.type=='MESH'and not(o.get('source_node')=='building-501'and o.get('projection_component')in owned)}
report=apply();bpy.context.view_layer.update();assert outside=={o.name:signature(o)for o in objects if o.name in outside};bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(path));report.update(status='PASS-GEOMETRY-ONLY-AWAITING-SOURCE-BAKE',previous_model_sha256=old,model_sha256=sha(path),outside_meshes_preserved=len(outside),outside_geometry_uv_materials_transforms_preserved=True,independent_prototype_evidence=str(WORK/'castle-audit/v15-floor-independent/hearth-prototype'),recipe_sha256=sha(Path(__file__).with_name('hall_hearth_boundary.py')));(w/'hearth-boundary-correction.json').write_text(json.dumps(report,indent=2)+'\n');print('HALL41_HEARTH_APPLIED',report,flush=True)
