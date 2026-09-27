"""Reproject Main Hall's revealed shell without changing covered resources.

Uses the revealed game image, native shell masks, and neighboring keep geometry
for first-hit visibility. Unobserved neutral faces receive inferred masonry
from a recorded source swatch. Existing colored texels, UVs and geometry remain.
"""
import argparse
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, distance_transform_edt, label

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'refinement/blender'))
from lossy_assets import read_glb, accessor_array, node_matrix


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raster(q, shape):
    low = np.maximum(np.floor(q.min(0)).astype(int), 0)
    high = np.minimum(np.ceil(q.max(0)).astype(int), np.array(shape[::-1]) - 1)
    basis = np.c_[q[1] - q[0], q[2] - q[0]]
    if np.any(high < low) or abs(np.linalg.det(basis)) < 1e-9:
        return None
    yy, xx = np.mgrid[low[1]:high[1] + 1, low[0]:high[0] + 1]
    v = (np.stack([xx + .5, yy + .5], -1) - q[0]) @ np.linalg.inv(basis).T
    weights = np.concatenate([1 - v.sum(-1, keepdims=True), v], -1)
    inside = np.all(weights >= -1e-7, axis=-1)
    return xx[inside], yy[inside], weights[inside]


def primitives(folder, doc, buffers):
    origin = np.array(json.loads((folder / 'asset.json').read_text())['source_origin_scene'])
    parents = {ch: i for i, n in enumerate(doc['nodes']) for ch in n.get('children', [])}
    def world(i):
        n = doc['nodes'][i]
        matrix = np.eye(4) if n.get('name') == 'map' else node_matrix(n)
        return world(parents[i]) @ matrix if i in parents else matrix
    for ni, node in enumerate(doc['nodes']):
        extra = node.get('extras', {})
        if 'mesh' not in node or extra.get('reveal_hide_when_applied') or extra.get('reveal_material_state') == 'covered':
            continue
        for primitive in doc['meshes'][node['mesh']]['primitives']:
            pos = accessor_array(doc, buffers, primitive['attributes']['POSITION'])
            pos = (np.c_[pos, np.ones(len(pos))] @ world(ni).T)[:, :3] + origin
            indices = (accessor_array(doc, buffers, primitive['indices']) if 'indices' in primitive else np.arange(len(pos))).reshape(-1, 3)
            uv = accessor_array(doc, buffers, primitive['attributes']['TEXCOORD_0'])
            yield ni, primitive, pos, indices, uv


def repair(library, reference, masks, output):
    aid = 'derby-keep-main-hall'
    folder = library / aid
    doc, buffers, raw = read_glb(folder / 'model.glb')
    if any('revealed_shell_repair' in m.get('extras', {}) for m in doc['materials']):
        raise ValueError('Use the pristine Main Hall model from the publication backup')
    before = copy.deepcopy(doc)
    source = np.array(Image.open(reference / 'revealed.png').convert('RGB'))
    h, w = source.shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    manifest = json.loads((masks / 'manifest.json').read_text())['masks']
    # Revealed keep shell and lower facade masks, separate from the room artwork.
    for index in (172, 174):
        entry = next(m for m in manifest if m['index'] == index)
        x, y = entry['box_top_left']; mw, mh = entry['box_size']
        mask[y:y + mh, x:x + mw] |= np.array(Image.open(masks / entry['png'])) > 0
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    def project(pos):
        return np.c_[pos[:, 0], -pos[:, 1] * sine - pos[:, 2] * cosine]
    def depths(pos):
        return -pos[:, 1] * cosine + pos[:, 2] * sine
    depth = np.full((h, w), -np.inf)
    owners = np.full((h, w), -1, dtype=int)
    items = list(primitives(folder, doc, buffers))
    all_items = list(items)
    inputs = {str(folder / 'model.glb'): sha(folder / 'model.glb'), str(folder / 'asset.json'): sha(folder / 'asset.json'),
              str(reference / 'revealed.png'): sha(reference / 'revealed.png'), str(masks / 'manifest.json'): sha(masks / 'manifest.json')}
    for index in (172, 174):
        path = masks / next(m for m in manifest if m['index'] == index)['png']; inputs[str(path)] = sha(path)
    scene_path = library.parent.parent / 'scenes/derby.rhlos-map.json'
    scene = json.loads(scene_path.read_text())
    inputs[str(scene_path)] = sha(scene_path)
    for name in sorted({ref['id'] for ref in scene['assetSources']} - {aid}):
        path = library / name
        odoc, obuffers, _ = read_glb(path / 'model.glb')
        all_items.extend(primitives(path, odoc, obuffers))
        for filename in ('model.glb', 'asset.json'):
            inputs[str(path / filename)] = sha(path / filename)
    for pi, (_, _, pos, indices, _) in enumerate(all_items):
        screen, z = project(pos), depths(pos)
        if screen[:, 0].max() < 580 or screen[:, 0].min() > 1200 or screen[:, 1].max() < 350 or screen[:, 1].min() > 1400:
            continue
        for tri in indices:
            hit = raster(screen[tri], (h, w))
            if hit is None:
                continue
            x, y, bary = hit; value = bary @ z[tri]
            take = value > depth[y, x]
            depth[y[take], x[take]] = value[take]; owners[y[take], x[take]] = pi
    binary = bytearray(buffers[0])
    reports = []
    # A small unadorned front masonry area; used only as an inferred fallback.
    swatch_box = [650, 1050, 680, 1100]
    tile = source[1050:1100, 650:680]
    for pi, (ni, primitive, pos, indices, uv) in enumerate(items):
        node = doc['nodes'][ni]
        existing_revealed = node.get('extras', {}).get('reveal_material_state') == 'revealed'
        if not doc['materials'][primitive['material']].get('extras', {}).get('source_ownership_label', '').startswith('interior-patch-000'):
            continue
        material = copy.deepcopy(doc['materials'][primitive['material']])
        texture = copy.deepcopy(doc['textures'][material['pbrMetallicRoughness']['baseColorTexture']['index']])
        image = copy.deepcopy(doc['images'][texture['source']])
        view = doc['bufferViews'][image['bufferView']]; offset = view.get('byteOffset', 0)
        pixels = np.array(Image.open(io.BytesIO(buffers[0][offset:offset + view['byteLength']])).convert('RGBA'))
        original = pixels.copy(); ih, iw = pixels.shape[:2]
        wooden = any(word in node['name'] for word in ('Banquet', 'support post', 'galleries / segment 01'))
        swatch_box = [653, 867, 671, 879] if wooden else [650, 1050, 680, 1100]
        x0, y0, x1, y1 = swatch_box; tile = source[y0:y1, x0:x1]
        neutral = (pixels[..., 0] == pixels[..., 1]) & (pixels[..., 1] == pixels[..., 2]) & (pixels[..., 0] >= 40) & (pixels[..., 0] <= 83)
        regions, _ = label(neutral); neutral &= np.bincount(regions.ravel())[regions] >= 64
        used = np.zeros((ih, iw), dtype=bool); changed = np.zeros_like(used); observed = np.zeros_like(used)
        for tri in indices:
            hit = raster(uv[tri] * [iw, ih], (ih, iw))
            if hit is None:
                continue
            x, y, bary = hit; used[y, x] = True
            take = neutral[y, x]; x, y, bary = x[take], y[take], bary[take]
            if not len(x):
                continue
            points = bary @ pos[tri]; screen = project(points)
            sx = np.clip(screen[:, 0].astype(int), 0, w - 1); sy = np.clip(screen[:, 1].astype(int), 0, h - 1)
            visible = (owners[sy, sx] == pi) & (np.abs(depths(points) - depth[sy, sx]) < 3) & mask[sy, sx]
            normal = np.cross(pos[tri[1]] - pos[tri[0]], pos[tri[2]] - pos[tri[0]])
            horizontal = 0 if abs(normal[1]) >= abs(normal[0]) else 1
            tx = np.floor(points[:, horizontal]).astype(int) % tile.shape[1]
            tile_v = points[:, 1] if abs(normal[2]) > max(abs(normal[0]), abs(normal[1])) else -points[:, 2] * cosine
            ty = np.floor(tile_v).astype(int) % tile.shape[0]
            pixels[y, x, :3] = np.clip(tile[ty, tx] * .65, 0, 255).astype(np.uint8)
            pixels[y[visible], x[visible], :3] = source[sy[visible], sx[visible]]
            observed[y[visible], x[visible]] = True; changed[y, x] = True
        if not changed.any():
            continue
        pad = binary_dilation(changed, iterations=3) & ~used & neutral
        nearest = distance_transform_edt(~changed, return_distances=False, return_indices=True)
        pixels[pad] = pixels[nearest[0][pad], nearest[1][pad]]
        assert np.array_equal(pixels[~neutral], original[~neutral])
        assert np.array_equal(pixels[..., 3], original[..., 3])
        data = io.BytesIO(); Image.fromarray(pixels).save(data, format='PNG')
        binary.extend(b'\0' * (-len(binary) % 4))
        image['bufferView'] = len(doc['bufferViews'])
        doc['bufferViews'].append(dict(buffer=0, byteOffset=len(binary), byteLength=len(data.getvalue())))
        binary.extend(data.getvalue())
        texture['source'] = len(doc['images']); doc['images'].append(image)
        material['pbrMetallicRoughness']['baseColorTexture']['index'] = len(doc['textures']); doc['textures'].append(texture)
        material['extras']['revealed_shell_repair'] = dict(source_sha256=sha(reference / 'revealed.png'), masks=[172, 174],
                                                          inferred_swatch=swatch_box, method='first-hit source reprojection; tiled masonry only for unobserved neutral regions')
        if not existing_revealed:
            # Shared shell nodes retain their exact covered mesh/material.
            clone = copy.deepcopy(node); mesh = copy.deepcopy(doc['meshes'][node['mesh']])
            assert len(mesh['primitives']) == 1
            clone['name'] += ' / texture-repaired revealed'
            clone['extras']['reveal_show_when_applied'] = ['appearance-1']
            node['extras']['reveal_hide_when_applied'] = ['appearance-1']
            clone['mesh'] = len(doc['meshes']); doc['meshes'].append(mesh)
            parent = next(n for n in doc['nodes'] if ni in n.get('children', []))
            parent['children'].append(len(doc['nodes'])); doc['nodes'].append(clone)
            primitive = mesh['primitives'][0]
        primitive['material'] = len(doc['materials']); doc['materials'].append(material)
        reports.append(dict(material=material['name'], observed_texels=int(observed.sum()), inferred_texels=int((changed & ~observed).sum()),
                            padding_texels=int(pad.sum()), remaining_used_neutral=int((neutral & used & ~changed).sum())))
    if len(reports) < 4:
        raise ValueError('Expected the four shell materials and any remaining interior placeholders')
    assert doc['accessors'] == before['accessors']
    assert doc['materials'][:len(before['materials'])] == before['materials']
    assert doc['images'][:len(before['images'])] == before['images']
    assert binary[:len(buffers[0])] == buffers[0]
    # The superseded reveal-only material has no users. Omit it so derivative
    # builders do not treat its legacy texture as a missing bake receiver.
    used_materials = sorted({p['material'] for m in doc['meshes'] for p in m['primitives']})
    remap = {old: new for new, old in enumerate(used_materials)}
    doc['materials'] = [doc['materials'][old] for old in used_materials]
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            primitive['material'] = remap[primitive['material']]
    binary.extend(b'\0' * (-len(binary) % 4)); doc['buffers'][0]['byteLength'] = len(binary)
    js = json.dumps(doc, separators=(',', ':')).encode(); js += b' ' * (-len(js) % 4)
    result = struct.pack('<4sII', b'glTF', 2, 28 + len(js) + len(binary)) + struct.pack('<II', len(js), 0x4e4f534a) + js + struct.pack('<II', len(binary), 0x004e4942) + binary
    output.mkdir(parents=True, exist_ok=False); dst = output / aid; dst.mkdir()
    (dst / 'model.glb').write_bytes(result); (dst / 'asset.json').write_bytes((folder / 'asset.json').read_bytes())
    report = dict(inputs=inputs, outputs={aid:dict(model_sha256=sha(dst / 'model.glb'), descriptor_sha256=sha(dst / 'asset.json'))},
                  covered_resources_unchanged=True, nonneutral_texels_unchanged=True, geometry_and_uvs_unchanged=True, materials=reports)
    (output / 'integration.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('library', 'reference', 'masks', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = repair(*(getattr(args, name).resolve() for name in ('library', 'reference', 'masks', 'output')))
    print(json.dumps(result['materials'], indent=2))
