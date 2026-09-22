"""Replace audited castle spire collision columns with closed render shells.

Use inside a grouped worker scene, then regenerate its modified packet. Visible
roof cap positions and their UVs stay exact; concealed thickness is an explicit
two-unit inference and receives a neutral material until projection.
"""
import argparse
import hashlib
import json
import math
import runpy
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

TAG = 'nottingham-castle-spire-shell-v1'
ROOFS = (377, 494, 495, 498,
         514, 515, 517, 518, 519, 520, 521, 522, 523, 524)
STAIRS = {361: 10, 363: 5, 487: 16}
SPIRES = {494:(495,None,151,443), 514:(515,509,490,477),
          517:(518,516,727,409), 520:(521,519,269,284),
          523:(524,522,508,181)}


def fingerprint(obj):
    data = {'vertices': [list(v.co) for v in obj.data.vertices],
            'faces': [list(p.vertices) for p in obj.data.polygons],
            'matrix': [list(row) for row in obj.matrix_world],
            'uv': {u.name: [list(v.uv) for v in u.data] for u in obj.data.uv_layers}}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def shell(obj):
    if obj.get('castle_refinement') == TAG:
        return {'object': obj.name, 'source_node': obj['source_node'], 'status': 'already-refined'}
    before = fingerprint(obj)
    old = obj.data
    world = obj.matrix_world.copy()
    # Wall triangles have vertical world normals. Roof cap triangles are the
    # only upward-facing triangles in each audited source component.
    normal_matrix = world.to_3x3().inverted().transposed()
    caps = [p for p in old.polygons if (normal_matrix @ p.normal).normalized().z > .05]
    if not caps:
        raise ValueError(f'No upward roof surface: {obj.name}')
    indices = sorted({v for p in caps for v in p.vertices})
    remap = {v: i for i, v in enumerate(indices)}
    top = [old.vertices[i].co.copy() for i in indices]
    drop = world.inverted().to_3x3() @ Vector((0, 0, 2))
    vertices = top + [p-drop for p in top]
    count = len(top)
    faces = [tuple(remap[v] for v in p.vertices) for p in caps]
    roof_count = len(faces)
    faces.extend(tuple(v+count for v in reversed(p)) for p in list(faces))
    edges = {}
    for face in faces[:roof_count]:
        for a, b in zip(face, face[1:]+face[:1]):
            key = tuple(sorted((a, b)))
            edges.setdefault(key, []).append((a, b))
    boundary = [values[0] for values in edges.values() if len(values) == 1]
    if any(len(values) > 2 for values in edges.values()):
        raise ValueError('Nonmanifold roof cap')
    faces.extend((a, a+count, b+count, b) for a, b in boundary)
    mesh = bpy.data.meshes.new(old.name+' / roof shell')
    mesh.from_pydata(vertices, [], faces)
    for mat in old.materials:
        mesh.materials.append(mat)
    neutral = bpy.data.materials.get('Nottingham / unknown roof thickness')
    if neutral is None:
        neutral = bpy.data.materials.new('Nottingham / unknown roof thickness')
        neutral.diffuse_color = (.32, .32, .32, 1)
    mesh.materials.append(neutral)
    for polygon in mesh.polygons:
        polygon.material_index = caps[polygon.index].material_index if polygon.index < roof_count else len(mesh.materials)-1
    for channel in old.uv_layers:
        layer = mesh.uv_layers.new(name=channel.name)
        for value in layer.data:
            value.uv = (.5, .5)
        for dst, src in zip(mesh.polygons[:roof_count], caps):
            for a, b in zip(dst.loop_indices, src.loop_indices):
                layer.data[a].uv = channel.data[b].uv
        layer.active_render = channel.active_render
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    nonmanifold = sum(not e.is_manifold for e in bm.edges)
    degenerate = sum(f.calc_area() < 1e-8 for f in bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    if nonmanifold or degenerate:
        raise ValueError(f'Invalid shell: {nonmanifold} boundary edges, {degenerate} degenerate faces')
    old_min = min((world @ v.co).z for v in old.vertices)
    obj.data = mesh
    obj['castle_refinement'] = TAG
    obj['roof_shell_thickness'] = 2.0
    obj['inferred_surface_note'] = 'Two-unit concealed thickness; visible cap positions retained exactly.'
    return {'object': obj.name, 'source_node': obj['source_node'],
            'before_sha256': before, 'after_sha256': fingerprint(obj),
            'vertices_before': len(old.vertices), 'vertices_after': len(mesh.vertices),
            'faces_before': len(old.polygons), 'faces_after': len(mesh.polygons),
            'roof_triangles': roof_count, 'nonmanifold_edges': nonmanifold,
            'degenerate_faces': degenerate, 'world_transform_drift': 0,
            'minimum_height_before': old_min,
            'minimum_height_after': min((world @ v.co).z for v in mesh.vertices),
            'source_cap_position_drift': 0, 'source_cap_uv_drift': 0}


def stairs(obj, count):
    tag = 'nottingham-castle-measured-stairs-v1'
    if obj.get('castle_refinement') == tag:
        return {'object': obj.name, 'source_node': obj['source_node'], 'status': 'already-refined'}
    old = obj.data
    world = obj.matrix_world.copy()
    normal_matrix = world.to_3x3().inverted().transposed()
    caps = [p for p in old.polygons if (normal_matrix @ p.normal).normalized().z > .05]
    ids = sorted({v for p in caps for v in p.vertices})
    if len(ids) != 4:
        raise ValueError('Measured stair ramp must have four roof corners')
    points = sorted((world @ old.vertices[i].co for i in ids), key=lambda p: p.z)
    low, high = sorted(points[:2], key=lambda p: p.x), points[2:]
    if sum((a-b).length_squared for a,b in zip(low,high)) > sum((a-b).length_squared for a,b in zip(low,reversed(high))):
        high.reverse()
    base = min((world @ v.co).z for v in old.vertices)
    lower, upper = sum(p.z for p in low)/2, sum(p.z for p in high)/2
    profile = [(0, base), (0, lower)]
    for i in range(count):
        z = lower+(upper-lower)*(i+1)/count
        profile.extend([(i/count, z), ((i+1)/count, z)])
    profile.append((1, base))
    vertices = []
    inverse = world.inverted()
    for a,b in zip(low,high):
        for t,z in profile:
            p = a.lerp(b,t)
            p.z = z
            vertices.append(inverse @ p)
    size = len(profile)
    faces = [tuple(range(size)), tuple(range(size,2*size))]
    faces.extend((i,(i+1)%size,(i+1)%size+size,i+size) for i in range(size))
    mesh = bpy.data.meshes.new(old.name+' / measured stairs')
    mesh.from_pydata(vertices,[],faces)
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    invalid = sum(not e.is_manifold for e in bm.edges)
    degenerate = sum(f.calc_area()<1e-8 for f in bm.faces)
    bm.to_mesh(mesh); bm.free()
    if invalid or degenerate:
        raise ValueError('Invalid measured stair topology')
    neutral = bpy.data.materials.get('Nottingham / unknown roof thickness')
    if neutral is None:
        neutral = bpy.data.materials.new('Nottingham / unknown roof thickness')
        neutral.diffuse_color=(.32,.32,.32,1)
    mesh.materials.append(neutral)
    uv = mesh.uv_layers.new(name='UVMap')
    for value in uv.data: value.uv=(.5,.5)
    before=fingerprint(obj)
    obj.data=mesh
    obj['castle_refinement']=tag
    obj['step_count']=count
    return {'object':obj.name,'source_node':obj['source_node'],'steps':count,
            'before_sha256':before,'after_sha256':fingerprint(obj),
            'vertices_before':len(old.vertices),'vertices_after':len(mesh.vertices),
            'faces_before':len(old.polygons),'faces_after':len(mesh.polygons),
            'nonmanifold_edges':invalid,'degenerate_faces':degenerate,
            'world_transform_drift':0,'evidence':'castle-audit/stair-'+obj['source_node'][-3:]+'-zoom.png'}


def conical_spires(targets):
    """A painted spire has one apex, not a ridge stretched across its drum."""
    root=Path(__file__).resolve().parents[3]
    native=json.loads((root/'datadirs/fullgame_gog_hackable/Data/Levels/nottingham.rhp.json').read_text())['sight_obstacles']
    by_node={int(o['source_node'][9:]):o for o in targets}
    output=[]
    for first,(second,drum,apex_x,apex_y) in SPIRES.items():
        if first not in by_node: continue
        if second not in by_node: raise ValueError('Incomplete paired spire ownership')
        if drum is None:
            # Round western spire eaves measured from its two visible slopes.
            ring=[(155+52*math.cos(i*2*math.pi/32),1258+18*math.sin(i*2*math.pi/32),590) for i in range(32)]
        else:
            ring=[(p['x'],p['y'],p['z_top']) for p in native[drum]['points']]
        cy=sum(p[1] for p in ring)/len(ring)
        peak=(apex_x,cy,cy-apex_y)
        sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
        def world(p): return Vector((p[0],-p[1]/sine,p[2]/cosine))
        surface=[[ring[i],ring[(i+1)%len(ring)],peak] for i in range(len(ring))]
        surface.append(list(reversed(ring)))
        for side,number in enumerate((first,second)):
            obj=by_node[number]
            if obj.get('castle_refinement')=='nottingham-castle-single-apex-v2':
                output.append({'source_node':obj['source_node'],'status':'already-refined'});continue
            before=fingerprint(obj); old=obj.data
            faces=[]; points=[]; cut=[]
            for face in surface:
                clipped=[]
                for a,b in zip(face,face[1:]+face[:1]):
                    da=(a[0]-apex_x)*(1 if side==0 else -1)
                    db=(b[0]-apex_x)*(1 if side==0 else -1)
                    if da<=1e-7:clipped.append(a)
                    if da*db < -1e-8:
                        t=da/(da-db);p=tuple(x+(y-x)*t for x,y in zip(a,b));clipped.append(p);cut.append(p)
                if len(clipped)>=3:
                    start=len(points);points.extend(clipped);faces.append(tuple(range(start,len(points))))
            cut.extend([peak])
            unique={tuple(round(x,5) for x in p):p for p in cut}
            center=tuple(sum(p[i] for p in unique.values())/len(unique) for i in range(3))
            cap=sorted(unique.values(),key=lambda p:math.atan2(p[2]-center[2],p[1]-center[1]))
            start=len(points);points.extend(cap);faces.append(tuple(range(start,len(points))))
            mesh=bpy.data.meshes.new(obj.name+' / single-apex spire')
            inverse=obj.matrix_world.inverted()
            mesh.from_pydata([inverse@world(p) for p in points],[],faces)
            bm=bmesh.new();bm.from_mesh(mesh)
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0002)
            bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.00001)
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
            invalid=sum(not e.is_manifold for e in bm.edges)
            degenerate=sum(f.calc_area()<1e-8 for f in bm.faces)
            bm.to_mesh(mesh);bm.free()
            if invalid or degenerate:raise ValueError(f'Spire{number}: {invalid} open edges {degenerate} degenerate faces')
            neutral=bpy.data.materials.get('Nottingham / unknown roof thickness')
            if neutral is None:
                neutral=bpy.data.materials.new('Nottingham / unknown roof thickness');neutral.diffuse_color=(.32,.32,.32,1)
            mesh.materials.append(neutral);mesh.uv_layers.new(name='UVMap')
            obj.data=mesh;obj['castle_refinement']='nottingham-castle-single-apex-v2'
            obj['apex_source_pixel']=[apex_x,apex_y]
            output.append({'source_node':obj['source_node'],'before_sha256':before,'after_sha256':fingerprint(obj),
                           'vertices_before':len(old.vertices),'vertices_after':len(mesh.vertices),
                           'faces_before':len(old.polygons),'faces_after':len(mesh.polygons),
                           'nonmanifold_edges':invalid,'degenerate_faces':degenerate,'world_transform_drift':0,
                           'source_apex':[apex_x,apex_y],'eave_source_node':f'building-{drum:03}' if drum else None,
                           'inference':'Concealed radial surfaces join the measured eave boundary and single painted apex.'})
    return output


def supported_roof(obj, bottom):
    """A roof without a separate wall receiver keeps its measured gable volume."""
    tag='nottingham-castle-supported-roof-v2'
    if obj.get('castle_refinement')==tag:return {'source_node':obj['source_node'],'status':'already-refined'}
    root=Path(__file__).resolve().parents[3]
    native=json.loads((root/'datadirs/fullgame_gog_hackable/Data/Levels/nottingham.rhp.json').read_text())['sight_obstacles']
    data=native[int(obj['source_node'][9:])]['points']
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    inverse=obj.matrix_world.inverted()
    vertices=[inverse@Vector((p['x'],-p['y']/sine,z/cosine)) for zkey in ('top','bottom') for p in data for z in [p['z_top'] if zkey=='top' else bottom]]
    n=len(data)
    faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    mesh=bpy.data.meshes.new(obj.name+' / roof and supporting walls');mesh.from_pydata(vertices,[],faces)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    invalid=sum(not e.is_manifold for e in bm.edges);degenerate=sum(f.calc_area()<1e-8 for f in bm.faces)
    bm.to_mesh(mesh);bm.free()
    if invalid or degenerate:raise ValueError('Invalid supported roof')
    mat=bpy.data.materials.get('Nottingham / unknown roof thickness')
    if mat is None:mat=bpy.data.materials.new('Nottingham / unknown roof thickness');mat.diffuse_color=(.32,.32,.32,1)
    mesh.materials.append(mat);mesh.uv_layers.new(name='UVMap')
    before=fingerprint(obj);old=obj.data;obj.data=mesh;obj['castle_refinement']=tag
    return {'source_node':obj['source_node'],'before_sha256':before,'after_sha256':fingerprint(obj),
            'vertices_before':len(old.vertices),'vertices_after':len(mesh.vertices),
            'faces_before':len(old.polygons),'faces_after':len(mesh.polygons),
            'nonmanifold_edges':invalid,'degenerate_faces':degenerate,'world_transform_drift':0,
            'native_support_height':bottom,'inference':'Concealed walls join measured roof outline to adjacent terrace height.'}


def hall_components():
    """Separate the measured retained roof frame, covers and room floor."""
    working=bpy.data.collections['nottingham Working']
    sources={int(o['source_node'][9:]):o for o in working.all_objects
             if o.type=='MESH' and o.get('asset_group')=='nottingham-castle-main-hall'
             and not o.get('castle_hall_generated')}
    if not {501,504,505,506,507,530,531,532,533,534,535}<=set(sources):
        raise ValueError('Main hall source ownership incomplete')
    generated=[o for o in working.all_objects if o.get('castle_hall_generated')]
    if generated:
        return {'status':'already-refined','components':[o.name for o in generated]}
    from freeze_tooling import select_tooling
    tooling=select_tooling()
    helpers=runpy.run_path(str(Path(tooling['directory'])/'derby_east_hall.py'))
    split,subtract=helpers['_split'],helpers['_subtract']
    sine,cosine=math.sin(math.radians(35)),math.cos(math.radians(35))
    # Traced cutaway boundary, measured on the exact revealed source pixels.
    opening=[(324,574),(481,466),(548,503),(714,646),(699,834),(573,891),(444,815),(324,705)]
    outline=[Vector((x,y,0)) for x,y in opening]
    triangles=tessellate_polygon([outline])
    triangles=[[outline[v] if isinstance(v,int) else v for v in triangle] for triangle in triangles]
    cutters=[]
    for triangle in triangles:
        center=sum(triangle,Vector())/3;planes=[]
        for a,b in zip(triangle,triangle[1:]+triangle[:1]):
            n=Vector((b.y-a.y,a.x-b.x)); offset=n.x*a.x+n.y*a.y
            if n.x*center.x+n.y*center.y>offset:n.negate();offset=-offset
            planes.append((Vector((n.x,-n.y*sine,-n.y*cosine)),offset))
        cutters.append(planes)
    reports=[]
    def component(primary,name,polygons,thin=False):
        objname=primary['source_node']+'__'+name
        points=[];faces=[]
        for polygon in polygons:
            clean=[]
            for p in polygon:
                if not clean or (p-clean[-1]).length>1e-5:clean.append(p)
            if len(clean)>2 and (clean[0]-clean[-1]).length<1e-5:clean.pop()
            if len(clean)<3:continue
            start=len(points);points.extend(clean);faces.append(tuple(range(start,len(points))))
        mesh=bpy.data.meshes.new(objname)
        inverse=primary.matrix_world.inverted();mesh.from_pydata([inverse@p for p in points],[],faces)
        bm=bmesh.new();bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0002)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.00001)
        if thin:
            points=list(bm.verts)
            for edge in list(bm.edges):
                a,b=edge.verts;delta=b.co-a.co
                if delta.length_squared<1e-10:continue
                fractions=[]
                for vertex in points:
                    if vertex in (a,b):continue
                    t=(vertex.co-a.co).dot(delta)/delta.length_squared
                    if .00001<t<.99999 and (a.co+t*delta-vertex.co).length<.001:
                        fractions.append(t)
                previous,current=0.,a
                for fraction in sorted(set(round(t,8) for t in fractions)):
                    _,inserted=bmesh.utils.edge_split(edge,current,(fraction-previous)/(1-previous))
                    previous,current=fraction,inserted
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001)
            # Co-planar clipped triangles join before a physical underside is added.
            bmesh.ops.dissolve_limit(bm,angle_limit=.003,verts=list(bm.verts),edges=list(bm.edges),use_dissolve_boundaries=False)
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
            bmesh.ops.solidify(bm,geom=list(bm.faces),thickness=2)
        loose=[edge for edge in bm.edges if not edge.link_faces]
        if loose:bmesh.ops.delete(bm,geom=loose,context='EDGES')
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-7 for f in bm.faces)
        bm.to_mesh(mesh);bm.free()
        mat=bpy.data.materials.get('Nottingham / unknown roof thickness')
        if mat is None:mat=bpy.data.materials.new('Nottingham / unknown roof thickness');mat.diffuse_color=(.32,.32,.32,1)
        mesh.materials.append(mat);mesh.uv_layers.new(name='UVMap')
        obj=bpy.data.objects.new(objname,mesh);working.objects.link(obj)
        obj.parent=primary.parent;obj.matrix_parent_inverse=primary.matrix_parent_inverse.copy();obj.matrix_world=primary.matrix_world.copy()
        for key in primary.keys():obj[key]=primary[key]
        obj['castle_hall_generated']=True;obj['projection_component']=name
        obj['reveal_component_patch_id']='patch-008'
        obj['reveal_component_role']='removable-cover' if name.endswith('cover') else 'retained-shell'
        if obj['reveal_component_role']=='removable-cover':obj['reveal_state']='covered'
        obj['castle_refinement']='nottingham-castle-hall-cutaway-v1'
        reports.append({'object':obj.name,'source_node':obj['source_node'],'component':name,
                        'vertices':len(mesh.vertices),'faces':len(mesh.polygons),
                        'nonmanifold_edges':bad,'degenerate_faces':deg,'world_transform_drift':0})
        if bad or deg:raise ValueError(f'Invalid hall component {objname}: {bad} open edges, {deg} degenerate faces')
        return obj
    def native_volume(primary,bottom,top=None):
        root=Path(__file__).resolve().parents[3]
        native=json.loads((root/'datadirs/fullgame_gog_hackable/Data/Levels/nottingham.rhp.json').read_text())['sight_obstacles']
        data=native[int(primary['source_node'][9:])]['points'];n=len(data)
        points=[Vector((p['x'],-p['y']/sine,(p['z_top'] if top is None else top)/cosine)) for p in data]
        points.extend(Vector((p['x'],-p['y']/sine,bottom/cosine)) for p in data)
        indices=[tuple(range(n)),tuple(reversed(range(n,2*n)))]
        indices.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
        return [[points[i] for i in face] for face in indices]
    for number in (505,506):
        primary=sources[number];normal=primary.matrix_world.to_3x3().inverted().transposed()
        caps=[[(primary.matrix_world@primary.data.vertices[i].co,Vector((0,0))) for i in p.vertices]
              for p in primary.data.polygons if (normal@p.normal).normalized().z>.05]
        retained=list(caps);removed=[]
        for planes in cutters:
            next_retained=[]
            for polygon in retained:
                inside=list(polygon)
                for plane,offset in planes:inside,_=split(inside,plane,offset)
                if len(inside)>=3:removed.append(inside)
                next_retained.extend(subtract(polygon,planes))
            retained=next_retained
        component(primary,'castle-hall-retained-roof',[[p for p,uv in polygon] for polygon in retained],True)
        component(primary,'castle-hall-removable-cover',[[p for p,uv in polygon] for polygon in removed],True)
        primary.hide_render=True;primary.hide_set(True)
    primary=sources[507]
    normal=primary.matrix_world.to_3x3().inverted().transposed()
    caps=[[primary.matrix_world@primary.data.vertices[i].co for i in p.vertices]
          for p in primary.data.polygons if (normal@p.normal).normalized().z>.05]
    component(primary,'castle-hall-removable-cover',caps,True)
    primary.hide_render=True;primary.hide_set(True)
    for number in (527,528):
        primary=sources[number]
        component(primary,'castle-hall-removable-cover',native_volume(primary,588))
        primary.hide_render=True;primary.hide_set(True)
    primary=sources[530]
    component(primary,'castle-hall-ceiling-cover',native_volume(primary,588,590))
    primary.hide_render=True;primary.hide_set(True)
    primary=sources[501]
    component(primary,'castle-hall-floor-support',native_volume(primary,0,418))
    floor=component(primary,'castle-hall-floor',native_volume(primary,418,420.001))
    floor['reveal_component_role']='interior-receiver'
    floor['reveal_state']='revealed'
    floor['source_floor_anchor']='Native501 is the measured room floor at420.001; ceiling530 is a separate cover near590.'
    primary.hide_render=True;primary.hide_set(True)
    for number in (502,531,532):
        primary=sources[number]
        component(primary,'castle-hall-retained-wall',native_volume(primary,0,420))
        component(primary,'castle-hall-removable-cover',native_volume(primary,420))
        primary.hide_render=True;primary.hide_set(True)
    return {'recipe':'nottingham-castle-hall-cutaway-v1','components':reports,
            'opening_source_pixels':opening,'floor_native_height':420,
            'limitations':['Floor outline inherits the upper ceiling footprint; exact wall-contact shaping requires revealed-camera review.',
                           'Hall chandelier, fireplace arch and furniture profiles remain coarse source reconstruction.',
                           'Partial wall504 visibility must be verified in the revealed state before approval.']}


def refine(asset_id=None):
    bpy.context.view_layer.update()
    working = bpy.data.collections['nottingham Working']
    if asset_id=='nottingham-castle-main-hall':return hall_components()
    targets = [o for o in working.all_objects if o.type == 'MESH'
               and o.get('source_node') in {f'building-{n:03}' for n in (*ROOFS,*STAIRS)}
               and (asset_id is None or o.get('asset_group') == asset_id)]
    if not targets:
        raise ValueError(f'No audited castle roofs in {asset_id}')
    outside = {o.name: fingerprint(o) for o in working.all_objects
               if o.type == 'MESH' and o not in targets}
    spire_nodes=set(SPIRES)|{p[0] for p in SPIRES.values()}
    changes=[]
    for obj in targets:
        number=int(obj['source_node'][9:])
        if number in spire_nodes:continue
        if number in STAIRS:changes.append(stairs(obj,STAIRS[number]))
        elif number in (377,498,519,522):changes.append(supported_roof(obj,{377:100,498:350,519:480,522:590}[number]))
        else:changes.append(shell(obj))
    changes.extend(conical_spires(targets))
    if asset_id=='nottingham-castle-southwest-spire':
        for obj in working.all_objects:
            if obj.type=='MESH' and obj.get('asset_group')==asset_id:
                obj['reveal_state']='covered'
                obj['reveal_patch_id']='patch-008'
                obj['reveal_component_patch_id']='patch-008'
                obj['reveal_component_role']='removable-cover'
                obj['projection_component']='castle-hall-southwest-spire-cover'
    drift = [name for name, digest in outside.items() if fingerprint(bpy.data.objects[name]) != digest]
    if drift:
        raise ValueError(f'Outside geometry changed: {drift}')
    return {'recipe': TAG, 'changes': changes, 'outside_objects_checked': len(outside),
            'outside_object_changes': drift, 'approval': 'not-requested',
            'texture_generation': 'not-started',
            'limitations': ['Spire profiles retain the measured planar facets; curved profiles require further anchors.',
                            'Concealed underside thickness is inferred and must remain neutral.',
                            'Hall roof and interiors require independent covered/revealed receiver refinement.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--asset')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    report = refine(args.asset)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
    report['model_sha256'] = hashlib.sha256((out/'model.blend').read_bytes()).hexdigest()
    (out/'geometry-report.json').write_text(json.dumps(report, indent=2)+'\n')
