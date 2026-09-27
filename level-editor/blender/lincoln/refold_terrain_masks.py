"""Re-render the Lincoln terrain workspace against a new reviewed mask manifest.

The terrain geometry, framing and authored ground domain (mask 454) stay exactly
those of the previous workspace. The workspace mask guard freezes the mask
inventory, so a manifest revision (for example the foliage fold-in, where the
ground row gains reviewed exclude_mask_indices) needs a fresh workspace:

* context: an integrated scene that already carries the refined ground
  (grouped-v5 or later); its ground geometry must hash-match the previous model;
* baseline/input: the same scene with the flat pre-refinement ground plane
  (appended from the frozen grouped-v4), so the packet still reviews the terrain
  change against the flat datum;
* model/modified: the refined ground with the observed-source material rebuilt
  from the new ground row (domain minus exclusions).

    /usr/bin/blender --background --threads 2 --python-exit-code 1 \
        --python level-editor/blender/lincoln/refold_terrain_masks.py -- \
        --source-blend <scene.blend> --masks <source-masks.json> --output <workspace> \
        [--previous <workspace>]
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare_terrain as pt  # noqa: E402
import terrain_ground  # noqa: E402
from render_slots import acquire  # noqa: E402
from freeze_tooling import select_tooling  # noqa: E402

FLAT_SOURCE = pt.ROOT / 'grouped/lincoln-grouped-v4.blend'


def surface_digest(obj):
    return terrain_ground.digest({'vertices': [list(v.co) for v in obj.data.vertices],
                                  'faces': [list(p.vertices) for p in obj.data.polygons]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-blend', type=Path, required=True)
    parser.add_argument('--masks', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previous', type=Path, default=pt.ROOT / 'round-4/assets' / pt.ASSET)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    acquire()
    tooling = select_tooling(pt.ROOT / 'tooling/e6b57cb851c7142b')
    from refinement_workspace import _ownership, _files, _freeze_masks, validate
    from refinement_review import render_review
    previous = args.previous.resolve(strict=True)
    old_geometry = json.loads((previous / 'geometry-recipe.json').read_text())
    old_domain = json.loads((previous / 'inspection/ground-domain-ground.json').read_text())
    source_blend = args.source_blend.resolve(strict=True)
    source_hash = pt.sha(source_blend)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    reference = output / 'reference'
    shutil.copytree(previous / 'reference', reference)
    shutil.copytree(previous / 'inspection', output / 'inspection',
                    ignore=shutil.ignore_patterns('coverage-*', 'source-comparison.png', 'footbridge-*'))
    image = reference / 'source.png'
    masks = json.loads(args.masks.read_text())
    inventory = (args.masks.resolve().parent / masks['mask_inventory']).resolve(strict=True)
    masks['mask_inventory'] = str(inventory)
    ground_rows = [r for r in masks['projections']['exterior']['assignments'] if r.get('source_node') == 'ground']
    if len(ground_rows) != 1:
        raise ValueError('Manifest needs exactly one ground row')
    records = {r['index']: r for r in json.loads(inventory.read_text())['masks']}
    authored = [i for i in ground_rows[0]['mask_indices']
                if records[i].get('constraint_kind') == 'reviewed-authored-receiver-domain']
    png = Path(records[authored[0]]['png'])
    png = png if png.is_absolute() else inventory.parent / png
    if len(authored) != 1 or pt.sha(png) != old_domain['bitmap']['sha256']:
        raise ValueError('Ground row must keep the reviewed authored domain of the previous workspace')
    mask_path = output / 'source-masks.json'
    mask_path.write_text(json.dumps(masks, indent=2, sort_keys=True) + '\n')

    bpy.ops.wm.open_mainfile(filepath=str(source_blend))
    bpy.context.window.scene = bpy.data.scenes[pt.SCENE]
    ground = pt.the_ground()
    if surface_digest(ground) != old_geometry['after_geometry_sha256']:
        raise ValueError('Context ground differs from the previously reviewed terrain surface')
    refined = ground.data
    refined.use_fake_user = True
    with bpy.data.libraries.load(str(FLAT_SOURCE), link=False) as (src, dst):
        dst.objects = [ground.name]
    flat_object = dst.objects[0]
    flat = flat_object.data
    bpy.data.objects.remove(flat_object, do_unlink=True)
    if len(flat.polygons) != 2:
        raise ValueError('Flat ground from grouped-v4 is not the frozen plane')
    ground.data = flat
    ground['asset_group'] = pt.ASSET
    ground['asset_name'] = 'Lincoln terrain'
    lighting = json.loads(pt.LIGHTING.read_text())['lighting']
    previous_config = json.loads((previous / 'workspace.json').read_text())
    config = {key: previous_config[key] for key in ('version', 'asset_id', 'scene_name', 'collection_name', 'map_name',
                                                   'part_ids', 'projection_manifest', 'width', 'height',
                                                   'elevation_degrees', 'context_padding', 'lighting', 'terrain_role')}
    config.update(source_blend=str(source_blend), source_blend_sha256=source_hash, source_path=str(image),
                  source_mask_manifest=str(mask_path), tooling=tooling,
                  source_mask_parent_manifest=str(args.masks.resolve()), source_mask_parent_sha256=pt.sha(args.masks),
                  authored_ground_mask_index=authored[0], previous_workspace=str(previous),
                  previous_model_sha256=pt.sha(previous / 'model.blend'),
                  baseline_ground='flat plane appended from ' + str(FLAT_SOURCE))
    _, config['outside_geometry'] = _ownership(config)
    _freeze_masks(output, config)
    outside = {o.name: pt.geometry_hash(o) for o in pt.working_meshes() if o != ground}
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'baseline.blend'), copy=True)
    config['baseline_sha256'] = pt.sha(output / 'baseline.blend')
    frames = json.loads((previous / 'framing.json').read_text())
    nodes = sorted({o.get('source_node') for o in pt.working_meshes() if not o.hide_render}, key=str)
    frames['projection_layers'] = [{'source_path': str(image), 'projection_label': 'exterior', 'receiver_nodes': nodes,
                                    'occluder_nodes': nodes, 'source_sha256': pt.sha(image)}]
    (output / 'framing.json').write_text(json.dumps(frames, indent=2) + '\n')
    options = dict(scene_name=pt.SCENE, collection_name=pt.COLLECTION, asset_id=pt.ASSET, source_path=image,
                   projection_layers=[{k: v for k, v in frames['projection_layers'][0].items() if k != 'source_sha256'}],
                   source_mask_manifest=mask_path)
    print('Rendering input packet', flush=True)
    baseline = render_review(output / 'input', frame_manifest=frames, **options)
    config['input_files'] = _files(output / 'input')
    config['reference_files'] = _files(reference)
    (output / 'workspace.json').write_text(json.dumps(config, indent=2) + '\n')

    ground.data = refined
    refined.use_fake_user = False
    refined.materials.clear()
    for material in flat.materials:
        refined.materials.append(material)
    for face in refined.polygons:
        face.material_index = 0
    report = {**old_geometry, 'context_scene': str(source_blend), 'context_scene_sha256': source_hash,
              'geometry_reused_from': str(previous / 'model.blend')}
    bridge = [o for o in pt.working_meshes() if o.get('source_node') in ('building-045', 'building-046')]
    report['footbridge_clearance'] = terrain_ground.footbridge_clearance(ground, bridge)
    material = pt.install_ground_source_material(ground, image, mask_path, output)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'model.blend'))
    print('Rendering modified packet', flush=True)
    modified = render_review(output / 'modified', frame_manifest=output / 'input/views.json', **options)
    after = {o.name: pt.geometry_hash(o) for o in pt.working_meshes() if o != ground}
    if after != outside or pt.sha(source_blend) != source_hash:
        raise ValueError('Refold changed outside geometry or the frozen source')
    if surface_digest(ground) != old_geometry['after_geometry_sha256']:
        raise ValueError('Refold changed the terrain surface')
    shared = validate(output)
    validation = {**shared, 'outside_objects_preserved': len(outside), 'source_blend_sha256': source_hash,
                  'baseline_sha256': pt.sha(output / 'baseline.blend'), 'model_sha256': pt.sha(output / 'model.blend'),
                  'source_image_sha256': pt.sha(image), 'fixed_cameras_preserved': True, 'geometry': report,
                  'tooling': tooling, 'stored_ground_material': material,
                  'ownership': 'Explicit reviewed terrain source assignment with reviewed exclusions; scene visibility retained',
                  'approval': 'pending', 'texture_generation': 'not started'}
    (output / 'geometry-recipe.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    binding = {**validation, 'version': 1, 'input_files': _files(output / 'input'),
               'reference_files': _files(reference), 'modified_files': _files(output / 'modified'),
               'workspace_sha256': pt.sha(output / 'workspace.json'), 'recipe_sha256': pt.sha(__file__),
               'argv': sys.argv, 'accepted_known_pixels': sum(v['counts']['source'] for v in modified['views']),
               'input_known_pixels': sum(v['counts']['source'] for v in baseline['views'])}
    (output / 'terrain-packet.json').write_text(json.dumps(binding, indent=2) + '\n')
    print(json.dumps({k: validation[k] for k in ('status', 'model_sha256', 'outside_objects_preserved')}))


if __name__ == '__main__':
    main()
