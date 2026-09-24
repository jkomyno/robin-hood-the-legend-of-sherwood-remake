"""Keep the traced thatch outline on a coherent roof plane instead of folded eaves."""
import math
import bpy
from mathutils import Vector


def apply():
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    owned = [o for o in bpy.context.scene.objects if o.type == 'MESH'
             and o.get('asset_group') == 'nottingham-village-mill' and not o.hide_render]
    roof = next(o for o in owned if o.get('source_node') == 'building-237')
    lean = next(o for o in owned if o.get('source_node') == 'building-238')
    rear = Vector((1617.0413, 2625.9927, 150.009))
    front = Vector((1665.112, 2746.1895, 120))
    contact = Vector((1580.0377, 2703.1677, 95.268005))
    normal = (front - rear).cross(contact - rear)
    constant = normal.dot(rear)
    changes = []
    for obj in [roof, lean]:
        inverse = obj.matrix_world.inverted()
        for vertex in obj.data.vertices:
            before = obj.matrix_world @ vertex.co
            if before.z < 1 or (obj == lean and abs(before.x - 1591.8282) > .01):
                continue
            source_y = -before.y * sine - before.z * cosine
            height = (constant - normal.x * before.x - normal.y * source_y) / (normal.y + normal.z)
            after = Vector((before.x, -(source_y + height) / sine, height / cosine))
            vertex.co = inverse @ after
            assert abs((-after.y * sine - after.z * cosine) - source_y) < .001
            changes.append(dict(node=obj.get('source_node'), vertex=vertex.index,
                                source=[before.x, source_y], before_world=list(before), after_world=list(after),
                                native_height=height))
        obj.data.update()
    # Overhanging thatch is separate from the vertical supporting walls.
    from refine_village_secondary import replace
    import bmesh
    points = [roof.matrix_world @ v.co for v in roof.data.vertices]
    outer = [points[i] for i in [4, 5, 6, 9, 10]]
    lower = [p.copy() for p in points[:4]]
    lower[3].y = outer[-1].y
    upper = []
    for point in lower:
        y = -point.y * sine
        height = (constant - normal.x * point.x - normal.y * y) / normal.z - .5
        upper.append(Vector((point.x, point.y, height / cosine)))
    replace(roof, lower + upper,
            [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],
            'Mill vertical body below overhanging thatch')
    roof_points = [p - Vector((0,0,2/cosine)) for p in outer] + outer
    count = len(outer)
    faces = [tuple(reversed(range(count))), tuple(range(count,2*count))]
    faces += [(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
    mesh = bpy.data.meshes.new('Mill thatch slab union')
    mesh.from_pydata(roof_points, [], faces)
    mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    slab = bpy.data.objects.new('Mill thatch slab union',mesh)
    bpy.context.collection.objects.link(slab)
    bpy.context.view_layer.objects.active = roof
    modifier = roof.modifiers.new('Overhang and vertical wall union','BOOLEAN')
    modifier.operation = 'UNION'; modifier.solver = 'EXACT'; modifier.object = slab
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(slab,do_unlink=True)
    bm = bmesh.new(); bm.from_mesh(roof.data)
    nonmanifold = sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    if nonmanifold: raise ValueError(('Nonmanifold roof/body union',nonmanifold))
    shell = dict(nonmanifold_edges=nonmanifold, vertices=len(roof.data.vertices),
                 faces=len(roof.data.polygons), roof_native_thickness=2,
                 wall_support='Vertical walls with source-fitted rear timber-post contact')
    return dict(shell=shell, plane_anchors_native=[list(v) for v in [rear, front, contact]], vertices=changes,
                limitation='Depth along each source ray is inferred. The roof plane preserves every traced source contour; the lean-to front ridge shifts about five native height units to meet it.')
