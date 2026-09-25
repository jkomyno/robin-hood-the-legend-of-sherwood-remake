"""Render verified atlas provenance on the saved mesh without modifying it.

Red shows unfilled visible texels, green preserved source, blue generated fill,
yellow bounded extrapolation, and magenta materials without provenance evidence.
This diagnoses coverage independently of whether a gray or black color looks
plausible. It does not establish material quality or approve a texture.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np

from render_multiview_asset import render


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect(manifest_path, bake, output, *, provenance_reports=None):
    manifest_path, bake, output = map(Path, (manifest_path, bake, output))
    if output.exists():
        raise ValueError('Coverage output must be a fresh directory')
    model = bake / 'worker.blend'
    model_hash = sha(model)
    manifest = json.loads(manifest_path.read_text())
    bpy.ops.wm.open_mainfile(filepath=str(model.resolve()))
    scene = bpy.data.scenes[manifest['scene_name']]
    bpy.context.window.scene = scene
    records = []
    report_paths = ([Path(path) for path in provenance_reports] if provenance_reports is not None
                    else sorted(bake.glob('layer-*.json')))
    for report_path in report_paths:
        for entry in json.loads(report_path.read_text())['objects']:
            if entry.get('texel_provenance'):
                records.append((report_path, entry))
    if not records:
        raise ValueError('No explicit atlas provenance; do not infer it from alpha')
    palette = np.asarray([[1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 1], [1, 1, 0, 1]], dtype=np.float32)
    evidence, replacements = [], []
    matched = set()
    try:
        for report_path, entry in records:
            obj = scene.objects.get(entry['object'])
            if obj is None:
                raise ValueError('Missing provenance receiver: ' + entry['object'])
            proof = entry['texel_provenance']
            path = Path(proof['path'])
            if sha(path) != proof['sha256']:
                raise ValueError('Provenance changed: ' + str(path))
            with np.load(path, allow_pickle=False) as data:
                ownership = data['ownership'].copy()
            if not np.isin(ownership, np.arange(4)).all():
                raise ValueError('Unknown provenance class')
            slots = []
            for index, material in enumerate(obj.data.materials):
                if not material or not material.use_nodes:
                    continue
                textures = [n for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
                if len(textures) != 1 or not textures[0].image.packed_file:
                    continue
                if hashlib.sha256(textures[0].image.packed_file.data).hexdigest() != proof['packed_image_sha256']:
                    continue
                uv_nodes = [n for n in material.node_tree.nodes if n.type == 'UVMAP']
                if len(uv_nodes) != 1:
                    raise ValueError('Ambiguous provenance UV mapping')
                uv = obj.data.uv_layers[uv_nodes[0].uv_map]
                if hashlib.sha256(json.dumps([list(x.uv) for x in uv.data]).encode()).hexdigest() != proof['uv_sha256']:
                    raise ValueError('Provenance UV layout changed')
                width, height = textures[0].image.size
                if ownership.shape != (height, width):
                    raise ValueError('Provenance atlas shape changed')
                diagnostic = bpy.data.images.new('Coverage diagnostic', width=width, height=height, alpha=True)
                diagnostic.colorspace_settings.name = 'Non-Color'
                diagnostic.pixels.foreach_set(palette[ownership].ravel())
                diagnostic.update()
                copy = material.copy()
                texture = copy.node_tree.nodes[textures[0].name]
                texture.image = diagnostic
                texture.interpolation = 'Closest'
                replacements.append((obj, index, material))
                obj.data.materials[index] = copy
                matched.add((obj.name, index))
                slots.append(index)
            if not slots:
                raise ValueError('Saved atlas does not match provenance: ' + obj.name)
            evidence.append({'object': obj.name, 'slots': slots, 'report': str(report_path.resolve()),
                             'report_sha256': sha(report_path), 'provenance': proof})
        # Displayed materials without matching evidence are conspicuous, never
        # silently reported as filled based on their rendered color.
        from reviewed_texture_scope import displayed_objects
        displayed = displayed_objects(manifest, [o for o in scene.objects if not o.hide_render and o.get('asset_group') == manifest['asset_id']])
        unverified = []
        for obj in displayed:
            if obj.type != 'MESH':
                continue
            for index in {face.material_index for face in obj.data.polygons}:
                if (obj.name, index) in matched:
                    continue
                original = obj.data.materials[index] if index < len(obj.data.materials) else None
                if original is None:
                    raise ValueError('Displayed receiver has no material')
                material = bpy.data.materials.new('Coverage evidence missing')
                material.use_nodes = True
                material.node_tree.nodes.clear()
                emission = material.node_tree.nodes.new('ShaderNodeEmission')
                emission.inputs['Color'].default_value = (1, 0, 1, 1)
                terminal = material.node_tree.nodes.new('ShaderNodeOutputMaterial')
                material.node_tree.links.new(emission.outputs[0], terminal.inputs['Surface'])
                replacements.append((obj, index, original))
                obj.data.materials[index] = material
                unverified.append({'object': obj.name, 'slot': index})
        output.mkdir(parents=True)
        render(manifest_path, output, width=manifest['tile_size'][0])
        from PIL import Image
        width, height = manifest['tile_size']
        sheet = Image.new('RGBA', (width * 4, height * 2))
        views = []
        for index in range(8):
            path = output / f'view-{index}-textured.png'
            with Image.open(path) as image:
                rgba = np.asarray(image.convert('RGBA'))
                sheet.paste(image, ((index % 4) * width, (index // 4) * height))
            rgb = rgba[:, :, :3].astype(float)
            visible = rgba[:, :, 3] > 127
            red = visible & (rgb[:, :, 0] > 80) & (rgb[:, :, 0] > 2 * rgb[:, :, 1]) & (rgb[:, :, 0] > 2 * rgb[:, :, 2])
            views.append({'index': index, 'unfilled_visible_pixels': int(red.sum()), 'sha256': sha(path)})
        sheet.save(output / 'coverage.png')
        report = {'status': 'DIAGNOSTIC', 'asset_id': manifest['asset_id'], 'model_sha256': model_hash,
                  'manifest_sha256': sha(manifest_path), 'palette': {'red': 'unfilled', 'green': 'source', 'blue': 'generated', 'yellow': 'bounded extrapolation', 'magenta': 'unverified material'},
                  'views': views, 'unverified_materials': unverified, 'atlas_evidence': evidence,
                  'coverage_sheet_sha256': sha(output / 'coverage.png'),
                  'limitations': ['Eight cameras do not prove coverage of unseen undersides.', 'Pixel counts use nearest atlas sampling and exclude translucent edge pixels; inspect the diagnostic sheet.']}
        if sha(model) != model_hash:
            raise ValueError('Saved worker changed during diagnostic')
        (output / 'coverage.json').write_text(json.dumps(report, indent=2) + '\n')
        return report
    finally:
        for obj, index, material in reversed(replacements):
            obj.data.materials[index] = material


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('bake', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--provenance-report', type=Path, action='append', default=None,
                        help='Exact replay report; saved packed atlas and UV hashes must still match')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    result = inspect(args.manifest, args.bake, args.output, provenance_reports=args.provenance_report)
    print(json.dumps({'asset': result['asset_id'], 'views': result['views'], 'unverified_materials': result['unverified_materials']}))
