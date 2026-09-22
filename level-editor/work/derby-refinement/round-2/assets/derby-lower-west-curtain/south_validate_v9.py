"""Independent saved-file validation of unchanged lower masonry volumes."""
from pathlib import Path
import json
import bpy,bmesh
from mathutils import Vector
root=Path(__file__).resolve().parent;out=root/'inspection/south-cap-fit-v9'
records={}
for label,path in [('before',root/'inspection/complete-wall-candidate-v5/model.blend'),('after',out/'model.blend')]:
    bpy.ops.wm.open_mainfile(filepath=str(path));records[label]={}
    for node in ('building-023','building-042'):
        obj=next(o for o in bpy.data.collections['Derby Working'].objects if o.type=='MESH' and o.get('source_node')==node and not o.hide_render)
        bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.transform(bm,matrix=obj.matrix_world,verts=list(bm.verts))
        bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=Vector((0,0,189)),plane_no=Vector((0,0,1)),dist=.0001,clear_outer=True,clear_inner=False)
        boundary=[e for e in bm.edges if e.is_boundary]
        bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        records[label][node]={'lower_volume':bm.calc_volume(signed=True),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges)}
        bm.free()
for node in records['before']:
    a,b=records['before'][node],records['after'][node]
    b['relative_volume_difference']=abs(b['lower_volume']-a['lower_volume'])/a['lower_volume']
    assert b['relative_volume_difference']<1e-5,(node,a,b)
    assert a['nonmanifold_edges']==b['nonmanifold_edges']==0
(out/'lower-wall-validation.json').write_text(json.dumps(records,indent=2)+'\n')
print(records)
