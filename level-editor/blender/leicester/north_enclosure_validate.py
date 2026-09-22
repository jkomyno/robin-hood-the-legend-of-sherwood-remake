"""Check enclosure transforms, retained anchors, datum and closed topology."""
import json,hashlib
from pathlib import Path
import bpy,bmesh

w=Path(bpy.data.filepath).parent
def owned():
    return {o['source_node']:o for o in bpy.data.collections['Leicester Working'].all_objects
            if o.type=='MESH' and o.get('asset_group')=='leicester-church-courtyard-wall'}
bpy.ops.wm.open_mainfile(filepath=str(w/'baseline.blend'))
baseline={node:([tuple(o.matrix_world@v.co) for v in o.data.vertices],[list(r) for r in o.matrix_world]) for node,o in owned().items()}
bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'))
rows=[]
for node,o in owned().items():
    before,matrix=baseline[node];points=[o.matrix_world@v.co for v in o.data.vertices]
    drift=max(abs(matrix[i][j]-o.matrix_world[i][j]) for i in range(4) for j in range(4))
    bm=bmesh.new();bm.from_mesh(o.data)
    row={'source_node':node,'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces),'transform_drift':drift,'minimum_z':min(p.z for p in points),'vertices':len(points),'faces':len(o.data.polygons)}
    bm.free()
    assert not row['nonmanifold_edges'] and not row['degenerate_faces'] and drift==0,row
    if node!='building-368':assert abs(row['minimum_z']-61.04)<.01,row
    if node not in ('building-368','building-371','building-372'):
        from mathutils import Vector
        upper=[Vector(p) for p in before if p[2]>61.04]
        row['maximum_upper_anchor_drift']=max(min((v-p).length for v in points) for p in upper)
        assert row['maximum_upper_anchor_drift']<.5,row
    row['geometry_sha256']=hashlib.sha256(json.dumps({'vertices':[list(v.co) for v in o.data.vertices],'faces':[list(f.vertices) for f in o.data.polygons]},sort_keys=True).encode()).hexdigest()
    rows.append(row)
(w/'geometry-validation.json').write_text(json.dumps({'status':'PASS','components':rows,'limits':'Arch soffit and barrel surfaces intentionally replace their measured box envelopes; other upper anchors remain within half a world unit.'},indent=2)+'\n')
print(json.dumps({'status':'PASS','components':len(rows)}))
