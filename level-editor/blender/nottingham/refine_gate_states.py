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

sys.path.insert(0, str(Path(__file__).parent))
from refine_church import ROOT, SIN, COS, fingerprint, copy_component, prism, split_plane, replace_native, neutral

TAG = 'nottingham-gate-states-v1'


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
        for state in ['initial','applied']:
            reports.append(sprite_mesh(objects[333],layers['patches'][3],state,1611,'portcullis-'+state))
    else:
        raise ValueError('Unsupported gate asset')
    drift = [n for n,digest in outside.items() if fingerprint(bpy.data.objects[n]) != digest]
    if drift:
        raise ValueError(f'Outside geometry changed: {drift}')
    return {'recipe': TAG, 'asset_id': asset_id, 'mechanical_states': reports,
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
