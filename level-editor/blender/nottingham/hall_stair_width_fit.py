"""Fit the upper interior stair edge to its measured source silhouette."""
import hashlib
import json
import math


def apply():
    import bpy
    import bmesh
    from mathutils import Vector

    objects = [o for o in bpy.data.collections['nottingham Working'].all_objects if o.type == 'MESH']
    obj = next(o for o in objects if o.get('source_node') == 'building-500'
               and not o.get('projection_component'))
    assert not obj.get('hall_stair_width_fit'), 'Stair width already fitted'
    assert len(obj.data.vertices) == 42, 'Expected the reviewed nine-step extrusion'
    def geometry(o):
        value = ([list(v.co) for v in o.data.vertices], [list(p.vertices) for p in o.data.polygons],
                 [list(r) for r in o.matrix_world])
        return hashlib.sha256(json.dumps(value).encode()).hexdigest()
    protected = {o.name: geometry(o) for o in objects if o != obj}
    s, c = math.sin(math.radians(35)), math.cos(math.radians(35))
    inverse = obj.matrix_world.inverted()
    old = [obj.matrix_world @ v.co for v in obj.data.vertices]
    depths = [-v.y * s for v in old[21:]]
    near, far = min(depths), max(depths)
    assert 1198 < near < 1200 and 1237 < far < 1239, (near, far)
    rows = []
    for index in range(21, 42):
        v = old[index]
        y, z = -v.y * s, v.z * c
        inset = 5 * (far - y) / (far - near)
        fitted = Vector((v.x - inset, -(y + inset) / s, v.z))
        obj.data.vertices[index].co = inverse @ fitted
        rows.append(dict(vertex=index, native_inset=inset,
                         source_before=[v.x, y-z], source_after=[fitted.x, y+inset-z]))
    obj.data.update()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bad = sum(not e.is_manifold for e in bm.edges)
    degenerate = sum(f.calc_area() < 1e-8 for f in bm.faces)
    assert bad == degenerate == 0, (bad, degenerate)
    bm.to_mesh(obj.data)
    bm.free()
    assert all((obj.matrix_world @ obj.data.vertices[i].co - old[i]).length < 1e-4 for i in range(21))
    assert protected == {o.name: geometry(o) for o in objects if o != obj}
    obj['hall_stair_width_fit'] = 'upper-right-inset5-taper-to-foot-v1'
    return dict(status='APPLIED', source_node='building-500', step_count=9,
                geometry_changed='Right side narrows at the upper landing, tapering to the unchanged lower foot.',
                native_height_unchanged=True, opposite_side_unchanged=True,
                nonmanifold_edges=bad, degenerate_faces=degenerate,
                protected_mesh_count=len(protected), right_profile=rows,
                source_evidence='castle-audit/hall39-blocker-independent/stair-source-grid.png',
                limitation='Existing material UVs require rebaking after this geometry correction.')
