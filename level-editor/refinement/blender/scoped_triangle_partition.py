"""Partition explicitly selected ngons into their existing rendered triangles.

No new vertex or triangle is inferred. The returned mesh is not linked or saved
until exact physical equivalence has passed. Atlas generation and source-domain
proof remain separate requirements.
"""
from triangle_equivalence import verify_equivalence


def partition(obj, face_ids, atlas_uv_names=()):
    mesh = obj.data
    face_ids = set(face_ids)
    if not face_ids or any(not isinstance(i, int) or i < 0 or i >= len(mesh.polygons) for i in face_ids):
        raise ValueError('Explicit existing polygon IDs required')
    if mesh.shape_keys or obj.modifiers:
        raise ValueError('Modifiers and shape keys require separate surface proof')
    if mesh.has_custom_normals:
        raise ValueError("Custom split normals require separate corner-normal proof")
    mesh.calc_loop_triangles()
    layouts=[]
    for p in mesh.polygons:
        if p.index in face_ids:
            layouts.extend((p.index, tuple(t.vertices), tuple(t.loops)) for t in mesh.loop_triangles if t.polygon_index == p.index)
        else:
            layouts.append((p.index, tuple(p.vertices), tuple(p.loop_indices)))
    import bpy
    new=bpy.data.meshes.new(mesh.name+'__scoped_triangle_partition')
    new.from_pydata([tuple(v.co) for v in mesh.vertices], [tuple(e.vertices) for e in mesh.edges], [v for _,v,_ in layouts])
    for m in mesh.materials:new.materials.append(m)
    for layer in mesh.uv_layers:
        dst=new.uv_layers.new(name=layer.name)
        for p, (_,_,oldloops) in zip(new.polygons,layouts):
            for loop,oldloop in zip(p.loop_indices,oldloops):dst.data[loop].uv=layer.data[oldloop].uv
    for p,(old_id,_,_) in zip(new.polygons,layouts):
        p.material_index=mesh.polygons[old_id].material_index
        p.use_smooth=mesh.polygons[old_id].use_smooth
    new.update();new.calc_loop_triangles()
    def snapshot(m, origins):
        records={p.index:{'polygon':[],'triangles':[]} for p in mesh.polygons}
        for p in m.polygons:records[origins[p.index]]['polygon'].append(tuple(p.vertices))
        for t in m.loop_triangles:
            p=m.polygons[t.polygon_index]
            corners=[dict(position=tuple(m.vertices[v].co),uv={l.name:tuple(l.data[loop].uv) for l in m.uv_layers if l.name not in atlas_uv_names}) for v,loop in zip(t.vertices,t.loops)]
            records[origins[t.polygon_index]]['triangles'].append(dict(corners=corners,material=(p.material_index,p.use_smooth)))
        return {obj.name:dict(invariants=dict(vertices=[tuple(v.co) for v in m.vertices],matrix=[tuple(r) for r in obj.matrix_world],materials=[m.name if m else None for m in m.materials],uv_names=[l.name for l in m.uv_layers]),polygons=records)}
    try:
        report=verify_equivalence(snapshot(mesh,list(range(len(mesh.polygons)))),snapshot(new,[old for old,_,_ in layouts]),{obj.name:sorted(face_ids)})
    except Exception:
        bpy.data.meshes.remove(new);raise
    report['original_polygon_by_new_polygon']=[old for old,_,_ in layouts]
    report['atlas_uv_names']=list(atlas_uv_names)
    return new,report
