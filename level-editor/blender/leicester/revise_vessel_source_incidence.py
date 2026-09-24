"""Create an isolated, source-only incidence revision without changing meshes."""
import argparse
from array import array
import hashlib
import json
from pathlib import Path
import shutil
import sys


def run(approved, output, cosine):
    import bpy
    import refinement_workspace as workspace
    from bake_reviewed_asset import _materials
    from source_projection_bake import bake
    import audit_stored_materials

    approved, output = Path(approved).resolve(), Path(output).resolve()
    if Path(bpy.data.filepath).resolve() != approved / 'model.blend':
        raise ValueError('Load the immutable approved source worker')
    if not .05 < cosine < 1:
        raise ValueError('Expected a stricter source incidence cosine')
    workspace.validate(approved)
    config = json.loads((approved / 'workspace.json').read_text())
    targets, _ = workspace._ownership(config)
    if len(targets) != 1 or config.get('projection_manifest'):
        raise ValueError('This recipe requires one exterior vessel receiver')
    obj = targets[0]
    object_name = obj.name
    geometry = {o.name: workspace._geometry(o) for o in bpy.context.scene.objects}
    outside = {o.name: _materials(o) for o in bpy.context.scene.objects
               if o.type == 'MESH' and o != obj}
    old_uv = {layer.name: [tuple(v.uv) for v in layer.data] for layer in obj.data.uv_layers}
    old_materials = [(m, m.name if m else None) for m in obj.data.materials]
    old_material_names = [name for _, name in old_materials]
    images = {}
    for material, _ in old_materials:
        if material and material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    image = node.image
                    pixels = array('f', [0]) * len(image.pixels)
                    image.pixels.foreach_get(pixels)
                    images[image.name] = hashlib.sha256(pixels.tobytes()).hexdigest()
    approved_hash = workspace._sha(approved / 'model.blend')
    output.mkdir(parents=True, exist_ok=False)
    for name in ('reference', 'mask-reference'):
        if (approved / name).exists():
            shutil.copytree(approved / name, output / name)
    shutil.copytree(approved / 'modified', output / 'input')
    for name in ('baseline.blend', 'model.blend'):
        shutil.copy2(approved / 'model.blend', output / name)
    if (approved / 'source-masks.json').exists():
        shutil.copy2(approved / 'source-masks.json', output / 'source-masks.json')
    config.update(baseline_sha256=approved_hash, source_blend=str(approved / 'model.blend'),
                  source_blend_sha256=approved_hash, input_files=workspace._files(output / 'input'))
    # Native mask and artwork paths remain bound to the unchanged approved evidence.
    config['source_projection_revision'] = {'kind': 'receiver-incidence-floor',
        'previous_workspace': str(approved), 'previous_model_sha256': approved_hash,
        'minimum_cosine': cosine, 'approval': 'pending new source-ownership review'}
    workspace._json(output / 'workspace.json', config)
    bpy.ops.wm.open_mainfile(filepath=str(output / 'model.blend'))
    bpy.context.window.scene = bpy.data.scenes[config['scene_name']]
    obj = bpy.data.objects[object_name]
    obj['projection_min_cosine'] = cosine
    report_dir = output / 'projection' / 'source-incidence'
    report_dir.mkdir(parents=True)
    report = bake(config['map_name'], config['source_path'], report_dir / 'ownership.json',
        receiver_nodes=config['part_ids'], receiver_object_names=[obj.name],
        collection_name=config['collection_name'], projection_label='exterior',
        elevation_deg=config['elevation_degrees'], preserve_authored=False,
        source_mask_manifest=config.get('source_mask_manifest'),
        material_suffix='source-incidence-' + str(cosine))
    if geometry != {o.name: workspace._geometry(o) for o in bpy.context.scene.objects}:
        raise ValueError('Geometry changed during source-only revision')
    if outside != {n: _materials(bpy.data.objects[n]) for n in outside}:
        raise ValueError('Outside materials changed')
    if any(old_uv[n] != [tuple(v.uv) for v in obj.data.uv_layers[n].data] for n in old_uv):
        raise ValueError('Existing UV layer changed')
    if [m.name if m else None for m in obj.data.materials][:len(old_material_names)] != old_material_names:
        raise ValueError('Existing material slots changed')
    for name, expected in images.items():
        image = bpy.data.images[name]
        pixels = array('f', [0]) * len(image.pixels)
        image.pixels.foreach_get(pixels)
        if hashlib.sha256(pixels.tobytes()).hexdigest() != expected:
            raise ValueError('Existing source atlas changed: ' + name)
    workspace._render(config, output / 'modified', output / 'input' / 'views.json')
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'model.blend'))
    validation = workspace.validate(output)
    validation.update(geometry_unchanged=True, existing_uv_layers_preserved=list(old_uv),
        existing_atlas_pixels_preserved=images, outside_materials_unchanged=len(outside),
        source_projection_revision=config['source_projection_revision'])
    workspace._json(output / 'validation.json', validation)
    shutil.copy2(__file__, output / 'recipe.py')
    audit = audit_stored_materials.run(output, output / 'inspection' / 'stored-materials',
                                     render=True, export=True)
    if workspace._sha(approved / 'model.blend') != approved_hash:
        raise ValueError('Approved worker changed')
    workspace._json(output / 'handoff.json', {'status': 'validation-pending',
        'all_eight_views_inspected': False, 'recipe': 'recipe.py',
        'geometry_approval': 'pending new source-ownership review; mesh unchanged',
        'texture_generation': 'not-started', 'ownership': 'projection/source-incidence/ownership.json',
        'previous_approved_workspace': str(approved),
        'previous_approved_model_sha256': approved_hash,
        'notes': ['Grazing source-owned facets become neutral unknown; no native RGB is repainted.',
                  'Threshold is a review hypothesis; existing approval does not transfer.']})
    print(json.dumps({'workspace': str(output), 'cosine': cosine, 'audit': audit['status'],
                      'known_texels': report['known_texels']}), flush=True)


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement' / 'blender'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('approved')
    parser.add_argument('output')
    parser.add_argument('cosine', type=float)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    run(args.approved, args.output, args.cosine)
