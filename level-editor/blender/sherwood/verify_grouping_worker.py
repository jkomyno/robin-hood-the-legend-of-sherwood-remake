"""Reopen and verify the saved grouping candidate, independently of its render scene."""
import json
from pathlib import Path
import sys
import bpy

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from stage_grouping_review import fingerprint,sha

root=Path(sys.argv[sys.argv.index('--')+1]).resolve()
report=json.loads((root/'stage.json').read_text());plan=json.loads((root/'plan.json').read_text())
assert sha(root/'grouped-source-only.blend')==report['worker_sha256']
bpy.ops.wm.open_mainfile(filepath=str(root/'grouped-source-only.blend'))
objects=[o for o in bpy.data.collections['Sherwood Working'].objects if o.type=='MESH']
assert len(objects)==report['mesh_count']
assert fingerprint(objects)==report['geometry_uv_material_fingerprint']
assert {o.name:o['asset_group'] for o in objects}==plan['assignments']
assert len({o['asset_group'] for o in objects})==plan['candidate_groups']+1
result=dict(status='PASS',saved_worker_sha256=report['worker_sha256'],mesh_count=len(objects),
            selectable_groups=plan['candidate_groups'],geometry_uv_materials_unchanged=True,exact_mesh_ownership=True)
(root/'saved-worker-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
