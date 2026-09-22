"""Source-supported stump rounding and environment surface-connectivity review.

The imported receivers have per-face vertices. Join exactly coincident vertices
while retaining every polygon corner UV; do not invent concealed rock, tree or
terrain surfaces. Round the two visible cut stumps using preserved extrema and
height anchors, documenting their concealed rear half. Call refine(asset_id) in
the isolated reviewed workspace, then
rerun refinement_workspace.modified before evaluating projected materials.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ASSETS = {
    'nottingham-castle-courtyard-ground': {'building-366'},
    'nottingham-castle-west-rocks': {'building-478', 'building-479', 'building-480', 'building-481', 'building-484'},
    'nottingham-forest-tree-trunks': {f'building-{i:03}' for i in range(541, 546)},
    'nottingham-forest-bundled-tree': {'building-541'},
    'nottingham-forest-wood-stack': {'building-542'},
    'nottingham-forest-west-stump': {'building-543'},
    'nottingham-forest-tall-trunk': {'building-544'},
    'nottingham-forest-east-stump': {'building-545'},
    'nottingham-forest-rock-outcrop': {'building-546'},
    'nottingham-southwest-prison-road-props': {'building-482', 'building-483'},
    'nottingham-castle-yard-mission-props': {f'building-{i:03}' for i in range(547, 551)},
    'nottingham-church-road-mission-props': {f'building-{i:03}' for i in range(551, 555)},
    'nottingham-terrain-ground': {'ground'},
}


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _geometry(obj):
    return {'vertices': [list(v.co) for v in obj.data.vertices],
            'faces': [list(p.vertices) for p in obj.data.polygons]}


def _corners(obj):
    """Index-independent face-corner positions and UVs prove unchanged receivers."""
    layers = list(obj.data.uv_layers)
    records = []
    for face in obj.data.polygons:
        corners = []
        for li in face.loop_indices:
            vertex = obj.data.vertices[obj.data.loops[li].vertex_index]
            corners.append([list(vertex.co), [list(layer.data[li].uv) for layer in layers]])
        records.append({'material': face.material_index, 'corners': corners})
    return records


def _topology(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    visited = set()
    components = 0
    for vertex in bm.verts:
        if vertex in visited:
            continue
        components += 1
        pending = [vertex]
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            pending.extend(edge.other_vert(current) for edge in current.link_edges)
    result = {'vertices': len(bm.verts), 'edges': len(bm.edges), 'faces': len(bm.faces),
              'connected_components': components,
              'boundary_edges': sum(edge.is_boundary for edge in bm.edges),
              'nonmanifold_edges': sum(not edge.is_manifold for edge in bm.edges),
              'degenerate_faces': sum(face.calc_area() < 1e-9 for face in bm.faces)}
    bm.free()
    return result


def _round_stump(obj):
    tag = 'nottingham_stump_recipe_v1'
    if obj.get(tag):
        return json.loads(obj[tag])
    before = _geometry(obj)
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    cx, cy = (lo[0]+hi[0])/2, (lo[1]+hi[1])/2
    radius = (hi[0]-lo[0])/2
    count = 16
    inverse = obj.matrix_world.inverted()
    vertices = [inverse @ Vector((cx+radius*math.cos(i*2*math.pi/count),
                                  cy+radius*math.sin(i*2*math.pi/count), z))
                for z in [lo[2], hi[2]] for i in range(count)]
    faces = [tuple(reversed(range(count))), tuple(range(count,2*count))]
    faces += [(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
    mesh = bpy.data.meshes.new(obj.name+' / rounded stump')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv = mesh.uv_layers.new(name='Source projection')
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    for loop in mesh.loops:
        p = obj.matrix_world @ mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (p.x/2304, 1-(-p.y*sine-p.z*cosine)/3520)
    neutral = bpy.data.materials.get('Nottingham unobserved stump neutral')
    if neutral is None:
        neutral = bpy.data.materials.new('Nottingham unobserved stump neutral')
        neutral.diffuse_color = (.5,.5,.5,1)
    mesh.materials.append(neutral)
    obj.data = mesh
    topology = _topology(mesh)
    if topology['nonmanifold_edges'] or topology['degenerate_faces']:
        raise ValueError(f'Invalid rounded stump: {obj.name}')
    report = {'source_node':obj['source_node'], 'recipe':'round-cut-stump', 'radial_segments':count,
              'world_center_xy':[cx,cy], 'world_radius':radius, 'world_bottom_top':[lo[2],hi[2]],
              'before_geometry_sha256':_hash(before),'after_geometry_sha256':_hash(_geometry(obj)),
              'validation':topology, 'source_evidence':'Visible round cut end and continuous curved bark in native Day crop',
              'preserved_anchors':['World horizontal center','World vertical center of footprint','Left/right projected extrema','Bottom/top heights'],
              'inference':['Hidden rear half continues the visible cylindrical form.','Underside is a neutral closed disk; concealed roots are not modeled.'],
              'approval':'pending','projection_status':'stale; requires modified source projection'}
    obj[tag] = json.dumps(report,sort_keys=True)
    return report


def _platform(sources):
    """Recover the measured prison-road timber frame and five stair treads."""
    objects={obj['source_node']:obj for obj in sources}
    tag='nottingham_prison_platform_v1'
    if objects['building-482'].get(tag):
        return json.loads(objects['building-482'][tag])
    root=Path(__file__).resolve().parents[3]
    native=json.loads((root/'level-editor/work/nottingham-refinement/baseline/nottingham.rhp.json').read_text())['sight_obstacles']
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    def point(p,z):return Vector((p['x'],-p['y']/sine,z/cosine))
    measured={'left_post_ground':[666,2334],'left_post_top':[666,2239],
              'right_post_ground':[711,2320],'right_post_top':[711,2227],
              'crossboard_left_top_y':[2252,2260,2268],
              'crossboard_right_top_y':[2239,2247,2255], 'visible_treads':5}
    reports=[]
    for node,obj in objects.items():
        before=_hash(_geometry(obj));matrix=[list(row) for row in obj.matrix_world]
        vertices=[];faces=[]
        def box(coords):
            start=len(vertices);vertices.extend(coords)
            faces.extend(tuple(start+i for i in face) for face in
                [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
        def beam(a,b,width):
            axis=(b-a).normalized();side=axis.cross(Vector((0,0,1)))
            if side.length<.01:side=axis.cross(Vector((1,0,0)))
            side.normalize();up=axis.cross(side).normalized()
            ring=[side*x*width/2+up*y*width/2 for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
            box([p+d for p in (a,b) for d in ring])
        points=native[int(node[-3:])]['points']
        if node=='building-482':
            bottom=[point(p,p['z_bottom']) for p in points];top=[point(p,p['z_top']) for p in points]
            box(bottom+top)
            left=Vector((666,-2334/sine,0));right=Vector((711,-2320/sine,0))
            beam(left,left+Vector((0,0,95/cosine)),3.8)
            beam(right,right+Vector((0,0,93/cosine)),3.8)
            for left_y,right_y in zip(measured['crossboard_left_top_y'],measured['crossboard_right_top_y']):
                a=left+Vector((0,0,(2334-left_y)/cosine));b=right+Vector((0,0,(2320-right_y)/cosine))
                d=Vector((0,0,-6/cosine));thickness=Vector((0,2,0))
                box([a,b,b+d,a+d,a+thickness,b+thickness,b+d+thickness,a+d+thickness])
            for p in top:
                beam(Vector((p.x,p.y,0)),p-Vector((0,0,3)),3.4)
            for i in range(4):beam(top[i]-Vector((0,0,3)),top[(i+1)%4]-Vector((0,0,3)),3)
        else:
            low=[point(points[i],0) for i in (3,2)]
            high=[point(points[i],31.800001) for i in (0,1)]
            for i in range(5):
                lo=i/5;hi=(i+1)/5;z=31.800001*hi/cosine
                quad=[low[0].lerp(high[0],lo),low[1].lerp(high[1],lo),
                      low[1].lerp(high[1],hi),low[0].lerp(high[0],hi)]
                for p in quad:p.z=z
                box([p-Vector((0,0,2)) for p in quad]+quad)
            for a,b in zip(low,high):beam(a,b-Vector((0,0,2.5)),2.8)
        mesh=bpy.data.meshes.new(obj.name+' / measured timber frame')
        inverse=obj.matrix_world.inverted();mesh.from_pydata([inverse@p for p in vertices],[],faces);mesh.update()
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        uv=mesh.uv_layers.new(name='Source projection')
        for loop in mesh.loops:
            p=obj.matrix_world@mesh.vertices[loop.vertex_index].co
            uv.data[loop.index].uv=(p.x/2304,1-(-p.y*sine-p.z*cosine)/3520)
        for material in obj.data.materials:mesh.materials.append(material)
        obj.data=mesh
        defects=_topology(mesh)
        if defects['nonmanifold_edges'] or defects['degenerate_faces']:raise ValueError(defects)
        if matrix!=[list(row) for row in obj.matrix_world]:raise ValueError('Platform transform drift')
        reports.append({'source_node':node,'before_geometry_sha256':before,'after_geometry_sha256':_hash(_geometry(obj)),
                        'topology':defects,'transform_drift':0})
    report={'recipe':'prison-platform-frame-and-stair','source_measurements':measured,'objects':reports,
            'source_crop':[570,2170,780,2400],
            'changes':['Two measured tall uprights and three separated crossboards.','Deck support feet and four perimeter beams.','Five solid timber stair treads and two stringers.'],
            'inference':['Concealed rear support feet and timber thickness are conservative structural estimates.',
                         'Deck plank irregularities remain in the source artwork.'],
            'approval':'pending','projection_status':'stale; requires modified source projection'}
    objects['building-482'][tag]=json.dumps(report,sort_keys=True)
    return report


def _forest_form(obj):
    """Measured trunk taper/root flare and visible leaning firewood poles."""
    node=obj['source_node'];tag='nottingham_forest_form_v1'
    if obj.get(tag):return json.loads(obj[tag])
    before=_hash(_geometry(obj));vertices=[];faces=[]
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    def rings(coords):
        start=len(vertices);count=len(coords[0])
        for ring in coords:vertices.extend(ring)
        faces.append(tuple(start+i for i in reversed(range(count))))
        for row in range(len(coords)-1):
            for i in range(count):
                a=start+row*count+i;b=start+row*count+(i+1)%count
                faces.append((a,b,b+count,a+count))
        faces.append(tuple(start+(len(coords)-1)*count+i for i in range(count)))
    if node in {'building-541','building-544'}:
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        cx=(min(p.x for p in points)+max(p.x for p in points))/2
        cy=(min(p.y for p in points)+max(p.y for p in points))/2
        height=max(p.z for p in points)
        profile=([(0,21),(14,16),(30,12.5),(height*.58,12.2),(height,14)]
                 if node=='building-541' else [(0,25),(10,20),(30,12),(height*.65,10.5),(height,10)])
        count=20
        coords=[]
        for row,(z,radius) in enumerate(profile):
            coords.append([Vector((cx+radius*math.cos(i*2*math.pi/count),
                                   cy+radius*math.sin(i*2*math.pi/count),z)) for i in range(count)])
        rings(coords)
        changes=['Replaced rectangular trunk with twenty-sided tapered bark volume.',
                 'Modeled flared root collar from the wider visible footprint and narrower bole.']
        measurements={'world_center_xy':[cx,cy],'height_radius_profile':profile,
                      'source_horizontal_extent':[cx-profile[0][1],cx+profile[0][1]],
                      'source_evidence':'Visible taper and flared root collar in the top-edge forest artwork; trunk continues beyond source-image top.'}
        inference=['Rear trunk radius continues the observed rounded form.','Root collar is a conservative continuous flare; individual concealed roots are unspecified.',
                   'Existing top height is retained because the tree continues beyond the artwork; no canopy or complete tree height is inferred.']
    elif node=='building-542':
        cx,cy=1833,-140/sine
        # Seven visible long poles span the front. Five rear and three inner
        # poles form the documented hidden continuation of the compact pile.
        for i in range(15):
            angle=math.pi+i*2*math.pi/12 if i<12 else (i-12)*2*math.pi/3
            base_radius,top_radius=(16,8.5) if i<12 else (7,3)
            bottom=Vector((cx+base_radius*math.cos(angle),cy+base_radius*math.sin(angle),1.2))
            top=Vector((cx+top_radius*math.cos(angle),cy+top_radius*math.sin(angle),(28.5+(i%3)*1.2)/cosine))
            axis=(top-bottom).normalized();side=axis.cross(Vector((0,0,1))).normalized();up=axis.cross(side).normalized()
            radius=2.1 if i<7 else 1.8
            ring=[side*math.cos(j*math.pi/4)*radius+up*math.sin(j*math.pi/4)*radius for j in range(8)]
            rings([[p+d for d in ring] for p in (bottom,top)])
        changes=['Replaced the continuous wedge with fifteen separate leaning timber poles and visible cut ends.',
                 'Seven front poles follow the source bundle; five rear and three inner poles complete the inferred compact pile.']
        measurements={'source_bundle_center_x':1833,'source_ground_center_y':140,'base_radius_world':16,
                      'source_cut_end_cluster_y':[107,113],'source_footprint_y':[130,150],
                      'front_visible_long_poles':7,'hidden_rear_poles':5,'hidden_inner_poles':3,'pole_diameter_world':[3.6,4.2],
                      'source_evidence':'Seven distinguishable long front timber strips and clustered pale cut ends in the enlarged native crop.'}
        inference=['Five rear and three inner poles continue the compact pile behind the visible front fan.','Pole thickness, radial section and concealed contact are estimated from the source silhouette.']
    else:raise ValueError('Unsupported forest form '+node)
    mesh=bpy.data.meshes.new(obj.name+' / forest silhouette')
    inverse=obj.matrix_world.inverted();mesh.from_pydata([inverse@v for v in vertices],[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    uv=mesh.uv_layers.new(name='Source projection')
    for loop in mesh.loops:
        p=obj.matrix_world@mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv=(p.x/2304,1-(-p.y*sine-p.z*cosine)/3520)
    for material in obj.data.materials:mesh.materials.append(material)
    obj.data=mesh;topology=_topology(mesh)
    if topology['nonmanifold_edges'] or topology['degenerate_faces']:raise ValueError(topology)
    report={'source_node':node,'recipe':'forest-visible-form','before_geometry_sha256':before,
            'after_geometry_sha256':_hash(_geometry(obj)),'measurements':measurements,
            'changes':changes,'inference':inference,'topology':topology,'approval':'pending',
            'projection_status':'stale; requires modified source projection'}
    obj[tag]=json.dumps(report,sort_keys=True)
    return report


def refine(asset_id):
    if asset_id not in ASSETS:
        raise ValueError(f'Unsupported environment asset: {asset_id}')
    sources = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH'
               and obj.get('source_node') in ASSETS[asset_id]
               and not obj.hide_render and not obj.hide_get()]
    if {obj.get('source_node') for obj in sources} != ASSETS[asset_id]:
        raise ValueError(f'Missing or hidden environment receiver for {asset_id}')
    outside = {obj.name: (_hash(_geometry(obj)), [list(row) for row in obj.matrix_world])
               for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj not in sources}
    reports = []
    for obj in sources:
        original = _geometry(obj)
        corners = _corners(obj)
        matrix = [list(row) for row in obj.matrix_world]
        before = _topology(obj.data)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        by_position = {}
        targets = {}
        for vertex in bm.verts:
            key = tuple(vertex.co)
            if key in by_position:
                targets[vertex] = by_position[key]
            else:
                by_position[key] = vertex
        if targets:
            bmesh.ops.weld_verts(bm, targetmap=targets)
            bm.to_mesh(obj.data)
            obj.data.update()
        bm.free()
        if _corners(obj) != corners:
            raise ValueError(f'Face-corner position, UV or material drift: {obj.name}')
        if [list(row) for row in obj.matrix_world] != matrix:
            raise ValueError(f'Transform drift: {obj.name}')
        after = _topology(obj.data)
        if after['degenerate_faces'] > before['degenerate_faces']:
            raise ValueError(f'New degenerate receiver: {obj.name}')
        reports.append({'object': obj.name, 'source_node': obj['source_node'],
                        'before': before, 'after': after, 'welded_exact_vertices': len(targets),
                        'before_geometry_sha256': _hash(original),
                        'after_geometry_sha256': _hash(_geometry(obj)),
                        'surface_uv_material_corner_sha256': _hash(corners),
                        'surface_and_uv_preserved': True, 'transform_drift': 0})
    for name, prior in outside.items():
        obj = bpy.data.objects[name]
        if (_hash(_geometry(obj)), [list(row) for row in obj.matrix_world]) != prior:
            raise ValueError(f'Outside-object mutation: {name}')
    changed = any(report['welded_exact_vertices'] for report in reports)
    stumps = [_round_stump(obj) for obj in sources if obj['source_node'] in {'building-543','building-545'}]
    platform=_platform(sources) if asset_id=='nottingham-southwest-prison-road-props' else None
    forest=[_forest_form(obj) for obj in sources if obj['source_node'] in {'building-541','building-542','building-544'}]
    extra=None
    if asset_id in {'nottingham-castle-west-rocks','nottingham-forest-rock-outcrop'}:
        from refine_environment_rocks import refine as refine_rocks
        extra=refine_rocks(asset_id)
    elif asset_id in {'nottingham-castle-yard-mission-props','nottingham-church-road-mission-props','nottingham-castle-courtyard-ground'}:
        from refine_environment_props import refine as refine_props
        extra=refine_props(asset_id)
    return {'asset_id': asset_id, 'status': 'refined-source-form' if forest or extra else ('refined-platform-frame' if platform else ('refined-round-stumps' if stumps else ('refined-connectivity' if changed else 'audited-unchanged'))), 'objects': reports,
            'forest_refinements':forest,'asset_refinement':extra,
            'platform_refinement':platform,
            'stump_refinements':stumps,
            'outside_objects_unchanged': True, 'projection_status': 'stale; rerun modified packet',
            'geometry_approval': 'pending', 'texture_generation': 'not started',
            'limitations': ['Source-visible forest, rock or prop form refined; concealed inferences and retained receivers are recorded in asset-specific reports.' if forest or extra else ('Measured platform frame and stair details include conservative concealed supports.' if platform else ('Two cut stumps are rounded from visible contours; other receiver silhouettes are unchanged.' if stumps else 'Only exact coincident receiver vertices are joined; silhouette is unchanged.')),
                            'Hidden structure inferences are recorded per recipe; unaffected receivers retain their open or clipped backs.',
                            'Foliage and architectural foreground pixels need native mask and receiver ownership validation.',
                            'Ground and courtyard remain source-supported surfaces; their unseen undersides are unspecified.']}


if __name__ == '__main__':
    import argparse
    import sys
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset', required=True, choices=sorted(ASSETS))
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--save', action='store_true', help='Save an isolated model.blend worker')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.save and (Path(bpy.data.filepath).name != 'model.blend'
                      or 'baseline' in Path(bpy.data.filepath).parts):
        raise ValueError('Save is restricted to an isolated model.blend worker')
    result = refine(args.asset)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2)+'\n')
    if args.save:
        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    print(json.dumps(result))
