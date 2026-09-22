"""Replace dining benches' deep block envelopes with seats and paired supports.

The seat's four measured top corners are preserved. Support width and placement
are conservative hidden-depth hypotheses, checked against native furniture masks.
"""
import collections

import bpy
import bmesh
from mathutils import Vector

ASSET = 'leicester-great-keep'
BENCHES = tuple(f'building-{i}' for i in (307, 308, 311, 312))
TABLES = tuple(f'building-{i}' for i in (309, 310))
FLOOR_Z = 170.91
TAG = 'leicester-keep-dining-seats-v1'


def top_ring(obj):
    vertices = [obj.matrix_world @ v.co for v in obj.data.vertices]
    highest = max(v.z for v in vertices)
    top = [list(p.vertices) for p in obj.data.polygons
           if all(vertices[i].z > highest-.5 for i in p.vertices)]
    counts = collections.Counter(tuple(sorted((p[i], p[(i+1) % len(p)])))
                                 for p in top for i in range(len(p)))
    edges = [(p[i], p[(i+1) % len(p)]) for p in top for i in range(len(p))
             if counts[tuple(sorted((p[i], p[(i+1) % len(p)])))] == 1]
    successor = dict(edges)
    if len(edges) != 4 or len(successor) != 4:
        raise RuntimeError(f'{obj.name}: expected one quadrilateral seat cap')
    indices = [edges[0][0]]
    while len(indices) < 4:
        indices.append(successor[indices[-1]])
    ring = [vertices[i] for i in indices]
    # Orient the first parametric direction along the long side.
    if (ring[1]-ring[0]).length < (ring[2]-ring[1]).length:
        ring = ring[1:]+ring[:1]
    return ring, highest-min(v.z for v in vertices)


def seating_mesh(obj, tabletop=False):
    corners, original_depth = top_ring(obj)
    thickness = original_depth if tabletop else 3.5
    if not 1 < thickness < 10:
        raise RuntimeError(f'{obj.name}: implausible seat thickness {thickness}')
    xs, ys = [0., .08, .18, .82, .92, 1.], [0., .12, .24, .76, .88, 1.]
    cells = set()
    for x in range(5):
        for y in range(5):
            cells.add((x, y, 1))
            if x in (1, 3) and (y in (1, 3) if tabletop else y in (1, 2, 3)):
                cells.add((x, y, 0))
    vertices, faces, lookup = [], [], {}
    def vertex(key):
        if key not in lookup:
            x, y, level = key
            u, v = xs[x], ys[y]
            point = ((1-u)*(1-v)*corners[0] + u*(1-v)*corners[1]
                     + u*v*corners[2] + (1-u)*v*corners[3])
            point.z = FLOOR_Z if level == 0 else point.z-thickness if level == 1 else point.z
            lookup[key] = len(vertices)
            vertices.append(obj.matrix_world.inverted() @ point)
        return lookup[key]
    for x,y,z in sorted(cells):
        sides = [((-1,0,0),((x,y,z),(x,y,z+1),(x,y+1,z+1),(x,y+1,z))),
                 ((1,0,0),((x+1,y,z),(x+1,y+1,z),(x+1,y+1,z+1),(x+1,y,z+1))),
                 ((0,-1,0),((x,y,z),(x+1,y,z),(x+1,y,z+1),(x,y,z+1))),
                 ((0,1,0),((x,y+1,z),(x,y+1,z+1),(x+1,y+1,z+1),(x+1,y+1,z))),
                 ((0,0,-1),((x,y,z),(x,y+1,z),(x+1,y+1,z),(x+1,y,z))),
                 ((0,0,1),((x,y,z+1),(x+1,y,z+1),(x+1,y+1,z+1),(x,y+1,z+1)))]
        for direction, quad in sides:
            if tuple(a+b for a,b in zip((x,y,z),direction)) not in cells:
                faces.append(tuple(vertex(key) for key in quad))
    mesh = bpy.data.meshes.new(obj.name+' / supported seat')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bad_edges=sum(not e.is_manifold for e in bm.edges)
    bad_faces=sum(f.calc_area()<1e-7 for f in bm.faces)
    if bad_edges or bad_faces:
        bm.free();bpy.data.meshes.remove(mesh)
        raise RuntimeError(f'{obj.name}: invalid seat mesh {bad_edges}/{bad_faces}')
    bm.to_mesh(mesh);bm.free()
    for material in obj.data.materials:mesh.materials.append(material)
    mesh.uv_layers.new(name='UVMap')
    obj.data=mesh
    obj['refinement_recipe']=TAG
    obj['todo']='Validate support positions against native furniture masks after reprojection.'
    return {'source_node':obj['source_node'],'vertices':len(mesh.vertices),'faces':len(mesh.polygons),
            'support_count':4 if tabletop else 2,'floor_z':FLOOR_Z,'seat_thickness':thickness,
            'nonmanifold_edges':bad_edges,'degenerate_faces':bad_faces,
            'limitation':'Support placement and thickness require source-mask review; hidden depth is inferred.'}


def refine(collection_name='Leicester Working'):
    nodes = set(BENCHES+TABLES)
    objects=[o for o in bpy.data.collections[collection_name].all_objects
             if o.type=='MESH' and o.get('asset_group')==ASSET and o.get('source_node') in nodes]
    if len(objects)!=len(nodes) or {o['source_node'] for o in objects}!=nodes:
        raise RuntimeError('Dining furniture ownership incomplete or duplicated')
    return [seating_mesh(obj,obj['source_node'] in TABLES) for obj in objects
            if obj.get('refinement_recipe')!=TAG]
