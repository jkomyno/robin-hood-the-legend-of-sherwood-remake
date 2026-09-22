"""Measured visible wattle uprights and separate pickets on native fence paths."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

VERSION = 'leicester-measured-timber-v1'
SUPPORTED = {30, 32, 53}
# Ground centerlines in source-map coordinates; z is reconstructed at35degrees.
PATHS = {
    30: [(1991.5, 490), (2058.4, 468.9), (2183.5, 449), (2208, 448.5),
         (2234, 440), (2285.1, 482.9)],
    32: [(2263, 1512), (2299.5, 1572), (2384, 1596.5), (2442, 1592.5),
         (2482, 1583.5), (2499, 1589.5), (2618, 1593.5), (2644, 1604.5), (2703, 1609.94)],
    53: [(3061.14, 1147.31), (3136.08, 1162.07)],
}
# Centers and tips traced on3x crops for030/032 and4x for053.
# Unseen uprights are not counted.
TRACES = {
    30: [(171, 134), (204, 123), (240, 110), (270, 99), (292, 91),
         (318, 115), (414, 78), (435, 64), (456, 79), (494, 72), (526, 67),
         (561, 62), (600, 61), (639, 46), (686, 48), (712, 45),
         (755, 31), (770, 31), (804, 53), (830, 72), (862, 106), (884, 122)],
    32: [(433, 285), (453, 286), (470, 283), (491, 280), (516, 283),
         (539, 281), (560, 286), (581, 279), (602, 263), (624, 267),
         (646, 266), (670, 263), (691, 264), (713, 265), (735, 273),
         (757, 283), (780, 291), (805, 293), (828, 284), (850, 280),
         (873, 291), (894, 285), (916, 282), (938, 283), (960, 282),
         (981, 284), (1004, 287), (1025, 292), (1048, 282), (1070, 285),
         (1090, 288), (1113, 290), (1133, 300), (1156, 306), (1177, 316),
         (1200, 319), (1221, 322), (1244, 329), (1264, 332), (1284, 337)],
    53: [(60, 61), (80, 86), (106, 91), (130, 81), (159, 105), (177, 94),
         (200, 64), (222, 106), (244, 107), (264, 103), (286, 111), (311, 114), (334, 96)],
}
CROP_ORIGINS = {30: (1978, 405), 32: (2251, 1468), 53: (3048, 1102)}


def signature(obj):
    return hashlib.sha256(json.dumps({'v': [list(v.co) for v in obj.data.vertices],
        'f': [list(f.vertices) for f in obj.data.polygons]}, sort_keys=True).encode()).hexdigest()


def refine(obj):
    node = int(obj['source_node'].split('-')[-1])
    if node not in SUPPORTED:
        raise ValueError('Measured timber recipe supports only nodes030,032 and053')
    matrix = obj.matrix_world.copy()
    before = signature(obj)
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    path = PATHS[node]
    vertices, faces = [], []

    def at(x, height=0):
        for a, b in zip(path, path[1:]):
            if a[0] <= x <= b[0]:
                t = (x-a[0])/(b[0]-a[0])
                y = a[1]+t*(b[1]-a[1])
                return Vector((x, -y/sine, height/cosine)), y
        raise ValueError('Traced timber lies outside the native fence path')

    def beam(a, b, thickness, breadth):
        direction = (b-a).normalized()
        reference = Vector((0, 0, 1)) if abs(direction.z) < .9 else Vector((1, 0, 0))
        side = direction.cross(reference).normalized()*thickness/2
        up = direction.cross(side).normalized()*breadth/2
        offset = len(vertices)
        vertices.extend(p+s*side+u*up for p in (a, b) for s, u in [(-1,-1),(1,-1),(1,1),(-1,1)])
        faces.extend(tuple(offset+i for i in face) for face in
                     [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])

    ox, oy = CROP_ORIGINS[node]
    enlargement = 4 if node == 53 else 3
    tips = []
    for cx, cy in TRACES[node]:
        x, top_y = ox+cx/enlargement, oy+cy/enlargement
        bottom, ground_y = at(x)
        height = ground_y-top_y
        if height <= 0:
            raise ValueError('Measured timber tip lies below ground')
        beam(bottom, bottom+Vector((0, 0, height/cosine)), 1.5 if node in (32, 53) else 1.7,
             5.0 if node in (32, 53) else 2.2)
        tips.append(dict(x=x, top_y=top_y, height_source_pixels=height))

    if node == 30:
        # Twelve visible woven rows form a permeable panel; half-row staggering
        # expresses the alternating front/back weave without filling its gaps.
        levels = [1.2+1.45*i for i in range(12)]
        knots = sorted(set([p[0] for p in path]+[t['x'] for t in tips]))
        for row, height in enumerate(levels):
            for index, (left, right) in enumerate(zip(knots, knots[1:])):
                a, _ = at(left, height); b, _ = at(right, height)
                a.y += .6 if (row+index)%2 else -.6
                b.y += -.6 if (row+index)%2 else .6
                beam(a, b, .8, .85/cosine)
    elif node == 32:
        levels = [5., 25.]
        for a, b in zip(path, path[1:]):
            for height in levels:
                left, _ = at(a[0], height); right, _ = at(b[0], height)
                beam(left+Vector((0, 1.5, 0)), right+Vector((0, 1.5, 0)), 1.5, 2.2/cosine)
        # Keep concealed receiver spans as explicit uncertain panels. They are
        # not an invented continuation of the visible repeated board count.
        visible_left, visible_right = tips[0]['x']-3, tips[-1]['x']+3
        for a, b in zip(path, path[1:]):
            for left, right in ((a[0], min(b[0], visible_left)), (max(a[0], visible_right), b[0])):
                if right <= left:
                    continue
                start, _ = at(left, 15.5); end, _ = at(right, 15.5)
                beam(start, end, 2.0, 31/cosine)
    else:
        levels = []

    mesh = bpy.data.meshes.new(obj.name+' measured timber')
    inverse = matrix.inverted()
    mesh.from_pydata([inverse@v for v in vertices], [], faces)
    for material in obj.data.materials:
        mesh.materials.append(material)
    # Fresh projection replaces these deterministic fallback coordinates.
    mesh.uv_layers.new(name='Timber fallback')
    for loop in mesh.loops:
        world = vertices[loop.vertex_index]
        mesh.uv_layers.active.data[loop.index].uv = (world.x/3136, (-world.y*sine-world.z*cosine)/1984)
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    topology = dict(vertices=len(bm.verts), faces=len(bm.faces),
                    nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
                    degenerate_faces=sum(f.calc_area()<1e-7 for f in bm.faces))
    if topology['nonmanifold_edges'] or topology['degenerate_faces']:
        raise ValueError('Timber topology failed: '+str(topology))
    bm.to_mesh(mesh); bm.free(); mesh.update()
    previous = obj.data; obj.data = mesh
    if previous.users == 0:
        bpy.data.meshes.remove(previous)
    obj['leicester_geometry_recipe'] = VERSION
    if obj.matrix_world != matrix:
        raise ValueError('Timber recipe changed transform')
    return dict(source_node=obj['source_node'], before_geometry_sha256=before,
                after_geometry_sha256=signature(obj), world_transform_drift=0,
                traced_upright_count=len(tips), traced_tips=tips, rail_levels=levels,
                topology=topology, limitations=[
                    'Manual tip measurements have roughly two source-pixel uncertainty; weathered tips remain texture detail.',
                    'Post depth, board thickness and concealed back faces are inferred.',
                    'Native ground bends anchor depth; source-only projection must reject foliage and roof occlusion.',
                    'The final palisade edge is clipped by the artwork boundary; no off-image posts or unobserved rails are invented.' if node == 53 else
                    'Concealed end spans retain uncertain receiver panels; no unseen upright count is asserted.' if node == 32 else
                    'Wattle weave phase is an inferred depth alternation; fine irregular twigs remain texture detail.'])


def run(workspace):
    workspace = Path(workspace).resolve()
    config = json.loads((workspace/'workspace.json').read_text())
    if Path(bpy.data.filepath).resolve() != workspace/'model.blend':
        raise ValueError('Open the isolated worker model.blend')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from refinement_workspace import validate
    validate(workspace)
    targets = [o for o in bpy.data.collections[config['collection_name']].all_objects
               if o.type == 'MESH' and o.get('asset_group') == config['asset_id']]
    if not targets or any(int(o['source_node'].split('-')[-1]) not in SUPPORTED for o in targets):
        raise ValueError('Workspace contains unsupported timber parts')
    records = [refine(o) for o in targets]
    hashes = [signature(o) for o in targets]
    for obj in targets:
        refine(obj)
    if hashes != [signature(o) for o in targets]:
        raise ValueError('Timber recipe is not idempotent')
    report = dict(recipe=VERSION, asset_id=config['asset_id'], objects=records, idempotence='PASS',
                  projection_status='STALE; regenerate modified packet', approval_status='refinement-in-progress',
                  texture_generation='not-started')
    validate(workspace)
    (workspace/'inspection').mkdir(exist_ok=True)
    (workspace/'inspection/timber-recipe.json').write_text(json.dumps(report, indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'))
    return report
