"""Measured market-stall battens and explicit state-only prop review.

Preserve native obstacle identities and transforms. Castle state proxies and
courtyard receivers are deliberately unchanged when artwork supplies no better
surface evidence. Call refine(asset_id), then regenerate source projection.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
ASSETS = {
    'nottingham-castle-yard-mission-props': set(range(547, 551)),
    'nottingham-church-road-mission-props': set(range(551, 555)),
    'nottingham-castle-courtyard-ground': {366},
}
TAG = 'nottingham_market_battens_v1'


def _snapshot(obj):
    return {'vertices': [list(v.co) for v in obj.data.vertices],
            'faces': [list(p.vertices) for p in obj.data.polygons],
            'uv': [[list(c.uv) for c in layer.data] for layer in obj.data.uv_layers],
            'matrix': [list(row) for row in obj.matrix_world]}


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _battens(obj, obstacle):
    """Two narrow cross battens lie on each measured inclined board receiver."""
    if TAG in obj:
        record = json.loads(obj[TAG])
        return {**record, 'already_applied': True}
    before = _snapshot(obj)
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    corners = [Vector((p['x'], -p['y']/sine, p['z_top']/cosine))
               for p in obstacle['points']]
    # 552 traverses short,long,short,long; 553 traverses long,short,long,short.
    if obj['source_node'] == 'building-553':
        corners = [corners[i] for i in (0, 3, 2, 1)]
    a, b, c, d = corners
    normal = (b-a).cross(d-a).normalized()
    if normal.z < 0:
        normal.negate()
    inverse = obj.matrix_world.inverted()
    native_points = obstacle['points']
    vertices = [inverse @ Vector((p['x'], -p['y']/sine, p[z]/cosine))
                for z in ('z_bottom', 'z_top') for p in native_points]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    material_indices = [0]*6
    details = []
    for fraction in (.20, .70):
        half = .018
        base = [a.lerp(d, fraction-half), b.lerp(c, fraction-half),
                b.lerp(c, fraction+half), a.lerp(d, fraction+half)]
        first = len(vertices)
        vertices.extend(inverse @ p for p in base)
        vertices.extend(inverse @ (p+normal*.8) for p in base)
        faces.extend(tuple(first+i for i in face) for face in
                     [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
        material_indices.extend([0]*6)
        details.append({'fraction_along_long_edge': fraction,
                        'width_fraction': half*2, 'normal_depth': .8,
                        'projected_centerline': [[float(p.x),float(-p.y*sine-p.z*cosine)]
                                                 for p in (a.lerp(d,fraction), b.lerp(c,fraction))]})
    mesh = bpy.data.meshes.new(obj.data.name+' / cross battens')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    for material in obj.data.materials:
        mesh.materials.append(material)
    for face, index in zip(mesh.polygons, material_indices):
        face.material_index = index
    uv = mesh.uv_layers.new(name='Source projection')
    for loop in mesh.loops:
        p = obj.matrix_world @ mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (p.x/2304, 1-(-p.y*sine-p.z*cosine)/3520)
    obj.data = mesh
    record = {'source_node': obj['source_node'], 'recipe': 'two-visible-market-cross-battens',
              'before_sha256': _hash(before), 'after_sha256': _hash(_snapshot(obj)),
              'vertices_before': len(before['vertices']), 'vertices_after': len(vertices),
              'faces_before': len(before['faces']), 'faces_after': len(faces),
              'batten_count': 2, 'measurements': details,
              'preserved': ['Object identity', 'Parent', 'World transform', 'Native slab contour'],
              'inference': ['Batten depth 0.8 world units is conservative; source establishes narrow raised strips.',
                            'Two batten centers estimated at 20% and 70% of slab length from source crop.',
                            'Native slab corner envelope reconstructed as closed solid; concealed underside is inferred.'],
              'limitations': ['Slab board seams remain painted detail; no unsupported plank count is asserted.',
                              'Fish and unassigned adjacent vessels remain source artwork; container/support inferences are recorded separately.']}
    obj[TAG] = json.dumps(record, sort_keys=True)
    return record


def _lower_props(obj):
    tag = 'nottingham_market_lower_props_v1'
    if tag in obj:
        return {**json.loads(obj[tag]), 'already_applied': True}
    before = _snapshot(obj)
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    verts, faces = [], []
    def box(quad, depth):
        start = len(verts)
        verts.extend(p-Vector((0,0,depth)) for p in quad)
        verts.extend(quad)
        faces.extend(tuple(start+i for i in f) for f in
                     [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    def vessel(cx, top_y, bottom_y, radius, opening):
        cy = -bottom_y/sine
        height = (bottom_y-top_y)/cosine
        # Preserve the visibly narrow projected top ellipse independently from height.
        ry = radius*.43/sine
        profile = [(0,.88),(.05,.91),(.18,.97),(.22,1.04),(.26,.99),
                   (.53,1.04),(.72,1.0),(.76,1.06),(.80,.97),(1,.90)]
        if opening:
            profile = [(0,.73),(.05,.75),(.45,.88),(.91,1),(1,1.03),(1,.83),(.18,.62)]
        start = len(verts)
        for fraction, radial in profile:
            verts.extend(Vector((cx+radius*radial*math.cos(i*math.tau/16),
                                 cy+ry*radial*math.sin(i*math.tau/16),height*fraction))
                         for i in range(16))
        for row in range(len(profile)-1):
            for i in range(16):
                j=(i+1)%16
                faces.append(tuple(start+k for k in (row*16+i,row*16+j,(row+1)*16+j,(row+1)*16+i)))
        faces.append(tuple(start+i for i in reversed(range(16))))
        faces.append(tuple(start+(len(profile)-1)*16+i for i in range(16)))
        return {'top_center_source':[cx,top_y], 'ground_center_source':[cx,bottom_y],
                'radius_source_x':radius,'radius_source_y':radius*.43,'segments':16,'open':opening}
    node = obj['source_node']
    if node == 'building-551':
        measurements = {'shelf_top_source':[[1501,535],[1526,529],[1540,553],[1527,566]],
                        'shelf_elevation':22.334002}
        quad = [Vector((x,-(y+22.334002)/sine,22.334002/cosine))
                for x,y in measurements['shelf_top_source']]
        box(quad, 2)
        for p in (quad[0].lerp(quad[3],.80), quad[1].lerp(quad[2],.75)):
            corner=[p+Vector((x,y,0)) for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
            box(corner,p.z)
        measurements['barrel']=vessel(1542,571,594,10,False)
        changes=['Replace broad low clutter prism with thin measured shelf.',
                 'Add two conservative shelf supports.',
                 'Recover foreground barrel round silhouette and hoop profile.']
    else:
        measurements={'bucket':vessel(1783,550,568,6,True)}
        changes=['Replace box proxy with tapered open bucket and thick rim.']
    inverse=obj.matrix_world.inverted()
    mesh=bpy.data.meshes.new(obj.data.name+' / measured containers')
    mesh.from_pydata([inverse@v for v in verts],[],faces)
    mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    for material in obj.data.materials:mesh.materials.append(material)
    uv=mesh.uv_layers.new(name='Source projection')
    for loop in mesh.loops:
        p=verts[loop.vertex_index]
        uv.data[loop.index].uv=(p.x/2304,1-(-p.y*sine-p.z*cosine)/3520)
    obj.data=mesh
    record={'source_node':node,'recipe':'measured-market-lower-props',
            'before_sha256':_hash(before),'after_sha256':_hash(_snapshot(obj)),
            'source_measurements':measurements,'changes':changes,
            'vertices_before':len(before['vertices']),'vertices_after':len(verts),
            'faces_before':len(before['faces']),'faces_after':len(faces),
            'inference':['Concealed barrel rear continues the visible rounded contour.',
                         'Hoop depth and container wall thickness are conservative.',
                         'Shelf support positions and thickness are approximate from occluded painted legs.'],
            'limitations':['Fish remain painted source detail.',
                           'Other adjacent vessels outside the native receiver footprint are not assigned to this object.']}
    obj[tag]=json.dumps(record,sort_keys=True)
    return record


def refine(asset_id):
    if asset_id not in ASSETS:
        raise ValueError(f'Unsupported asset: {asset_id}')
    nodes = {f'building-{i:03}' for i in ASSETS[asset_id]}
    sources = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.get('source_node') in nodes]
    if len(sources) != len(nodes) or {o['source_node'] for o in sources} != nodes:
        raise ValueError(f'Missing or duplicate native receiver: {asset_id}')
    outside = {o.name: _hash(_snapshot(o)) for o in bpy.context.scene.objects
               if o.type == 'MESH' and o not in sources}
    transforms = {o.name: [list(row) for row in o.matrix_world] for o in sources}
    native = json.loads((WORK/'baseline/nottingham.rhp.json').read_text())
    changes = []
    unchanged = []
    for obj in sorted(sources, key=lambda o:o['source_node']):
        number = int(obj['source_node'].split('-')[-1])
        if number in (551, 554):
            changes.append(_lower_props(obj))
        elif number in (552, 553):
            changes.append(_battens(obj, native['sight_obstacles'][number]))
        else:
            reason = ('No visible alternate prop artwork in isolated initial/applied patch009 states. Native obstacle state must remain an untextured proxy; no visible form invented.'
                      if 547 <= number <= 550 else
                      'The native 34-point courtyard floor at constant top elevation follows the visible raised paved platform. Painted paving joints are not height evidence; preserve contour and elevation.'
                      if number == 366 else
                      'Native low clutter receiver is coarse but the source does not unambiguously assign each barrel, bucket or fish to this receiver; retain pending separate component ownership review.')
            unchanged.append({'source_node': obj['source_node'], 'no_change_reason': reason,
                              'geometry_uv_transform_sha256': _hash(_snapshot(obj))})
    for obj in sources:
        if transforms[obj.name] != [list(row) for row in obj.matrix_world]:
            raise ValueError(f'Transform drift: {obj.name}')
    for name, digest in outside.items():
        if digest != _hash(_snapshot(bpy.data.objects[name])):
            raise ValueError(f'Outside mutation: {name}')
    return {'asset_id': asset_id, 'status': 'refinement-in-progress' if changes else 'source-audited-unchanged',
            'changes': changes, 'unchanged': unchanged, 'outside_objects_unchanged': True,
            'transform_drift': 0, 'projection_status': 'stale; rerun modified packet' if changes else 'unchanged',
            'geometry_approval': 'pending', 'texture_generation': 'not started',
            'evidence': 'environment-audit/props/evidence.json'}
