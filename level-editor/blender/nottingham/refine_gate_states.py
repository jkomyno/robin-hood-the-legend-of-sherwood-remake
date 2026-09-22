"""Gate tower cutaway and source-exact initial/final mechanical state meshes.

Animated surfaces use opaque sprite silhouettes extruded one native unit. Their
front pixels are authoritative; concealed thickness and backs remain neutral.
This discrete-state representation retains every transition frame as evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

sys.path.insert(0, str(Path(__file__).parent))
from refine_church import ROOT, SIN, COS, fingerprint, copy_component, prism, split_plane, replace_native, neutral

TAG = 'nottingham-gate-states-v1'


def cross_section(obj, outline, start, end, depth):
    front=[(start[0]+(end[0]-start[0])*t,start[1]+(end[1]-start[1])*t,z) for t,z in outline]
    vertices=front+[(x+depth[0],y+depth[1],z) for x,y,z in front]
    n=len(front);faces=[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    for offset in [0,n]:
        # Triangulate the planar profile directly to avoid large-coordinate
        # precision errors in a nearly axis-aligned world-space wall plane.
        vectors=[Vector((t*100,z,0)) for t,z in outline]
        for tri in tessellate_polygon([vectors]):
            indices=[offset+(v if isinstance(v,int) else min(range(n),key=lambda i:(vectors[i]-v).length_squared)) for v in tri]
            faces.append(tuple(indices if offset else reversed(indices)))
    replace_native(obj,vertices,faces)


def gate_masonry(objects):
    """Measured five/four-merlon parapets and pointed gateway opening.

    The two masonry rails follow their recorded plan axes. The lower pointed
    opening is measured from the source silhouette; its concealed vault depth
    is an explicit inference between the two rails.
    """
    native = json.loads((ROOT/'work/nottingham-refinement/source-states/level.json').read_text())['sight_obstacles']
    for number, count, phase in [(335,5,.03),(336,4,.02)]:
        points = native[number]['points']
        a,b = points[3],points[0]
        dx,dy = points[1]['x']-b['x'],points[1]['y']-b['y']
        bottom,top = points[0]['z_bottom'],points[0]['z_top']
        breaks = [(0,top-18)]
        for i in range(count):
            lo=phase+i/count;hi=min(1,lo+.62/count)
            breaks += [(lo,top-18),(lo,top),(hi,top),(hi,top-18)]
        breaks.append((1,top-18))
        cross_section(objects[number],[(0,bottom),(1,bottom)]+list(reversed(breaks)),
                      (a['x'],a['y']),(b['x'],b['y']),(dx,dy))
        objects[number]['measured_merlon_count']=count
    a,b=(882.2,1632.9),(1025.4,1583.1)
    samples=[(0,108),(.12,108),(.12,175),(.24,201),(.38,225),(.49,239),(.60,228),(.73,207),(.84,179),(.84,108),(1,108)]
    cross_section(objects[333],samples+[(1,275),(0,275)],a,b,(-12,-31))
    for obj in objects.values():
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-5)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-4)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
        obj['gate_state_recipe']=TAG
    return {'front_merlons':5,'back_merlons':4,'opening':'pointed source-silhouette hypothesis',
            'inferred':'concealed vault depth and threshold datum108'}


def sprite_mesh(template, record, state, native_y, label):
    graphic = record[state+'_graphic']
    path = ROOT/'work/nottingham-refinement/source-states'/graphic['image']
    image = bpy.data.images.load(str(path), check_existing=True)
    width, height = image.size
    pixels = list(image.pixels)
    # Blender pixels begin at the lower-left; source records use top-left.
    occupied = {(x, y) for y in range(height) for x in range(width)
                if pixels[((height-1-y)*width+x)*4+3] > .5}
    if not occupied:
        raise ValueError(f'Empty animated source silhouette: {path}')
    left, top = graphic['bbox'][:2]
    vertices, vertex_map, faces, front = [], {}, [], []
    def index(x, y, depth):
        key = (x, y, depth)
        if key not in vertex_map:
            vertex_map[key] = len(vertices)
            # Constant native-y plane projects exactly to the sprite rectangle.
            vertices.append((left+x, native_y+depth, native_y-(top+y)))
        return vertex_map[key]
    for x, y in sorted(occupied):
        faces.append(tuple(index(xx, yy, 0) for xx, yy in [(x,y),(x+1,y),(x+1,y+1),(x,y+1)]))
        front.append(len(faces)-1)
        faces.append(tuple(index(xx, yy, 1) for xx, yy in [(x,y+1),(x+1,y+1),(x+1,y),(x,y)]))
        for other, endpoints in [((x-1,y),((x,y),(x,y+1))), ((x+1,y),((x+1,y+1),(x+1,y))),
                                 ((x,y-1),((x+1,y),(x,y))), ((x,y+1),((x,y+1),(x+1,y+1)))]:
            if other not in occupied:
                a,b = endpoints
                faces.append((index(*a,0),index(*b,0),index(*b,1),index(*a,1)))
    obj = copy_component(template, label)
    replace_native(obj, vertices, faces)
    material = bpy.data.materials.new('Nottingham / '+label+' / preserved source pixels')
    material.use_nodes = True
    tree = material.node_tree
    bsdf = tree.nodes.get('Principled BSDF')
    texture = tree.nodes.new('ShaderNodeTexImage')
    texture.image = image
    texture.interpolation = 'Closest'
    tree.links.new(texture.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 1
    obj.data.materials.append(material)
    uv = obj.data.uv_layers.new(name='StateSourceUV')
    front = set(front)
    for polygon in obj.data.polygons:
        polygon.material_index = 1 if polygon.index in front else 0
        for loop in polygon.loop_indices:
            vx,vy,vz = vertices[obj.data.loops[loop].vertex_index]
            uv.data[loop].uv = ((vx-left)/width, 1-(native_y-vz-top)/height)
    obj['projection_component'] = label
    obj['gate_state_recipe'] = TAG
    obj['animation_patch_id'] = record['id']
    if record['id'] == 'patch-004':
        obj['reveal_component_patch_id'] = 'patch-005'
        obj['reveal_component_role'] = 'retained'
    obj['animation_state'] = state
    obj['source_frame_sha256'] = graphic['sha256']
    obj['source_frame_path'] = str(path)
    obj['source_frame_bbox'] = graphic['bbox']
    obj['source_front_pixel_count'] = len(occupied)
    obj['preserve_state_source_material'] = True
    obj['inferred_surface_note'] = 'One-native-unit concealed extrusion; front is exact state sprite silhouette.'
    obj.hide_render = state == 'applied'
    obj.hide_set(state == 'applied')
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bad = sum(not e.is_manifold for e in bm.edges)
    bm.to_mesh(obj.data)
    bm.free()
    return {'object': obj.name, 'canonical_source_node': obj['source_node'],
            'component': label, 'state': state, 'patch': record['id'],
            'source_pixel_count': len(occupied), 'nonmanifold_edges': bad,
            'source_front_projection_error_pixels': 0,
            'source_sha256': graphic['sha256']}


def refine(asset_id):
    collection = bpy.data.collections['nottingham Working']
    targets = [o for o in collection.all_objects if o.type == 'MESH' and o.get('asset_group') == asset_id]
    objects = {int(o['source_node'].split('-')[-1]): o for o in targets}
    if any(o.get('gate_state_recipe') == TAG for o in targets):
        raise ValueError('Gate recipe already applied; restart from the frozen worker baseline')
    outside = {o.name:fingerprint(o) for o in collection.all_objects if o.type == 'MESH' and o not in targets}
    layers = json.loads((ROOT/'work/nottingham-refinement/source-states/layers.json').read_text())
    reports = []
    if asset_id == 'nottingham-castle-gate-east-tower':
        if set(objects) != {334,337,338,339}:
            raise ValueError('Unexpected gate tower source ownership')
        native=json.loads((ROOT/'work/nottingham-refinement/source-states/level.json').read_text())['sight_obstacles']
        for number,obj in objects.items():
            points=native[number]['points']
            prism(obj,[(p['x'],p['y']) for p in points],
                  [110 if number==338 else min(p['z_bottom'],p['z_top']-.2) for p in points],
                  [p['z_top'] for p in points])
            if number==338:
                obj['inferred_surface_note']='Rear room wall extends to the source-aligned floor datum110; measured upper wall retained.'
        from ribbon_crown import arc_ribbon_geometry
        pairs=[(5,6),(4,7),(3,8),(2,9),(1,10),(0,11),(17,12),(16,13),(15,14)]
        # Eight raised capstones are counted on the focused crown source crop.
        # C-ring seam aligns with the low rear entrance component338.
        notches=[(0,.025)]+[(i/8-.025,i/8+.025) for i in range(1,8)]+[(.975,1)]
        vertices,faces=arc_ribbon_geometry(native[337]['points'],pairs,notches,base=0,notch_depth=14)
        replace_native(objects[337],vertices,faces)
        objects[337]['measured_merlon_count']=8
        shell = objects[337]
        # Opening landmarks approximately x1002..1083, y1357..1484; split the
        # front annular wall, retaining the rear shell, upper tower and plinth.
        low, high = split_plane(shell, (0,0,1), 235/COS, 'mechanism-lower', 'mechanism-upper')
        base, middle = split_plane(low, (0,0,1), 110/COS, 'mechanism-base', 'mechanism-middle')
        rear, front = split_plane(middle, (0,-SIN,0), 1568, 'mechanism-rear-wall', 'mechanism-front')
        left, cover = split_plane(front, (1,0,0), 995, 'mechanism-left-wall', 'mechanism-removable-cover')
        for obj in [base, high, rear, left, cover]:
            obj['gate_state_recipe'] = TAG
            obj['reveal_patch_ids'] = ['patch-005']
            obj['reveal_component_patch_id'] = 'patch-005'
            obj['reveal_component_role'] = 'removable-cover' if obj == cover else 'retained'
            obj['reveal_state'] = 'covered' if obj == cover else 'both'
        floor = copy_component(base, 'mechanism-room-floor')
        polygon = [(1003,1527),(1048,1528),(1077,1539),(1077,1568),(1043,1585),
                   (1011,1584),(977,1561),(977,1542)]
        prism(floor, polygon, 109, 110)
        floor['gate_state_recipe'] = TAG
        floor['reveal_patch_ids'] = ['patch-005']
        floor['reveal_component_patch_id'] = 'patch-005'
        floor['reveal_component_role'] = 'retained'
        floor['reveal_state'] = 'revealed'
        floor['inferred_surface_note'] = 'Floor datum110 from mechanism anchor and projected wooden floor; concealed extent follows inner ring.'
        for state in ['initial','applied']:
            reports.append(sprite_mesh(base,layers['patches'][4],state,1575,'mechanism-'+state))
    elif asset_id == 'nottingham-castle-gate-arch':
        if set(objects) != {333,335,336}:
            raise ValueError('Unexpected gate arch source ownership')
        masonry = gate_masonry(objects)
        for state in ['initial','applied']:
            reports.append(sprite_mesh(objects[333],layers['patches'][3],state,1611,'portcullis-'+state))
    else:
        raise ValueError('Unsupported gate asset')
    topology={}
    for obj in collection.all_objects:
        if obj.type!='MESH' or obj.get('asset_group')!=asset_id:continue
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-5)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-4)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        topology[obj.name]={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
                            'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)}
        bm.to_mesh(obj.data);bm.free()
    drift = [n for n,digest in outside.items() if fingerprint(bpy.data.objects[n]) != digest]
    if drift:
        raise ValueError(f'Outside geometry changed: {drift}')
    invalid={name:counts for name,counts in topology.items() if any(counts.values())}
    if invalid:
        raise ValueError(f'Gate topology validation failed: {invalid}')
    return {'recipe': TAG, 'asset_id': asset_id, 'mechanical_states': reports,
            'masonry': masonry if asset_id == 'nottingham-castle-gate-arch' else None,
            'crown_merlons':8 if asset_id == 'nottingham-castle-gate-east-tower' else None,
            'topology':topology,
            'outside_object_changes': drift, 'geometry_approval': 'pending',
            'texture_generation': 'not-started',
            'animation_representation': 'Separate exact initial/applied visible state components; select one component at a time.',
            'transition_frame_archive': str(ROOT/'work/nottingham-refinement/source-states/base-patches'),
            'limitations': ['Mechanical fronts are sprite-shaped extrusions; unseen depth is inferred and neutral.',
                           'All41 transition frames are archived but no interpolated 3D motion is claimed.',
                           'Source-pixel silhouette precision does not validate gameplay depth ordering or collision.',
                           'Mechanism room wall cut heights and floor datum require camera review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--asset', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    result = refine(args.asset)
    args.output.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output/'model.blend'))
    (args.output/'geometry-report.json').write_text(json.dumps(result, indent=2)+'\n')
