"""Post-publication Smart UV rebake of one Lincoln asset, for comparison only (never publishes).

Run from the repository root (Blender, background; the source blend is opened read-only):

    blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/uv_unwrap_rebake.py -- \
      --source level-editor/work/lincoln-refinement/textures/combine/stage-v2-6dd36223-combine-batch3/worker.blend \
      --source-sha256 c57c60db187e86fbc2a295da9002ee401a7536a77becf6df9088ececf4f783b5 \
      --asset lincoln-east-gate-north-tower \
      --output level-editor/work/lincoln-refinement/scratch/uv-unwrap/lincoln-east-gate-north-tower

`--objects NAME ...` selects exact mesh objects instead of an `asset_group`. Published assets use
per-face source-projection atlases (every face its own chart, sized to hold source pixels 1:1,
with generated fill combined into the same images). Those atlases stay the provenance record; this
step only derives an alternative layout from them:

1. Append the asset meshes (and their parents) from the source blend into an empty file.
2. Duplicate them, add an `Unwrapped atlas` UV layer and run Smart UV Project over all meshes at
   once (one shared atlas). Smart UV projects each island onto a single plane, which foreshortens
   curved islands; by default (`--relax ANGLE_BASED`) its island borders become seams and each
   island is re-flattened with Unwrap. Then Pack Islands with rotation.
3. Atlas size: per-face texel density (texels per world unit = map pixel) is measured on the
   source atlases; the smallest power of two (or multiple of 256 with `--rounding 256`) whose
   packed layout reaches the source's area-weighted median density is chosen, capped at
   `--max-size`. The pack margin is re-derived until it spans `--pack-margin-px` texels.
4. Cycles EMIT bake on the duplicates: each used material is reduced to its image texture, read
   through its original UV layer and emitted into the new layer; a second pass bakes the source
   alpha (observed/inferred ownership) into the atlas alpha. The originals are never modified.
5. Validation: the eight frozen review cameras of the asset's current workspace render the
   originals and the unwrapped duplicates (emission only, identical Cycles settings); per-view
   color differences are measured and composed into comparison sheets.
6. Writes `<output>/model.blend` (unwrapped asset only, atlas packed), `glb/model.glb` (+
   `asset.json`, shared editor exporter), `atlas.png`, `compare-sheet.png`,
   `atlas-comparison.png`, `renders/` and `report.json`.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
LEVEL_EDITOR = HERE.parents[1]
ROOT = LEVEL_EDITOR / 'work/lincoln-refinement'
NEW_UV = 'Unwrapped atlas'
BACKGROUND = 128  # sheet/diff background gray (0-255) under transparent render pixels


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def weighted_quantile(values, weights, q):
    order = np.argsort(values)
    values, weights = np.asarray(values)[order], np.asarray(weights)[order]
    cumulative = np.cumsum(weights)
    require(cumulative[-1] > 0, 'Weighted quantile of zero total weight')
    return float(values[np.searchsorted(cumulative, q * cumulative[-1])])


def stats(values, weights):
    values = np.asarray(values, dtype=np.float64)
    return {'area_weighted_median': weighted_quantile(values, weights, .5),
            'area_weighted_p10': weighted_quantile(values, weights, .1),
            'area_weighted_p90': weighted_quantile(values, weights, .9),
            'face_median': float(np.median(values)), 'min': float(values.min()), 'max': float(values.max())}


def find_views(asset_id):
    """The frozen eight-camera packet of the asset's current workspace."""
    candidates = [ROOT / 'round-6/assets' / asset_id]
    overrides = json.loads((ROOT / 'workspace-overrides-v6.json').read_text())['assets']
    if asset_id in overrides:
        candidates.append(Path(overrides[asset_id]))
    for workspace in candidates:
        for packet in ('modified/views.json', 'input/views.json'):
            if (workspace / packet).is_file():
                return workspace / packet
    raise FileNotFoundError(f'No workspace views.json for {asset_id} in {candidates}')


def face_geometry(obj, layer_name):
    """World area and UV area (unit square) of every polygon."""
    mesh, matrix = obj.data, obj.matrix_world
    world = [matrix @ v.co for v in mesh.vertices]
    uv = mesh.uv_layers[layer_name].uv
    areas, uv_areas = [], []
    for poly in mesh.polygons:
        points = [world[i] for i in poly.vertices]
        normal = sum(((points[i] - points[0]).cross(points[i + 1] - points[0])
                      for i in range(1, len(points) - 1)), points[0] * 0)
        areas.append(normal.length / 2)
        coords = [uv[i].vector for i in poly.loop_indices]
        uv_areas.append(abs(sum(coords[i].x * coords[i - 1].y - coords[i - 1].x * coords[i].y
                                for i in range(len(coords)))) / 2)
    return np.array(areas), np.array(uv_areas)


def face_axes(obj, layer_name, width, height):
    """Per-face (min, max) texels per world unit along the principal axes of the UV map.

    Uses the largest fan triangle of each polygon; a stretched layout shows up as min << max.
    """
    mesh, matrix = obj.data, obj.matrix_world
    world = [matrix @ v.co for v in mesh.vertices]
    uv = mesh.uv_layers[layer_name].uv
    rows = []
    for poly in mesh.polygons:
        corners = list(zip(poly.vertices, poly.loop_indices))
        best = max(range(1, len(corners) - 1), key=lambda i: (world[corners[i][0]] - world[corners[0][0]]).cross(
            world[corners[i + 1][0]] - world[corners[0][0]]).length)
        (v0, l0), (v1, l1), (v2, l2) = corners[0], corners[best], corners[best + 1]
        e1, e2 = world[v1] - world[v0], world[v2] - world[v0]
        axis_x = e1.normalized() if e1.length > 0 else e1
        axis_y = e1.cross(e2).cross(e1)
        if e1.length == 0 or axis_y.length == 0:
            rows.append((0.0, 0.0))
            continue
        axis_y.normalize()
        local = np.array([[e1.dot(axis_x), e2.dot(axis_x)], [e1.dot(axis_y), e2.dot(axis_y)]])
        scale = np.array([width, height])
        texel = np.array([(uv[l1].vector - uv[l0].vector)[:], (uv[l2].vector - uv[l0].vector)[:]]).T * scale[:, None]
        singular = np.linalg.svd(texel @ np.linalg.inv(local), compute_uv=False)
        rows.append((float(singular.min()), float(singular.max())))
    return np.array(rows)


def uv_islands(meshes, layer_name):
    """Connected face sets whose shared edges also share both UV endpoints."""
    import bmesh
    total = 0
    for mesh in meshes:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        uv = bm.loops.layers.uv[layer_name]
        parent = list(range(len(bm.faces)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        close = lambda a, b: (a - b).length < 1e-6
        for edge in bm.edges:
            loops = list(edge.link_loops)
            if len(loops) != 2:
                continue
            a, b = loops
            a0, a1 = a[uv].uv, a.link_loop_next[uv].uv
            b0, b1 = b[uv].uv, b.link_loop_next[uv].uv
            if (close(a0, b1) and close(a1, b0)) or (close(a0, b0) and close(a1, b1)):
                parent[find(a.face.index)] = find(b.face.index)
        total += len({find(i) for i in range(len(bm.faces))})
        bm.free()
    return total


def uv_coverage(objects, layer_name, size):
    """Per-texel face count of a UV layout rasterized at `size` (texel centers)."""
    from PIL import Image, ImageDraw
    count = np.zeros((size, size), dtype=np.int32)
    degenerate = 0
    for obj in objects:
        uv = obj.data.uv_layers[layer_name].uv
        for poly in obj.data.polygons:
            points = [(uv[i].vector.x * size - .5, (1 - uv[i].vector.y) * size - .5) for i in poly.loop_indices]
            x0, y0 = (max(0, math.floor(min(p[i] for p in points))) for i in (0, 1))
            x1, y1 = (min(size, math.ceil(max(p[i] for p in points)) + 1) for i in (0, 1))
            if x1 <= x0 or y1 <= y0:
                degenerate += 1
                continue
            mask = Image.new('1', (x1 - x0, y1 - y0))
            ImageDraw.Draw(mask).polygon([(x - x0, y - y0) for x, y in points], fill=1)
            count[y0:y1, x0:x1] += np.asarray(mask, dtype=np.int32)
    return count, degenerate


def material_image(material, obj):
    """Reduce a used material to (image, uv layer, interpolation, extension) or refuse."""
    tree = material.node_tree
    require(tree is not None, f'Material without nodes: {material.name}')
    outputs = [n for n in tree.nodes if n.bl_idname == 'ShaderNodeOutputMaterial' and n.is_active_output]
    require(len(outputs) == 1, f'Material needs one active output: {material.name}')
    surface = outputs[0].inputs['Surface']
    require(surface.is_linked, f'Unlinked surface: {material.name}')
    node = surface.links[0].from_node
    if node.bl_idname == 'ShaderNodeEmission':
        require(abs(node.inputs['Strength'].default_value - 1) < 1e-6 and node.inputs['Color'].is_linked,
                f'Unsupported emission setup: {material.name}')
        node = node.inputs['Color'].links[0].from_node
    require(node.bl_idname == 'ShaderNodeTexImage' and node.image is not None,
            f'Surface is not a plain image texture (unsupported for rebake): {material.name}')
    vector = node.inputs['Vector']
    if vector.is_linked:
        uv_node = vector.links[0].from_node
        require(uv_node.bl_idname == 'ShaderNodeUVMap' and uv_node.uv_map,
                f'Image vector is not an explicit UV Map node: {material.name}')
        layer = uv_node.uv_map
    else:
        layer = next(u.name for u in obj.data.uv_layers if u.active_render)
    require(layer in obj.data.uv_layers, f'{material.name} reads missing UV layer {layer} on {obj.name}')
    return node.image, layer, node.interpolation, node.extension


def image_record(image):
    width, height = image.size
    return {'name': image.name, 'size': [width, height], 'pixels': width * height,
            'rgba8_bytes': width * height * 4, 'rgba8_mipmapped_bytes': round(width * height * 4 * 4 / 3),
            'png_bytes': image.packed_file.size if image.packed_file else None,
            'source_filepath': image.filepath or None}


def image_array(image):
    """uint8 RGBA, top row first, of a byte image (Blender pixels are raw byte values / 255)."""
    width, height = image.size
    buffer = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(buffer)
    return np.flipud((buffer.reshape(height, width, 4) * 255 + .5).clip(0, 255).astype(np.uint8))


def build_material(name, image, layer, interpolation, extension, *, emission_from, target=None):
    """UV Map -> Image -> (Emission) -> Output; optional active bake target node."""
    import bpy
    material = bpy.data.materials.new(name)
    if material.node_tree is None:
        material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new('ShaderNodeOutputMaterial')
    uv_node = tree.nodes.new('ShaderNodeUVMap')
    uv_node.uv_map = layer
    texture = tree.nodes.new('ShaderNodeTexImage')
    texture.image, texture.interpolation, texture.extension = image, interpolation, extension
    tree.links.new(uv_node.outputs['UV'], texture.inputs['Vector'])
    if emission_from is None:
        # Same graph shape as the published projection materials (exported as unlit).
        tree.links.new(texture.outputs['Color'], output.inputs['Surface'])
    else:
        emission = tree.nodes.new('ShaderNodeEmission')
        emission.inputs['Strength'].default_value = 1.0
        tree.links.new(texture.outputs[emission_from], emission.inputs['Color'])
        tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])
    if target is not None:
        node = tree.nodes.new('ShaderNodeTexImage')
        node.image = target
        for other in tree.nodes:
            other.select = False
        node.select = True
        tree.nodes.active = node
    return material


def set_slots(obj, materials, face_slots):
    """Replace all slots with `materials` and point every face at its new slot index."""
    mesh = obj.data
    mesh.materials.clear()
    for material in materials:
        mesh.materials.append(material)
    mesh.polygons.foreach_set('material_index', face_slots)
    mesh.update()


def unwrap(duplicates, args, source_density):
    """Smart project + pack; returns (size, pack margin, per-face new UV areas)."""
    import bpy
    bpy.ops.object.select_all(action='DESELECT')
    for obj in duplicates:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = duplicates[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(args.angle_limit), island_margin=args.island_margin,
                             area_weight=1.0, correct_aspect=True, scale_to_bounds=False)
    if args.relax != 'none':
        # Smart UV projects each island onto one plane, so curved islands (a tower's cylinder band)
        # are foreshortened up to cos(angle limit) across the surface. Keep its islands as seams and
        # flatten each island instead; packing then sees near-isotropic charts.
        bpy.ops.mesh.mark_seam(clear=True)
        bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)
        bpy.ops.uv.unwrap(method=args.relax, fill_holes=True, correct_aspect=True,
                          margin_method='FRACTION', margin=args.island_margin)
    margin = args.island_margin
    history = []
    for _ in range(6):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, rotate_method='ANY', scale=True,
                                margin_method='FRACTION', margin=margin, shape_method='CONCAVE')
        bpy.ops.object.mode_set(mode='OBJECT')
        areas, uv_areas = [], []
        for obj in duplicates:
            area, uv_area = face_geometry(obj, NEW_UV)
            areas.append(area)
            uv_areas.append(uv_area)
        area, uv_area = np.concatenate(areas), np.concatenate(uv_areas)
        ratio = weighted_quantile(np.sqrt(uv_area / np.maximum(area, 1e-12)), area, .5)
        required = source_density / ratio
        if args.rounding == 'pow2':
            size = 2 ** max(8, math.ceil(math.log2(required)))
        else:
            size = 256 * max(1, math.ceil(required / 256))
        capped = size > args.max_size
        size = min(size, args.max_size)
        history.append({'pack_margin_fraction': margin, 'required_size': required, 'size': size,
                        'uv_utilization': float(uv_area.sum())})
        if margin * size >= args.pack_margin_px - 1e-9:
            return size, capped, required, margin, history, uv_areas
        margin = args.pack_margin_px / size
    raise RuntimeError(f'Pack margin did not converge: {history}')


def render_views(scene, cameras, out_dir, show, hide):
    import bpy
    out_dir.mkdir(parents=True)
    for obj in hide:
        obj.hide_render = True
    for obj in show:
        obj.hide_render = False
    paths = []
    for index, camera in enumerate(cameras):
        scene.camera = camera
        scene.render.filepath = str(out_dir / f'view-{index}.png')
        bpy.ops.render.render(write_still=True, scene=scene.name)
        paths.append(out_dir / f'view-{index}.png')
    return paths


def composite(path):
    from PIL import Image
    rgba = np.asarray(Image.open(path).convert('RGBA')).astype(np.float64)
    alpha = rgba[..., 3:] / 255
    return rgba[..., :3] * alpha + BACKGROUND * (1 - alpha), rgba[..., 3] > 0


def label(image, text, height=28):
    from PIL import Image, ImageDraw
    canvas = Image.new('RGB', (image.width, image.height + height), (24, 24, 24))
    canvas.paste(image, (0, height))
    ImageDraw.Draw(canvas).text((6, 7), text, fill=(235, 235, 235))
    return canvas


def compare(original_paths, unwrapped_paths, output, labels=('original (per-face source atlases)', 'unwrapped (Smart UV rebake)')):
    """Per-view difference statistics and a labelled original/unwrapped/diff sheet."""
    from PIL import Image
    rows, per_view = [[], [], []], []
    for index, (before_path, after_path) in enumerate(zip(original_paths, unwrapped_paths)):
        before, covered_before = composite(before_path)
        after, covered_after = composite(after_path)
        covered = covered_before | covered_after
        require(covered.any(), f'View {index} renders nothing')
        delta = np.abs(before - after)
        peak = delta.max(axis=2)[covered]
        per_view.append({'view': index, 'covered_pixels': int(covered.sum()),
                         'silhouette_mismatch_pixels': int((covered_before != covered_after).sum()),
                         'mean': float(peak.mean()), 'mean_rgb': float(delta[covered].mean()),
                         'p95': float(np.percentile(peak, 95)), 'max': float(peak.max()),
                         'fraction_over_8': float((peak > 8).mean()), 'fraction_over_24': float((peak > 24).mean())})
        heat = np.zeros(before.shape, dtype=np.float64) + 16
        heat[covered] = np.minimum(255, delta[covered] * 4)
        stats_text = f"v{index} mean {per_view[-1]['mean']:.2f} p95 {per_view[-1]['p95']:.1f} max {per_view[-1]['max']:.0f}"
        for row, pixels, text in ((0, before, f'v{index} {labels[0]}'),
                                  (1, after, f'v{index} {labels[1]}'),
                                  (2, heat, stats_text + ' | |diff| x4')):
            rows[row].append(label(Image.fromarray(pixels.round().astype(np.uint8)), text))
    tile_w, tile_h = rows[0][0].size
    half = (len(original_paths) + 1) // 2
    sheet = Image.new('RGB', (tile_w * half, tile_h * 6), (24, 24, 24))
    for block in range(2):
        for row in range(3):
            for column, tile in enumerate(rows[row][block * half:(block + 1) * half]):
                sheet.paste(tile, (column * tile_w, (block * 3 + row) * tile_h))
    sheet.save(output)
    return {'per_view': per_view,
            'overall': {'mean_of_view_means': float(np.mean([v['mean'] for v in per_view])),
                        'max_p95': float(max(v['p95'] for v in per_view)),
                        'max': float(max(v['max'] for v in per_view))},
            'metric': 'Per pixel max |channel| difference (0-255) after compositing both renders over '
                      f'gray {BACKGROUND}; statistics over the union of both silhouettes.'}


def atlas_sheet(sources, new_atlas, new_uvs, textures, output, max_edge=2400):
    """Old per-face atlases (with their UV charts) beside the new atlas, same texel scale."""
    from PIL import Image, ImageDraw
    gap = 16
    left_w = max(item['array'].shape[1] for item in sources)
    left_h = sum(item['array'].shape[0] for item in sources) + gap * (len(sources) - 1)
    size = new_atlas.shape[0]
    scale = min(1.0, max_edge / max(left_w + gap * 4 + size, left_h, size))

    def panel(array, charts):
        height, width = array.shape[:2]
        image = Image.fromarray(array[..., :3]).resize((max(1, round(width * scale)), max(1, round(height * scale))),
                                                      Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(image)
        for chart in charts:
            draw.polygon([(u * width * scale, (1 - v) * height * scale) for u, v in chart], outline=(255, 40, 200))
        return image

    left = [panel(item['array'], item['charts']) for item in sources]
    right = panel(new_atlas, new_uvs)
    header = 44
    x_right = max(p.width for p in left) + gap * 4
    width = x_right + right.width
    height = header + max(sum(p.height for p in left) + gap * (len(left) - 1), right.height)
    sheet = Image.new('RGB', (width, height), (24, 24, 24))
    y = header
    for image in left:
        sheet.paste(image, (0, y))
        y += image.height + gap
    sheet.paste(right, (x_right, header))
    draw = ImageDraw.Draw(sheet)
    before, after = textures['before'], textures['after']
    draw.text((4, 4), f"BEFORE: {before['count']} per-face source atlases, {before['pixels']:,} px, "
                      f"RGBA8 {before['rgba8_bytes'] / 2**20:.2f} MiB, PNG {before['png_bytes'] / 2**20:.2f} MiB", fill=(235, 235, 235))
    draw.text((4, 22), f"scale {scale:.3f} display px per texel (both panels)", fill=(170, 170, 170))
    draw.text((x_right, 4), f"AFTER: 1 unwrapped atlas {size}x{size}, RGBA8 {after['rgba8_bytes'] / 2**20:.2f} MiB, "
                            f"PNG {after['png_bytes'] / 2**20:.2f} MiB", fill=(235, 235, 235))
    draw.text((x_right, 22), 'magenta = UV charts', fill=(170, 170, 170))
    sheet.save(output)


def glb_summary(path):
    data = Path(path).read_bytes()
    length, kind = struct.unpack_from('<II', data, 12)
    require(kind == 0x4E4F534A, f'Not a GLB: {path}')
    doc = json.loads(data[20:20 + length])
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'materials': len(doc.get('materials', [])), 'images': len(doc.get('images', [])),
            'image_bytes': sum(doc['bufferViews'][i['bufferView']]['byteLength'] for i in doc.get('images', [])),
            'meshes': len(doc.get('meshes', []))}


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', type=Path, required=True, help='Textured worker/stage .blend (read-only)')
    parser.add_argument('--source-sha256', help='Refuse unless the source blend has this hash')
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--asset', help='asset_group id')
    selection.add_argument('--objects', nargs='+', help='Exact mesh object names')
    parser.add_argument('--output', type=Path, required=True, help='New directory (must not exist)')
    parser.add_argument('--views', type=Path, help='Review views.json (default: current workspace packet)')
    parser.add_argument('--reference-glb', type=Path, help='Published model.glb of the asset, for size comparison')
    parser.add_argument('--angle-limit', type=float, default=66.0, help='Smart UV angle limit (degrees)')
    parser.add_argument('--island-margin', type=float, default=0.003)
    parser.add_argument('--relax', choices=('none', 'ANGLE_BASED', 'CONFORMAL', 'MINIMUM_STRETCH'),
                        default='ANGLE_BASED', help='Re-flatten the Smart UV islands (seams = island borders)')
    parser.add_argument('--pack-margin-px', type=float, default=4.0, help='Minimum pack gap in atlas texels')
    parser.add_argument('--bake-margin', type=int, default=16, help='Bake dilation in texels')
    parser.add_argument('--margin-type', choices=('ADJACENT_FACES', 'EXTEND'), default='ADJACENT_FACES')
    parser.add_argument('--bake-samples', type=int, default=4)
    parser.add_argument('--render-samples', type=int, default=16)
    parser.add_argument('--rounding', choices=('pow2', '256'), default='pow2')
    parser.add_argument('--max-size', type=int, default=8192)
    args = parser.parse_args(argv)

    source = args.source.resolve(strict=True)
    source_sha = sha(source)
    if args.source_sha256:
        require(source_sha == args.source_sha256, f'Source blend hash {source_sha} != {args.source_sha256}')
    output = args.output.resolve()
    require(ROOT.resolve() in output.parents, f'Output must stay under {ROOT}')
    output.mkdir(parents=True, exist_ok=False)

    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(LEVEL_EDITOR / 'refinement/blender'))
    from render_slots import acquire
    acquire()
    import bpy
    from mathutils import Matrix
    from PIL import Image

    # Phase 1: identify the asset in the source file, then start from an empty file.
    bpy.ops.wm.open_mainfile(filepath=str(source))
    if args.asset:
        chosen = [o for o in bpy.data.objects if o.type == 'MESH' and o.get('asset_group') == args.asset]
    else:
        chosen = [bpy.data.objects[name] for name in args.objects]
    require(chosen, 'No meshes selected')
    require(all(o.type == 'MESH' for o in chosen), 'Only mesh objects can be rebaked')
    asset_ids = {o.get('asset_group') for o in chosen}
    require(len(asset_ids) == 1 and None not in asset_ids, f'Objects must share one asset_group: {asset_ids}')
    asset_id = asset_ids.pop()
    working = {c.name for o in chosen for c in o.users_collection}
    require(len(working) == 1 and next(iter(working)).endswith(' Working'), f'Unexpected collections {working}')
    map_name = next(iter(working)).removesuffix(' Working')
    names = sorted(o.name for o in chosen)
    parents = sorted({p.name for o in chosen for p in [o.parent] if p is not None})
    expected = {o.name: (tuple(map(tuple, o.matrix_world)), len(o.data.polygons), len(o.data.vertices)) for o in chosen}
    hidden = sorted(o.name for o in chosen if o.hide_render)
    require(not hidden, f'Render-hidden meshes are not part of the default look: {hidden}')
    bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)

    scene = bpy.context.scene
    scene.name = 'UV unwrap rebake'
    originals_collection = bpy.data.collections.new('Original')
    unwrapped_collection = bpy.data.collections.new(map_name + ' Working')
    scene.collection.children.link(originals_collection)
    scene.collection.children.link(unwrapped_collection)
    with bpy.data.libraries.load(str(source), link=False) as (src, dst):
        dst.objects = names + parents
    loaded = {o.name: o for o in dst.objects}
    require(set(loaded) == set(names + parents), 'Append renamed objects; the file was not empty')
    for obj in loaded.values():
        originals_collection.objects.link(obj)
    bpy.context.view_layer.update()
    originals = [loaded[name] for name in names]
    for obj in originals:
        matrix, faces, vertices = expected[obj.name]
        require(np.allclose(np.array(matrix), np.array(obj.matrix_world), atol=1e-4), f'Transform changed on append: {obj.name}')
        require((len(obj.data.polygons), len(obj.data.vertices)) == (faces, vertices), f'Mesh changed on append: {obj.name}')
        require(not obj.modifiers, f'Modifiers are not supported (edit-mode unwrap acts on base mesh): {obj.name}')

    # Source atlases and per-face density.
    per_object, source_images, charts = [], {}, {}
    all_area, all_density, all_axes, face_materials = [], [], [], {}
    for obj in originals:
        slots = np.empty(len(obj.data.polygons), dtype=np.int32)
        obj.data.polygons.foreach_get('material_index', slots)
        used = sorted(set(slots.tolist()))
        info = {}
        for slot in used:
            material = obj.material_slots[slot].material
            require(material is not None, f'Face uses empty slot {slot} on {obj.name}')
            image, layer, interpolation, extension = material_image(material, obj)
            info[slot] = (material, image, layer, interpolation, extension)
            source_images[image.name] = image
        face_materials[obj.name] = (slots, info)
        area = np.zeros(len(slots))
        texels = np.zeros(len(slots))
        axes = np.zeros((len(slots), 2))
        for slot, (material, image, layer, _, _) in info.items():
            face_area, uv_area = face_geometry(obj, layer)
            mask = slots == slot
            area[mask] = face_area[mask]
            texels[mask] = uv_area[mask] * image.size[0] * image.size[1]
            axes[mask] = face_axes(obj, layer, *image.size)[mask]
            uv = obj.data.uv_layers[layer].uv
            charts.setdefault(image.name, []).extend(
                [tuple(uv[i].vector) for i in poly.loop_indices]
                for poly, used_here in zip(obj.data.polygons, mask) if used_here)
        density = np.sqrt(texels / np.maximum(area, 1e-12))
        all_area.append(area)
        all_density.append(density)
        all_axes.append(axes)
        per_object.append({'object': obj.name, 'faces': len(slots), 'source_node': obj.get('source_node'),
                           'materials': [info[s][0].name for s in used], 'uv_layers': sorted({info[s][2] for s in used}),
                           'zero_uv_faces': int((texels <= 0).sum())})
    area, density, source_axes = np.concatenate(all_area), np.concatenate(all_density), np.concatenate(all_axes)
    require(area.sum() > 0, 'Asset has no surface area')
    before_density = stats(density, area)
    source_density = before_density['area_weighted_median']
    require(source_density > 0, 'Source atlases have no texel density')

    # Duplicates with the new UV layer.
    duplicates = []
    for obj in originals:
        copy = obj.copy()
        copy.data = obj.data.copy()
        copy.parent = None
        copy.matrix_world = obj.matrix_world.copy()
        copy.name = obj.name + ' / unwrapped'
        unwrapped_collection.objects.link(copy)
        layer = copy.data.uv_layers.new(name=NEW_UV)
        copy.data.uv_layers.active = layer
        duplicates.append(copy)
    bpy.context.view_layer.update()
    size, capped, required, pack_margin, pack_history, new_uv_areas = unwrap(duplicates, args, source_density)
    new_area = np.concatenate([face_geometry(o, NEW_UV)[0] for o in duplicates])
    after_density_values = np.sqrt(np.concatenate(new_uv_areas) * size * size / np.maximum(new_area, 1e-12))
    after_density = stats(after_density_values, new_area)
    below = (after_density_values < density - 1e-9)
    new_axes = np.concatenate([face_axes(o, NEW_UV, size, size) for o in duplicates])
    coverage, degenerate_faces = uv_coverage(duplicates, NEW_UV, size)
    # Polygon edges are drawn inclusively, so abutting faces of one island share a texel row;
    # only interiors (count > 1 away from any boundary) indicate real island overlap.
    overlap_texels = int((coverage > 1).sum())
    print(f'UV layout {size}: covered {int((coverage > 0).sum())} texels, overlap(incl. shared edges) '
          f'{overlap_texels}, degenerate faces {degenerate_faces}', flush=True)

    # Bake RGB then alpha into the new layer.
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = args.bake_samples
    scene.cycles.use_denoising = False
    scene.render.dither_intensity = 0.0
    scene.render.bake.use_selected_to_active = False
    passes = {}
    for pass_name, output_socket, colorspace in (('rgb', 'Color', 'sRGB'), ('alpha', 'Alpha', 'Non-Color')):
        target = bpy.data.images.new(f'uv-unwrap bake {pass_name}', size, size, alpha=True, float_buffer=False)
        target.colorspace_settings.name = colorspace
        target.generated_color = (BACKGROUND / 255, BACKGROUND / 255, BACKGROUND / 255, 1)
        for copy, obj in zip(duplicates, originals):
            slots, info = face_materials[obj.name]
            order = sorted(info)
            materials = [build_material(f'uv-unwrap bake {pass_name} / {info[s][0].name}', *info[s][1:],
                                        emission_from=output_socket, target=target) for s in order]
            set_slots(copy, materials, np.array([order.index(s) for s in slots], dtype=np.int32))
        # Blender dilates per baked object, so a second object's margin would overwrite texels the
        # first one baked into the shared atlas. Bake one joined temporary copy instead.
        joined = []
        for copy in duplicates:
            temporary = copy.copy()
            temporary.data = copy.data.copy()
            unwrapped_collection.objects.link(temporary)
            joined.append(temporary)
        bpy.ops.object.select_all(action='DESELECT')
        for temporary in joined:
            temporary.select_set(True)
        bpy.context.view_layer.objects.active = joined[0]
        bpy.ops.object.join()
        bake_object = bpy.context.view_layer.objects.active
        bpy.ops.object.bake(type='EMIT', margin=args.bake_margin, margin_type=args.margin_type,
                            use_clear=True, target='IMAGE_TEXTURES', uv_layer=NEW_UV)
        bake_mesh = bake_object.data
        bpy.data.objects.remove(bake_object, do_unlink=True)
        bpy.data.meshes.remove(bake_mesh)
        path = output / f'bake-{pass_name}.png'
        target.filepath_raw = str(path)
        target.file_format = 'PNG'
        target.save()
        passes[pass_name] = path
    rgb = np.asarray(Image.open(passes['rgb']).convert('RGB'))
    alpha = np.asarray(Image.open(passes['alpha']).convert('L'))
    atlas_path = output / 'atlas.png'
    Image.fromarray(np.dstack([rgb, alpha])).save(atlas_path, optimize=True)
    for path in passes.values():
        path.unlink()
    atlas = bpy.data.images.load(str(atlas_path))
    atlas.name = f'{chosen_name(originals)} / unwrapped atlas'
    atlas.alpha_mode = 'STRAIGHT'
    atlas.pack()
    interpolations = {(info[s][3], info[s][4]) for _, info in face_materials.values() for s in info}
    require(len(interpolations) == 1, f'Mixed sampling across source materials: {interpolations}')
    interpolation, extension = interpolations.pop()
    final = build_material(f'{chosen_name(originals)} / unwrapped atlas', atlas, NEW_UV, interpolation, extension,
                           emission_from=None)
    final['uv_unwrap_rebake'] = True
    final['uv_unwrap_source_materials'] = sorted({info[s][0].name for _, info in face_materials.values() for s in info})
    final['source_ownership_alpha'] = 'one=observed,zero=inferred;material remains opaque'
    for copy in duplicates:
        set_slots(copy, [final], np.zeros(len(copy.data.polygons), dtype=np.int32))
        for layer in [l.name for l in copy.data.uv_layers if l.name != NEW_UV]:
            copy.data.uv_layers.remove(copy.data.uv_layers[layer])
        copy.data.uv_layers[NEW_UV].active = True
        copy.data.uv_layers[NEW_UV].active_render = True
    new_islands = uv_islands([o.data for o in duplicates], NEW_UV)
    source_islands = sum(uv_islands([o.data], layer) for o in originals
                         for layer in {i[2] for i in face_materials[o.name][1].values()})

    # Validation renders from the frozen review cameras.
    views_path = (args.views or find_views(asset_id)).resolve(strict=True)
    views = json.loads(views_path.read_text())
    require(views['asset_id'] == asset_id and len(views['views']) == 8, f'Unexpected review packet {views_path}')
    unknown = set(views['object_names']) ^ set(names)
    if unknown:
        print(f'WARNING: review packet objects differ from rebaked meshes: {sorted(unknown)}', flush=True)
    width, height = views['tile_size']
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.cycles.samples = args.render_samples
    scene.world = None
    cameras = []
    for record in views['views']:
        data = bpy.data.cameras.new('UV unwrap review camera')
        data.type = 'ORTHO'
        data.clip_end = 100000
        data.ortho_scale = record['ortho_scale']
        camera = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(camera)
        if 'camera_location' in record:
            camera.location = record['camera_location']
            camera.rotation_euler = record['camera_rotation_euler']
        else:
            camera.matrix_world = Matrix(record['camera_matrix_world'])
        cameras.append(camera)
    bpy.context.view_layer.update()
    original_renders = render_views(scene, cameras, output / 'renders/original', originals, duplicates)
    unwrapped_renders = render_views(scene, cameras, output / 'renders/unwrapped', duplicates, originals)
    differences = compare(original_renders, unwrapped_renders, output / 'compare-sheet.png')

    # Texture memory before/after and the atlas comparison image.
    before_images = [image_record(image) for image in source_images.values()]
    textures = {
        'before': {'count': len(before_images), 'images': before_images,
                   'pixels': sum(i['pixels'] for i in before_images),
                   'rgba8_bytes': sum(i['rgba8_bytes'] for i in before_images),
                   'rgba8_mipmapped_bytes': sum(i['rgba8_mipmapped_bytes'] for i in before_images),
                   'png_bytes': sum(i['png_bytes'] or 0 for i in before_images)},
        'after': {'count': 1, 'size': [size, size], 'pixels': size * size, 'rgba8_bytes': size * size * 4,
                  'rgba8_mipmapped_bytes': round(size * size * 4 * 4 / 3), 'png_bytes': atlas_path.stat().st_size,
                  'path': str(atlas_path), 'sha256': sha(atlas_path)}}
    new_charts = []
    for copy in duplicates:
        uv = copy.data.uv_layers[NEW_UV].uv
        new_charts.extend([tuple(uv[i].vector) for i in poly.loop_indices] for poly in copy.data.polygons)
    atlas_sheet([{'array': image_array(image), 'charts': charts[name]} for name, image in source_images.items()],
                np.asarray(Image.open(atlas_path).convert('RGBA')), new_charts, textures,
                output / 'atlas-comparison.png')

    # Keep only the unwrapped asset: drop originals, cameras and bake materials, then export.
    for camera in cameras:
        bpy.data.objects.remove(camera, do_unlink=True)
    for obj in list(loaded.values()):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(originals_collection)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    for copy, name in zip(duplicates, names):
        copy.name = name
        copy.data.name = name + ' / unwrapped'
        copy['uv_unwrap_rebake_source_sha256'] = source_sha
    remaining = sorted(i.name for i in bpy.data.images if i.type != 'RENDER_RESULT')
    require(remaining == [atlas.name], f'Unexpected images kept in the output: {remaining}')
    from export_editor import export_editor
    glb_dir = output / 'glb'
    glb_dir.mkdir()
    export = export_editor(map_name, glb_dir / 'model.glb', asset_id)
    scene.render.engine = 'CYCLES'
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'model.blend'), compress=True, copy=True)

    report = {
        'version': 1, 'kind': 'uv-unwrap-rebake-comparison',
        'status': 'comparison-only; nothing published, no workspace/stage/library file changed',
        'asset_id': asset_id, 'map': map_name,
        'source': {'blend': str(source), 'sha256': source_sha, 'objects': per_object,
                   'faces': int(len(area)), 'uv_islands': source_islands},
        'views': {'path': str(views_path), 'sha256': sha(views_path), 'tile_size': [width, height]},
        'unwrap': {'uv_layer': NEW_UV, 'angle_limit_degrees': args.angle_limit, 'island_margin': args.island_margin,
                   'area_weight': 1.0, 'correct_aspect': True, 'scale_to_bounds': False,
                   'relax': args.relax,
                   'pack': {'rotate': True, 'rotate_method': 'ANY', 'shape_method': 'CONCAVE',
                            'margin_method': 'FRACTION', 'margin': pack_margin,
                            'margin_texels': pack_margin * size, 'history': pack_history},
                   'uv_islands': new_islands, 'uv_utilization': pack_history[-1]['uv_utilization']},
        'atlas_size': {'size': size, 'rounding': args.rounding, 'required_size': required,
                       'capped': capped, 'max_size': args.max_size,
                       'rule': 'smallest size whose area-weighted median density >= source area-weighted median'},
        'density_texels_per_world_unit': {
            'before': before_density, 'after': after_density,
            'surface_fraction_below_source': float(new_area[below].sum() / new_area.sum()),
            'faces_below_source': int(below.sum()),
            'atlas_texels_covered': int((coverage > 0).sum()),
            'atlas_texels_multiply_covered_incl_shared_edges': overlap_texels,
            'degenerate_uv_faces': degenerate_faces,
            'min_axis': {'before': stats(source_axes[:, 0], area), 'after': stats(new_axes[:, 0], new_area)},
            'max_axis': {'before': stats(source_axes[:, 1], area), 'after': stats(new_axes[:, 1], new_area)},
            'surface_fraction_min_axis_below_source': float(
                new_area[new_axes[:, 0] < source_axes[:, 0] - 1e-9].sum() / new_area.sum()),
            'anisotropy_after_max': float((new_axes[:, 1] / np.maximum(new_axes[:, 0], 1e-12)).max()),
            'definition': 'sqrt(texel area / world area) per face; min/max_axis are the principal '
                          'stretch values of the UV map (texels per world unit = map pixel)'},
        'bake': {'engine': 'CYCLES', 'device': 'CPU', 'type': 'EMIT', 'samples': args.bake_samples,
                 'margin': args.bake_margin, 'margin_type': args.margin_type,
                 'passes': 'rgb (sRGB) from image Color; alpha (Non-Color) from image Alpha; combined RGBA',
                 'source_sampling': {'interpolation': interpolation, 'extension': extension},
                 'method': 'Bake on duplicates: each used material reduced to UV Map(original layer) -> '
                           'image -> emission, target image active; originals untouched.'},
        'validation': {'render': {'engine': 'CYCLES', 'samples': args.render_samples, 'shading': 'emission only',
                                  'view_transform': 'Standard', 'film_transparent': True},
                       'differences': differences,
                       'renders': {'original': [str(p) for p in original_renders],
                                   'unwrapped': [str(p) for p in unwrapped_renders]}},
        'textures': textures,
        'outputs': {'blend': str(output / 'model.blend'), 'glb': glb_summary(glb_dir / 'model.glb'),
                    'asset_json': str(glb_dir / 'asset.json'), 'atlas': str(atlas_path),
                    'compare_sheet': str(output / 'compare-sheet.png'),
                    'atlas_comparison': str(output / 'atlas-comparison.png'),
                    'export_report': {k: v for k, v in export.items() if k != 'asset'}},
    }
    if args.reference_glb:
        report['reference_glb'] = glb_summary(args.reference_glb.resolve(strict=True))
    report['outputs']['blend_sha256'] = sha(output / 'model.blend')
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'size': size, 'capped': capped,
                      'differences': differences['overall']}, indent=2), flush=True)


def chosen_name(objects):
    names = {o.get('asset_name') for o in objects}
    require(len(names) == 1 and None not in names, f'Objects must share one asset_name: {names}')
    return names.pop()


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1:])
