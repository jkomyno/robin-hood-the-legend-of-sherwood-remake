"""Verify the bounded porch edit against the archived user-reviewed geometry."""
import json,sys,hashlib
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
w=Path(sys.argv[sys.argv.index('--')+1]).resolve()
asset='leicester-northeast-gabled-house'
def capture():
    result={}
    for o in bpy.data.collections['Leicester Working'].all_objects:
        if o.type!='MESH' or o.get('asset_group')!=asset:continue
        bm=bmesh.new();bm.from_mesh(o.data)
        value={'geometry_sha256':hashlib.sha256(json.dumps([[list(v.co) for v in o.data.vertices],[list(p.vertices) for p in o.data.polygons]]).encode()).hexdigest(),'transform':[list(r) for r in o.matrix_world],'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-6 for f in bm.faces)};bm.free()
        if o.get('projection_component') in ['canopy-left-post','canopy-right-post']:
            verts=[o.matrix_world@v.co for v in o.data.vertices];low=min(v.z for v in verts);high=max(v.z for v in verts)
            centers=[sum((v for v in verts if abs(v.z-z)<1e-4),Vector())/4 for z in [low,high]]
            value.update(axis_horizontal_drift=(centers[1]-centers[0]).xy.length,foot_elevation=low,top_elevation=high)
        result[o.name]=value
    return result
after=capture();bpy.ops.wm.open_mainfile(filepath=str(w/'history/before-vertical-porch-21f500d15e396441/model.blend'),load_ui=False);before=capture()
changed=[n for n in after if after[n]['geometry_sha256']!=before[n]['geometry_sha256']]
expected=['Leicester Northeast Canopy Left Post','Leicester Northeast Canopy Right Post']
assert set(changed)==set(expected),changed
assert all(a['transform']==before[n]['transform'] and not a['nonmanifold_edges'] and not a['degenerate_faces'] for n,a in after.items())
assert all(after[n]['axis_horizontal_drift']<1e-5 for n in expected)
report={'status':'PASS','changed_objects':changed,'roof_and_other_nine_meshes_exactly_unchanged':True,'before':before,'after':after,'terrain_limitation':'Source crop shows footings on ditch bank below house foundation. Generic flat ground is not accurate local terrain; future staging must not clip these posts at z0.'}
(w/'inspection/vertical-porch/validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':'PASS','changed_objects':changed}))
