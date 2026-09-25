"""Audit complete spire source domains and actual saved source-camera materials."""
import collections
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
sys.path[:0] = [str(ROOT / 'level-editor/refinement/blender'), str(Path(__file__).parent)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_census(workspace, asset, box, *, render_materials=True):
    import bpy
    from mathutils import Vector
    from refinement_review import _tree
    from occlusion_constraints import SourceMaskConstraints
    from source_visibility import first_source_hit
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    config = json.loads((workspace / 'workspace.json').read_text())
    bpy.context.window.scene = bpy.data.scenes[config['scene_name']]
    bpy.context.view_layer.update()
    objects = [o for o in bpy.data.collections[config['collection_name']].all_objects
               if o.type == 'MESH' and not o.hide_render]
    selected_assets = {asset} if isinstance(asset, str) else set(asset)
    owned = [o for o in objects if o.get('asset_group') in selected_assets]
    all_tree, all_owners, _ = _tree(objects)
    tree, owners, _ = _tree(owned)
    constraints = SourceMaskConstraints(workspace / 'source-masks.json', 'exterior',
                                        sha(workspace / 'reference/source.png'), (2304, 3520))
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    toward = Vector((0, -cosine, sine))
    result = {}
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            origin = Vector((x + .5, -(y + .5) * sine, -(y + .5) * cosine)) + toward * 10000
            hit, normal, index, _ = tree.ray_cast(origin, -toward)
            entry = dict(state='no-receiver', receiver=None)
            if index is not None:
                obj = owners[index]
                entry['receiver'] = obj['source_node']
                entry['receiver_object'] = obj.name
                entry['receiver_component'] = obj.get('projection_component')
                entry['cosine'] = normal.dot(toward)
                if not constraints.allowed_pixel(obj, x, y):
                    entry['state'] = 'mask-rejected'
                elif entry['cosine'] <= float(obj.get('projection_min_cosine', .05)):
                    entry['state'] = 'facing-rejected'
                else:
                    _, _, first, _ = first_source_hit(all_tree, all_owners, origin, -toward,
                        constraints=constraints, receiver=obj, source_pixel=(x, y))
                    first_obj = all_owners[first] if first is not None else None
                    entry['state'] = 'accepted' if first_obj == obj else 'blocked'
                    entry['first_receiver'] = first_obj.get('source_node') if first_obj else None
            result[x, y] = entry
    # Reuse the shared actual-material sampler, with a collection containing only this asset.
    collection = bpy.data.collections.new('Spire source-camera audit')
    for obj in owned:
        collection.objects.link(obj)
    from render_source_atlas_crop import render
    destination = workspace / 'inspection/source-actual.png'
    destination.parent.mkdir(exist_ok=True)
    if render_materials:
        render(collection.name, box, destination)
    return result, destination


def exact_rgb(workspace):
    import bpy
    import numpy as np
    from PIL import Image
    from mathutils import Matrix, Vector
    from refinement_review import _tree
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    config = json.loads((workspace / 'workspace.json').read_text())
    scene = bpy.data.scenes[config['scene_name']]
    bpy.context.window.scene = scene
    packet = json.loads((workspace / 'modified/views.json').read_text())
    tree, _, _ = _tree([bpy.data.objects[n] for n in packet['object_names']])
    source = np.array(Image.open(workspace / 'reference/source.png').convert('RGB'))
    width, height = packet['tile_size']
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    camera = bpy.data.cameras.new('Independent spire RGB camera')
    camera.type = 'ORTHO'
    down = Vector((0, -math.sin(math.radians(35)), -math.cos(math.radians(35))))
    count = mismatches = missing = 0
    for view in packet['views']:
        camera.ortho_scale = view['ortho_scale']
        fr = camera.view_frame(scene=scene)
        left, right = min(v.x for v in fr), max(v.x for v in fr)
        bottom, top = min(v.y for v in fr), max(v.y for v in fr)
        matrix = Matrix(view['camera_matrix_world'])
        direction = matrix.to_3x3() @ Vector((0, 0, -1))
        i = view['index']
        known = np.array(Image.open(workspace / f'modified/views/view-{i}-known.png').convert('L')) > 127
        actual = np.array(Image.open(workspace / f'modified/views/view-{i}-textured.png').convert('RGB'))
        for y, x in zip(*np.where(known)):
            count += 1
            origin = matrix @ Vector((left + (int(x) + .5) * (right - left) / width,
                                      top - (int(y) + .5) * (top - bottom) / height, 0))
            hit, _, face, _ = tree.ray_cast(origin, direction)
            if face is None:
                missing += 1
                continue
            sx, sy = math.floor(hit.x), math.floor(hit.dot(down))
            if not (0 <= sx < source.shape[1] and 0 <= sy < source.shape[0]
                    and np.array_equal(actual[y, x], source[sy, sx])):
                mismatches += 1
    report = dict(status='PASS' if not mismatches and not missing else 'FAIL', known_pixels=count,
                  source_rgb_mismatches=mismatches, missing_geometry_hits=missing,
                  model_sha256=sha(workspace / 'model.blend'),
                  modified_views_sha256=sha(workspace / 'modified/views.json'))
    (workspace / 'known-rgb-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['status'] != 'PASS':
        raise ValueError(report)
    return report


def main():
    from PIL import Image, ImageDraw
    workspace = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    config = json.loads((workspace / 'workspace.json').read_text())
    asset = config['asset_id']
    spec = json.loads(Path(__file__).with_name('spire_metal_ridge_traces.json').read_text())['assets'][asset]
    old = WORK / spec['approved_workspace']
    box = spec['source_crop']
    # Do not write even supplementary inspection images into the approved workspace.
    # Source-camera baseline sampling instead uses an isolated disposable scene below.
    import tempfile
    import shutil
    with tempfile.TemporaryDirectory(prefix='spire-source-audit-', dir=workspace) as temp:
        baseline_audit = Path(temp)
        for name in ['model.blend', 'workspace.json', 'source-masks.json']:
            (baseline_audit / name).symlink_to((old / name).resolve())
        (baseline_audit / 'reference').symlink_to((old / 'reference').resolve(), target_is_directory=True)
        before, baseline_image = source_census(baseline_audit, asset, box)
        shutil.copy2(baseline_image, workspace / 'inspection/original-source-actual.png')
    after, current_image = source_census(workspace, asset, box)
    retained = [p for p in before if before[p]['state'] == after[p]['state'] == 'accepted']
    removed = [p for p in before if before[p]['state'] == 'accepted' and after[p]['state'] != 'accepted']
    added = [p for p in before if before[p]['state'] != 'accepted' and after[p]['state'] == 'accepted']
    source = Image.open(workspace / 'reference/source.png').convert('RGB').crop(box)
    # The original native silhouette is independent of the candidate's acceptance.
    mask_manifest = json.loads((old / 'source-masks.json').read_text())
    inventory_path = Path(mask_manifest['mask_inventory'])
    inventory = json.loads(inventory_path.read_text())
    native_index = 444 if 'northeast' in asset else 442
    native = next(row for row in inventory['masks'] if row['index'] == native_index)
    native_path = Path(native['png'])
    if not native_path.is_absolute():
        native_path = inventory_path.parent / native_path
    native_image = Image.open(native_path).convert('L')
    ox, oy = native['box_top_left']
    native_counts = collections.Counter()
    native_pixels = []
    native_overlay = source.copy()
    colors = {'accepted': (0, 180, 0), 'no-receiver': (255, 0, 255),
              'mask-rejected': (255, 170, 0), 'facing-rejected': (0, 255, 255),
              'blocked': (255, 50, 50)}
    for point, row in after.items():
        x, y = point
        if (0 <= x - ox < native_image.width and 0 <= y - oy < native_image.height
                and native_image.getpixel((x - ox, y - oy)) > 127):
            native_counts[row['state']] += 1
            native_pixels.append(dict(source=point, **row))
            native_overlay.putpixel((x - box[0], y - box[1]), colors[row['state']])
    native_sheet = Image.new('RGB', (source.width * 2, source.height))
    native_sheet.paste(source)
    native_sheet.paste(native_overlay, (source.width, 0))
    native_sheet.resize((native_sheet.width * 3, native_sheet.height * 3), Image.Resampling.NEAREST).save(workspace / 'inspection/native-domain-complement.png')
    (workspace / 'inspection/native-domain-complement.json').write_text(json.dumps(dict(
        model_sha256=sha(workspace / 'model.blend'), native_mask_index=native_index,
        native_mask_sha256=sha(native_path), counts=dict(native_counts), pixels=native_pixels,
        legend=colors, status='awaiting-source-visual-classification'), indent=2) + '\n')
    marked = source.copy()
    for points, color in [(retained, (0, 160, 0)), (added, (0, 255, 255)), (removed, (255, 0, 0))]:
        for x, y in points:
            marked.putpixel((x - box[0], y - box[1]), color)
    proof = Image.new('RGB', (source.width * 2, source.height))
    proof.paste(source)
    proof.paste(marked, (source.width, 0))
    proof.resize((proof.width * 3, proof.height * 3), Image.Resampling.NEAREST).save(workspace / 'inspection/source-domain-difference.png')
    panels = [source, Image.open(workspace / 'inspection/original-source-actual.png').convert('RGB'),
              Image.open(current_image).convert('RGB')]
    comparison = Image.new('RGB', (source.width * 3, source.height + 18))
    draw = ImageDraw.Draw(comparison)
    for i, (panel, title) in enumerate(zip(panels, ['Original art', 'Approved atlas', 'Corrected atlas'])):
        comparison.paste(panel, (i * source.width, 18))
        draw.text((i * source.width + 2, 2), title, fill='white')
    comparison.resize((comparison.width * 3, comparison.height * 3), Image.Resampling.NEAREST).save(workspace / 'inspection/source-material-comparison.png')
    report = dict(status='PASS' if not removed else 'FAIL', model_sha256=sha(workspace / 'model.blend'),
        modified_views_sha256=sha(workspace / 'modified/views.json'), original_model_sha256=sha(old / 'model.blend'),
        source_sha256=sha(workspace / 'reference/source.png'),
        source_mask_assignments_unchanged=json.loads((old / 'source-masks.json').read_text())['projections'] == json.loads((workspace / 'source-masks.json').read_text())['projections'],
        retained_source_pixel_count=len(retained), added_source_pixel_count=len(added), removed_source_pixel_count=len(removed),
        original_state_counts=dict(collections.Counter(q['state'] for q in before.values())),
        modified_state_counts=dict(collections.Counter(q['state'] for q in after.values())),
        added_source_pixels=added, removed_source_pixels=removed,
        source_camera_scope='Actual saved materials from the original source camera; foreign context meshes omitted.',
        pixels=[dict(source=p, old=before[p], new=after[p]) for p in before])
    (workspace / 'inspection/source-domain-difference.json').write_text(json.dumps(report, indent=2) + '\n')
    rgb = exact_rgb(workspace)
    print(dict(retained=len(retained), added=len(added), removed=len(removed), rgb=rgb), flush=True)
    if removed:
        raise ValueError('Original source pixels lost; independent classification required')


if __name__ == '__main__':
    main()
