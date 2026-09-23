"""Stage disjoint covered and revealed material fills for Leicester architecture."""
import hashlib
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement/blender'))
from tower_texture_scope import capture, verify
from bake_reviewed_asset import stage


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def original_layers(manifest, template=None):
    """Record all existing named UVs and packed atlases, including selected faces."""
    result = {'uv': {}, 'images': {}}
    for name in manifest['object_names']:
        obj = bpy.data.objects[name]
        layer_names = template['uv'][name] if template else [layer.name for layer in obj.data.uv_layers]
        result['uv'][name] = {layer: hashlib.sha256(json.dumps(
            [list(value.uv) for value in obj.data.uv_layers[layer].data]).encode()).hexdigest()
            for layer in layer_names}
        if template is None:
            for material in obj.data.materials:
                if not material or not material.use_nodes:
                    continue
                for node in material.node_tree.nodes:
                    image = getattr(node, 'image', None)
                    if image:
                        if not image.packed_file:
                            raise ValueError('Approved atlas is not packed: ' + image.name)
                        result['images'][image.name] = hashlib.sha256(image.packed_file.data).hexdigest()
    if template is not None:
        result['images'] = {name: hashlib.sha256(bpy.data.images[name].packed_file.data).hexdigest()
                            for name in template['images']}
    return result


def prepare(experiment, labels):
    experiment = Path(experiment).resolve()
    manifest = json.loads((experiment / 'views.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(experiment / 'approved-model.blend'))
    displayed = manifest.get('render_object_names')
    if displayed is None:
        displayed = [name for name in manifest['object_names'] if not bpy.data.objects[name].hide_render]
    selected, protected = capture(manifest, labels=labels, displayed_names=displayed)
    if not selected:
        raise ValueError('No approved receiver polygons matched the requested labels')
    manifest.update(texture_receiver_object_names=sorted(selected),
                    texture_receiver_face_indices=selected,
                    texture_projection_labels=labels,
                    texture_material_suffix='wave2-generated-' + '-'.join(labels))
    (experiment / 'views-scoped.json').write_text(json.dumps(manifest, indent=2) + '\n')
    report = {'source_blend_sha256': digest(experiment / 'approved-model.blend'),
              'labels': labels, 'selected_faces': selected,
              'protected_faces': protected}
    (experiment / 'scope-before.json').write_text(json.dumps(report, indent=2) + '\n')
    return {'asset_id': manifest['asset_id'], 'labels': labels,
            'selected_faces': sum(map(len, selected.values())),
            'protected_faces': sum(map(len, protected.values()))}


def bake(experiment, output, source_blend=None):
    experiment, output = Path(experiment).resolve(), Path(output).resolve()
    manifest_path = experiment / 'views-scoped.json'
    manifest = json.loads(manifest_path.read_text())
    source = Path(source_blend).resolve() if source_blend else experiment / 'approved-model.blend'
    bpy.ops.wm.open_mainfile(filepath=str(source))
    selected, protected = capture(manifest, labels=manifest['texture_projection_labels'],
                                  displayed_names=manifest['texture_receiver_object_names'])
    if selected != manifest['texture_receiver_face_indices']:
        raise ValueError('Material ownership differs from the approved polygon scope')
    generation = experiment / 'generation-short-no-mask-with-lighting'
    source_sha = digest(source)
    original = original_layers(manifest)
    stage(manifest_path, generation / 'generated-preserved.png', output,
          texels_per_unit=2, reconciliation_reference=generation / 'generated-raw.png')
    result = verify(manifest, protected)
    if original != original_layers(manifest, original):
        raise RuntimeError('An original named UV layer or packed source atlas changed')
    result.update(status='PASS', asset_id=manifest['asset_id'],
                  source_blend=str(source), source_blend_sha256=source_sha,
                  baked_model_sha256=digest(output / 'worker.blend'),
                  selected_labels=manifest['texture_projection_labels'],
                  original_uv_and_packed_atlases_preserved=True, original_layers=original)
    (output / 'protected-materials.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    if args[0] == 'prepare':
        result = prepare(args[1], args[2:])
    elif args[0] == 'bake':
        result = bake(*args[1:])
    else:
        raise ValueError('Expected prepare EXP LABEL... or bake EXP OUTPUT [SOURCE_BLEND]')
    print(json.dumps(result), flush=True)
