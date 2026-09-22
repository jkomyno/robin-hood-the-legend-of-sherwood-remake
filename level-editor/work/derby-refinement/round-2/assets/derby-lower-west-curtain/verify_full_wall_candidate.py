import bpy,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
def fingerprint(o):
 verts=[tuple(round(v,4) for v in o.matrix_world@p.co) for p in o.data.vertices]
 return hashlib.sha256(json.dumps([verts,[list(p.vertices) for p in o.data.polygons]]).encode()).hexdigest()
protected={f'building-{i:03d}' for i in (27,28,29,30,31,32,36,37,38,45)}
def get_protected():
 return {n:sorted(fingerprint(o) for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH' and o.get('source_node')==n) for n in protected}
def floor_points():
 result={}
 for n in ('building-023','building-025','building-042'):
  o=next(o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH' and o.get('source_node')==n and not o.hide_render)
  result[n]=sorted({tuple(round(c,2) for c in p) for v in o.data.vertices if (p:=o.matrix_world@v.co).z<1})
 return result
bpy.ops.wm.open_mainfile(filepath=str(root/'logical-split/grouped-model.blend'))
before=get_protected();floor_before=floor_points()
bpy.ops.wm.open_mainfile(filepath=str(root/'inspection/complete-wall-candidate-v5/model.blend'))
after=get_protected();floor_after=floor_points()
checks={'protected_geometry_unchanged':before==after,'wall_bottom_footprints_unchanged':floor_before==floor_after,
        'protected_nodes':sorted(protected),'before_hashes':before,'after_hashes':after,
        'floor_before':floor_before,'floor_after':floor_after}
(root/'inspection/complete-wall-candidate-v5/preservation-validation.json').write_text(json.dumps(checks,indent=2)+'\n')
assert checks['protected_geometry_unchanged'], 'Approved stair/turret/support geometry changed'
assert checks['wall_bottom_footprints_unchanged'], 'Wall body ground footprints changed'
print('PASS: approved geometry and complete wall ground footprints unchanged')
