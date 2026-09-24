"""Inspect saved material evidence; optionally render/export the actual stored asset.

Run in Blender background mode with --python this_file -- WORKSPACE OUTPUT.
Optional --render uses Cycles CPU and the frozen review cameras; --export writes
an isolated GLB. The candidate blend and its materials are never saved or edited.
"""
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
_legacy = str(Path(__file__).resolve().parents[2] / 'blender')
if _legacy not in sys.path:
    sys.path.append(_legacy)

import bpy
from mathutils import Matrix
from export_editor import foliage_export_meshes, finalize_foliage_glb


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect(objects):
    records, problems = [], []
    for obj in objects:
        mesh = obj.data
        record = {'object': obj.name, 'source_node': obj.get('source_node'),
                  'faces': len(mesh.polygons), 'materials': []}
        for slot in sorted({p.material_index for p in mesh.polygons}):
            faces = [p for p in mesh.polygons if p.material_index == slot]
            mat = mesh.materials[slot] if slot < len(mesh.materials) else None
            if mat is None:
                problems.append(f'{obj.name}: faces reference absent material {slot}')
                continue
            item = {'slot': slot, 'name': mat.name, 'faces': len(faces),
                    'ownership_label': mat.get('source_ownership_label'),
                    'fill': mat.get('source_ownership_fill'), 'images': [], 'uv_maps': [],
                    'nodes': [], 'links': []}
            if not mat.use_nodes:
                problems.append(f'{obj.name}: material {mat.name} has no shader nodes')
            else:
                item['nodes'] = [n.bl_idname for n in mat.node_tree.nodes]
                item['links'] = [[l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name]
                                 for l in mat.node_tree.links]
                for node in mat.node_tree.nodes:
                    if node.type == 'UVMAP':
                        layer = mesh.uv_layers.get(node.uv_map)
                        valid = layer is not None
                        coords = [tuple(layer.data[i].uv) for f in faces for i in f.loop_indices] if valid else []
                        finite = bool(coords) and all(math.isfinite(v) for uv in coords for v in uv)
                        item['uv_maps'].append({'name': node.uv_map, 'exists': valid,
                            'finite': finite, 'bounds': [[min(uv[i] for uv in coords),max(uv[i] for uv in coords)] for i in range(2)] if coords else None})
                        if not finite:
                            problems.append(f'{obj.name}: missing/nonfinite UV {node.uv_map}')
                    if node.type == 'TEX_IMAGE':
                        img = node.image
                        if img is None:
                            problems.append(f'{obj.name}: empty texture node {node.name}')
                            continue
                        pixels = array('f', [0]) * (img.size[0]*img.size[1]*4)
                        img.pixels.foreach_get(pixels)
                        item['images'].append({'name': img.name, 'size': list(img.size),
                            'packed': bool(img.packed_file), 'filepath': img.filepath,
                            'pixel_sha256': hashlib.sha256(pixels.tobytes()).hexdigest(),
                            'colorspace': img.colorspace_settings.name, 'alpha_mode': img.alpha_mode,
                            'interpolation': node.interpolation, 'extension': node.extension,
                            'finite': all(math.isfinite(v) for v in pixels)})
                        if not pixels or not all(math.isfinite(v) for v in pixels):
                            problems.append(f'{obj.name}: empty/nonfinite atlas {img.name}')
                        if not img.packed_file and not Path(bpy.path.abspath(img.filepath)).is_file():
                            problems.append(f'{obj.name}: external image unavailable {img.filepath}')
            record['materials'].append(item)
        records.append(record)
    owners, image_owners = {}, {}
    for obj in objects:
        for slot in {p.material_index for p in obj.data.polygons}:
            mat = obj.data.materials[slot] if slot < len(obj.data.materials) else None
            if mat and mat.get('source_ownership_bake'):
                owners.setdefault(mat.name, []).append(obj.name)
                nodes = mat.node_tree.nodes if mat.use_nodes else []
                textures = [n for n in nodes if n.type == 'TEX_IMAGE' and n.image]
                outputs = [n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
                valid = len(textures) == 1 and len(outputs) == 1
                if valid:
                    texture, output = textures[0], outputs[0]
                    vector = texture.inputs['Vector']
                    surface = output.inputs['Surface']
                    valid = (len(vector.links) == 1 and vector.links[0].from_node.type == 'UVMAP'
                             and bool(obj.data.uv_layers.get(vector.links[0].from_node.uv_map))
                             and len(surface.links) == 1 and surface.links[0].from_node == texture
                             and surface.links[0].from_socket.name == 'Color')
                if not valid:
                    problems.append(f'{obj.name}: owned material lacks connected named UV / atlas Color / Surface graph')
                for texture in textures:
                    image_owners.setdefault(texture.image.name, []).append(obj.name)
    for name, names in owners.items():
        if len(set(names)) > 1:
            problems.append(f'Per-object ownership atlas material is shared by multiple meshes: {name}: {sorted(set(names))}')
    for name, names in image_owners.items():
        if len(set(names)) > 1:
            problems.append(f'Per-object atlas image shared by multiple meshes: {name}: {sorted(set(names))}')
    return records, problems


def glb_report(path):
    data = Path(path).read_bytes()
    magic, version, length = struct.unpack_from('<III', data)
    if magic != 0x46546C67 or version != 2 or length != len(data):
        raise ValueError('Invalid exported GLB header')
    size, kind = struct.unpack_from('<II', data, 12)
    if kind != 0x4E4F534A:
        raise ValueError('GLB first chunk is not JSON')
    doc = json.loads(data[20:20+size])
    return {'sha256': digest(path), 'images': len(doc.get('images', [])),
            'textures': len(doc.get('textures', [])),
            'materials': [{'name': m.get('name'), 'unlit': 'KHR_materials_unlit' in m.get('extensions', {}),
                'base_color_texture': m.get('pbrMetallicRoughness', {}).get('baseColorTexture'),
                'alpha_mode': m.get('alphaMode', 'OPAQUE')} for m in doc.get('materials', [])],
            'primitives': [{'attributes': p['attributes'], 'material': p.get('material')}
                for m in doc.get('meshes', []) for p in m['primitives']]}


def run(workspace, output, *, render=False, export=False, render_object_names=None, frame_manifest=None,
        model_path=None, use_loaded=False):
    workspace, output = Path(workspace).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    config = json.loads((workspace/'workspace.json').read_text())
    model = Path(model_path).resolve(strict=True) if model_path else workspace/'model.blend'
    before = digest(model)
    if use_loaded:
        if Path(bpy.data.filepath).resolve() != model.resolve():
            raise ValueError('Loaded material audit model differs from the exact requested model')
    else:
        bpy.ops.wm.open_mainfile(filepath=str(model))
    objects = sorted([o for o in bpy.data.collections[config['collection_name']].all_objects
                      if o.type == 'MESH' and (not o.hide_render if render_object_names is None else o.name in render_object_names) and o.get('asset_group') == config['asset_id']], key=lambda o:o.name)
    if render_object_names is not None and set(render_object_names) != {o.name for o in objects}:
        raise ValueError('State names missing or foreign to asset')
    if not objects:
        raise ValueError('No visible owned meshes')
    records, problems = inspect(objects)
    output.mkdir(parents=True)
    report = {'asset_id': config['asset_id'], 'model_sha256': before, 'objects': records,
              'render_object_names': [o.name for o in objects],
              'problems': problems, 'method': 'Stored face materials and named UVs; no source ray reprojection',
              'limitations': ['Structural checks do not establish visual texture alignment.',
                 'Cycles Standard display and exported unlit materials need visual comparison; gallery unknown shading differs.']}
    scene = bpy.data.scenes.new('Stored material audit')
    bpy.context.window.scene = scene
    copies = []
    for obj in objects:
        clone = obj.copy()
        world = obj.matrix_world.copy()
        clone.parent = None
        clone.matrix_world = world
        clone.hide_render = False
        clone.hide_viewport = False
        scene.collection.objects.link(clone)
        clone.hide_set(False)
        copies.append(clone)
    bpy.context.view_layer.update()
    if export:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in copies:
            obj.select_set(True)
        with foliage_export_meshes(copies), bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            bpy.ops.export_scene.gltf(filepath=str(output/'asset.glb'), export_format='GLB', use_selection=False, use_active_scene=True, export_extras=True)
        finalize_foliage_glb(output/'asset.glb')
        report['glb'] = glb_report(output/'asset.glb')
        if not report['glb']['primitives']:
            problems.append('Export contains no mesh primitives')
        owned = {m['name'] for o in records for m in o['materials'] if m['ownership_label']}
        exported = report['glb']['materials']
        for material in exported:
            if material['name'] in owned and (not material['unlit'] or material['base_color_texture'] is None):
                problems.append(f'Export lost unlit atlas material: {material["name"]}')
        if owned - {m['name'] for m in exported}:
            problems.append('Export lost owned materials')
        for primitive in report['glb']['primitives']:
            material = exported[primitive['material']] if primitive['material'] is not None else None
            texture = material and material['base_color_texture']
            if texture and f'TEXCOORD_{texture.get("texCoord", 0)}' not in primitive['attributes']:
                problems.append('Export lost texture coordinate attribute')
        if owned and not report['glb']['images']:
            problems.append('Export lost atlas images')
    if render:
        from refinement_review import _tile
        frame_path = Path(frame_manifest) if frame_manifest else workspace/'modified/views.json'
        frames = json.loads(frame_path.read_text())
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = 1
        scene.cycles.use_denoising = False
        scene.cycles.seed = 0
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        scene.view_settings.exposure = 0
        scene.view_settings.gamma = 1
        scene.render.resolution_x, scene.render.resolution_y = frames['tile_size']
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'PNG'
        scene.render.film_transparent = False
        world = bpy.data.worlds.new('Audit black world')
        world.use_nodes = True
        world.node_tree.nodes.get('Background').inputs['Color'].default_value = (0,0,0,1)
        scene.world = world
        buffers = []
        for f in frames['views']:
            camera = bpy.data.objects.new('Audit camera', bpy.data.cameras.new('Audit camera'))
            scene.collection.objects.link(camera)
            camera.data.type = 'ORTHO'
            camera.data.ortho_scale = f['ortho_scale']
            camera.data.clip_end = 100000
            camera.matrix_world = Matrix(f['camera_matrix_world'])
            scene.camera = camera
            scene.render.filepath = str(output/f'view-{f["index"]}.png')
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(scene.render.filepath, check_existing=False)
            values = array('f',[0])*len(img.pixels)
            img.pixels.foreach_get(values)
            buffers.append(values)
            bpy.data.images.remove(img)
        _tile(buffers, *frames['tile_size'], output/'materials.png')
        report['frame_manifest_sha256'] = digest(frame_path)
        report['render'] = {'engine': 'CYCLES', 'device': 'CPU', 'samples': 1, 'view_transform': 'Standard', 'material_override': False}
    report['artifact_sha256'] = {p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()}
    if digest(model) != before:
        raise RuntimeError('Candidate changed during read-only audit')
    report['status'] = 'FAIL' if problems else 'STRUCTURAL-PASS'
    (output/'audit.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace')
    parser.add_argument('output')
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--frame-manifest', type=Path)
    parser.add_argument('--render-object-names', type=Path, help='JSON array of explicit owned display-state object names')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    report = run(args.workspace, args.output, render=args.render, export=args.export,
                 frame_manifest=args.frame_manifest,
                 render_object_names=json.loads(args.render_object_names.read_text()) if args.render_object_names else None)
    print(json.dumps({k:report[k] for k in ('asset_id','status','problems')}))
