"""Validate stored terrain geometry, bridge clearance, and actual saved materials."""
import hashlib
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire()
tooling=select_tooling()
from audit_stored_materials import run
import refine_terrain
import refine_village
import refine_village_secondary

workspace=Path(sys.argv[sys.argv.index('--')+1]).resolve()
previous=Path(sys.argv[sys.argv.index('--')+2]).resolve()


def ground_geometry(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    ground=next(o for o in bpy.data.collections['nottingham Working'].all_objects
                if o.type=='MESH' and o.get('source_node')=='ground')
    return ground, {'geometry':refine_terrain._geometry(ground),
                    'matrix':[list(row) for row in ground.matrix_world],
                    'uv':[list(v.uv) for v in ground.data.uv_layers.active.data]}


_,prior=ground_geometry(previous/'model.blend')
ground,current=ground_geometry(workspace/'model.blend')
assert prior==current, 'Terrain geometry or UV changed since reviewed bridge-clearance version'
sources={o.get('source_node'):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'}
clearance={}
for name,recipe in [('main',refine_village._bridge),('west',refine_village_secondary.bridge)]:
    result=recipe(sources)
    bridge=bpy.data.objects[result['component']]
    clearance[name]=refine_terrain.validate_bridge_clearance(ground,bridge)
audit=run(workspace,workspace/'inspection/stored-material',render=True,export=False)
assert audit['status']=='STRUCTURAL-PASS',audit['problems']
report={'status':'PASS','model_sha256':hashlib.sha256((workspace/'model.blend').read_bytes()).hexdigest(),
        'previous_geometry_uv_world_matrix_identical':True,'bridge_clearance':clearance,
        'stored_material_audit':str(workspace/'inspection/stored-material/audit.json'),
        'tooling':tooling['snapshot_id']}
(workspace/'terrain-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS',workspace)
