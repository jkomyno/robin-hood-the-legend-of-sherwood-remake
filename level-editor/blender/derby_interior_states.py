"""Restore Derby room appearances while preserving the covered GLB payloads.

Requires numpy, Pillow, scipy and shapely >= 2.1. Run with Python, not Blender:
  python derby_interior_states.py <library/3d-assets/derby> <reference> <output>

The reference directory contains layers.json, patch alpha masks and revealed.png.
Only named facade components are cut. Room artwork is baked onto first-hit
surfaces inside the patch alpha; connected neutral placeholders receive a
source-swatch fallback with inferred ownership. Map/scene publication is separate.
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
from scipy.ndimage import label
from shapely import LineString, Point, Polygon, box, union_all, constrained_delaunay_triangles

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'refinement/blender'))
from lossy_assets import read_glb, accessor_array, node_matrix

SPECS = {'derby-keep-west-tower': ('patch-001', [132]), 'derby-east-hall': ('patch-002', [183, 185, 188, 189, 191, 192, 211, 212]), 'derby-upper-gatehouse': ('patch-003', [])}

def cut_weights(projected, mask):
    """Barycentric triangles outside a source-camera cutaway, preserving winding.

    Edge-on walls still need cutting: their 2D projection is a line, but they
    have area in 3D and become visible when the editor camera rotates.
    """
    basis = np.c_[projected[1] - projected[0], projected[2] - projected[0]]
    determinant = np.linalg.det(basis)
    if abs(determinant) < 1e-8:
        pairs = [(a, b) for a in range(3) for b in range(a + 1, 3)]
        a, b = max(pairs, key=lambda pair: np.linalg.norm(projected[pair[1]] - projected[pair[0]]))
        delta = projected[b] - projected[a]
        squared = delta @ delta
        if squared < 1e-12:
            return [] if mask.covers(Point(projected[0])) else [np.eye(3)]
        values = (projected - projected[a]) @ delta / squared
        remaining = LineString([projected[a], projected[b]]).difference(mask)
        lines = list(remaining.geoms) if hasattr(remaining, 'geoms') else [remaining]
        output = []
        for line in lines:
            if line.is_empty or line.geom_type != 'LineString':
                continue
            interval = (np.asarray(line.coords) - projected[a]) @ delta / squared
            polygon = list(np.eye(3))
            for boundary, sign in [(interval.min(), 1), (interval.max(), -1)]:
                clipped = []
                for first, second in zip(polygon, polygon[1:] + polygon[:1]):
                    fa, fb = first @ values, second @ values
                    inside_a = sign * (fa - boundary) >= 0
                    inside_b = sign * (fb - boundary) >= 0
                    if inside_a:
                        clipped.append(first)
                    if inside_a != inside_b:
                        clipped.append(first + (second - first) * (boundary - fa) / (fb - fa))
                polygon = clipped
            output.extend(np.array([polygon[0], polygon[i], polygon[i + 1]])
                          for i in range(1, len(polygon) - 1))
        return output
    polygon = Polygon(projected)
    if not polygon.intersects(mask):
        return [np.eye(3)]
    remaining = polygon.difference(mask)
    inverse = np.linalg.inv(basis)
    result = []
    for face in constrained_delaunay_triangles(remaining).geoms:
        coords = np.array(face.exterior.coords)[:3]
        uv = (coords - projected[0]) @ inverse.T
        barycentric = np.c_[1 - uv.sum(1), uv]
        if np.linalg.det(np.c_[coords[1] - coords[0], coords[2] - coords[0]]) * determinant < 0:
            barycentric = barycentric[[0, 2, 1]]
        result.append(barycentric)
    return result

def cut_assets(source_directory, REF, OUT):
    """Append reveal-only cut meshes; retain all covered accessors and materials."""
    manifest = json.loads((REF / 'layers.json').read_text())
    s, c = (math.sin(math.radians(35)), math.cos(math.radians(35)))
    jobs = []
    report = {}
    for aid, (patch, cut_ids) in SPECS.items():
        src = source_directory / aid
        dst = OUT / aid
        dst.mkdir(exist_ok=True)
        desc = json.loads((src / 'asset.json').read_text())
        doc, buffers, _ = read_glb(src / 'model.glb')
        assert len(buffers) == 1
        binary = bytearray(buffers[0])
        original_nodes = len(doc['nodes'])
        origin = np.array(desc['source_origin_scene'])
        parents = {ch: i for i, n in enumerate(doc['nodes']) for ch in n.get('children', [])}

        def accessor(array, kind):
            a = np.asarray(array, dtype='<f4')
            binary.extend(b'\x00' * (-len(binary) % 4))
            offset = len(binary)
            binary.extend(a.tobytes())
            vi = len(doc['bufferViews'])
            doc['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': a.nbytes})
            ai = len(doc['accessors'])
            d = {'bufferView': vi, 'componentType': 5126, 'count': len(a), 'type': kind}
            if kind == 'VEC3':
                d.update(min=a.min(0).tolist(), max=a.max(0).tolist())
            doc['accessors'].append(d)
            return ai

        def transform(i):
            n = doc['nodes'][i]
            m = np.eye(4) if n.get('name') == 'map' else node_matrix(n)
            return transform(parents[i]) @ m if i in parents else m
        r = next((p for p in manifest['patches'] if p['id'] == patch))
        x, y, w, h = r['graphic']['bbox']
        alpha = np.array(Image.open(REF / r['graphic']['alpha'])) > 127
        rects = []
        for row in range(h):
            edge = np.diff(np.r_[False, alpha[row], False].astype(int))
            for a, b in zip(np.where(edge == 1)[0], np.where(edge == -1)[0]):
                rects.append(box(x + int(a), y + row, x + int(b), y + row + 1))
        mask = union_all(rects).simplify(0.5, preserve_topology=True)
        changes = []
        for i in range(original_nodes):
            node = doc['nodes'][i]
            e = node.get('extras', {})
            source = e.get('source_node')
            comp = e.get('projection_component')
            if aid == 'derby-upper-gatehouse' and comp in ['upper-chamber-removable-cover', 'upper-chamber-west-removable-cover']:
                e['reveal_hide_when_applied'] = ['appearance-1']
                changes.append({'node': node['name'], 'action': 'hide cover'})
                continue
            if 'mesh' not in node or source not in [f'building-{n:03d}' for n in cut_ids]:
                continue
            matrix = transform(i)
            new_prims = []
            before = after = 0
            for prim in doc['meshes'][node['mesh']]['primitives']:
                attrs = {k: accessor_array(doc, buffers, v, True) for k, v in prim['attributes'].items()}
                p = attrs['POSITION']
                world = (np.c_[p, np.ones(len(p))] @ matrix.T)[:, :3] + origin
                q = np.c_[world[:, 0], -world[:, 1] * s - world[:, 2] * c]
                indices = accessor_array(doc, buffers, prim['indices']) if 'indices' in prim else np.arange(len(p))
                output = {k: [] for k in attrs}
                for tri in indices.reshape(-1, 3):
                    before += 1
                    projected = q[tri]
                    for bary in cut_weights(projected, mask):
                        for k, v in attrs.items():
                            output[k].extend(bary @ v[tri])
                        after += 1
                if not output['POSITION']:
                    continue
                np_ = copy.deepcopy(prim)
                np_.pop('indices', None)
                np_['attributes'] = {k: accessor(v, 'VEC' + str(np.asarray(v).shape[1])) for k, v in output.items()}
                new_prims.append(np_)
            e['reveal_hide_when_applied'] = ['appearance-1']
            if new_prims:
                replacement = copy.deepcopy(node)
                replacement['name'] += ' / revealed opening'
                replacement['extras'].pop('reveal_hide_when_applied')
                replacement['extras']['reveal_show_when_applied'] = ['appearance-1']
                replacement['mesh'] = len(doc['meshes'])
                doc['meshes'].append({'name': replacement['name'], 'primitives': new_prims})
                doc['nodes'][parents[i]]['children'].append(len(doc['nodes']))
                doc['nodes'].append(replacement)
            changes.append({'node': node['name'], 'action': 'partial cutaway', 'before': before, 'after': after})
        if len(changes) != (len(cut_ids) if cut_ids else 2):
            raise ValueError('Facade inventory changed: ' + aid)
        binary.extend(b'\x00' * (-len(binary) % 4))
        doc['buffers'][0]['byteLength'] = len(binary)
        js = json.dumps(doc, separators=(',', ':')).encode()
        js += b' ' * (-len(js) % 4)
        data = struct.pack('<4sII', b'glTF', 2, 28 + len(js) + len(binary)) + struct.pack('<II', len(js), 1313821514) + js + struct.pack('<II', len(binary), 5130562) + binary
        (dst / 'model.glb').write_bytes(data)
        (dst / 'asset.json').write_text(json.dumps(desc, indent=2) + '\n')
        report[aid] = changes
        jobs.append({'name': aid, 'origin': origin.tolist(), 'patch': 'appearance-1', 'bbox': [x, y, w, h]})
        print(aid, len(changes), flush=True)
    (OUT / 'report.json').write_text(json.dumps(report, indent=2))
    return jobs

def raster(q, shape):
    low = np.maximum(np.floor(q.min(0)).astype(int), 0)
    high = np.minimum(np.ceil(q.max(0)).astype(int), np.array(shape[::-1]) - 1)
    if np.any(high < low):
        return None
    basis = np.c_[q[1] - q[0], q[2] - q[0]]
    if abs(np.linalg.det(basis)) < 1e-09:
        return None
    yy, xx = np.mgrid[low[1]:high[1] + 1, low[0]:high[0] + 1]
    v = (np.stack([xx + 0.5, yy + 0.5], -1) - q[0]) @ np.linalg.inv(basis).T
    bary = np.concatenate([1 - v.sum(-1, keepdims=True), v], -1)
    inside = np.all(bary >= -1e-07, axis=-1)
    return (xx[inside], yy[inside], bary[inside])

def bake_assets(REF, OUT):
    """Bake source-visible texels and label unobserved fallback texels separately."""
    manifest = json.loads((REF / 'layers.json').read_text())
    source = np.array(Image.open(REF / 'revealed.png').convert('RGB'))
    height, width = source.shape[:2]
    s, c = (math.sin(math.radians(35)), math.cos(math.radians(35)))
    report = {}
    for aid, patch in [('derby-keep-west-tower', 'patch-001'), ('derby-east-hall', 'patch-002'), ('derby-upper-gatehouse', 'patch-003')]:
        folder = OUT / aid
        doc, buffers, _ = read_glb(folder / 'model.glb')
        binary = bytearray(buffers[0])
        desc = json.loads((folder / 'asset.json').read_text())
        origin = np.array(desc['source_origin_scene'])
        parents = {ch: i for i, n in enumerate(doc['nodes']) for ch in n.get('children', [])}

        def transform(i):
            n = doc['nodes'][i]
            m = np.eye(4) if n.get('name') == 'map' else node_matrix(n)
            return transform(parents[i]) @ m if i in parents else m

        def blob(data):
            binary.extend(b'\x00' * (-len(binary) % 4))
            vi = len(doc['bufferViews'])
            doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(data)})
            binary.extend(data)
            return vi
        prims = []
        depth = np.full((height, width), -np.inf)
        owners = np.full((height, width), -1, dtype=np.int32)
        for ni, n in enumerate(doc['nodes']):
            if 'mesh' not in n or n.get('extras', {}).get('reveal_hide_when_applied'):
                continue
            matrix = transform(ni)
            for pi, prim in enumerate(doc['meshes'][n['mesh']]['primitives']):
                p = accessor_array(doc, buffers, prim['attributes']['POSITION'], True)
                world = (np.c_[p, np.ones(len(p))] @ matrix.T)[:, :3] + origin
                q = np.c_[world[:, 0], -world[:, 1] * s - world[:, 2] * c]
                d = -world[:, 1] * c + world[:, 2] * s
                idx = accessor_array(doc, buffers, prim['indices']) if 'indices' in prim else np.arange(len(p))
                idx = idx.reshape(-1, 3)
                key = len(prims)
                prims.append((ni, pi, prim, q, d, idx))
                for tri in idx:
                    hit = raster(q[tri], depth.shape)
                    if hit is None:
                        continue
                    xx, yy, bary = hit
                    z = bary @ d[tri]
                    ok = z > depth[yy, xx]
                    depth[yy[ok], xx[ok]] = z[ok]
                    owners[yy[ok], xx[ok]] = key
        r = next((r for r in manifest['patches'] if r['id'] == patch))
        x, y, w, h = r['graphic']['bbox']
        mask = np.zeros((height, width), bool)
        mask[y:y + h, x:x + w] = np.array(Image.open(REF / r['graphic']['alpha'])) > 127
        copies = {}
        counts = []
        for key, (ni, pi, prim, q, d, idx) in enumerate(prims):
            if doc['nodes'][ni].get('extras', {}).get('source_node') == 'building-267':
                continue
            if not np.any((owners == key) & mask) and (not doc['nodes'][ni].get('extras', {}).get('reveal_show_when_applied')):
                continue
            material = doc['materials'][prim['material']]
            tex = material.get('pbrMetallicRoughness', {}).get('baseColorTexture')
            if tex is None:
                continue
            texture = doc['textures'][tex['index']]
            imdesc = doc['images'][texture['source']]
            view = doc['bufferViews'][imdesc['bufferView']]
            offset = view.get('byteOffset', 0)
            im = Image.open(io.BytesIO(buffers[view.get('buffer', 0)][offset:offset + view['byteLength']])).convert('RGBA')
            pixels = np.array(im)
            ih, iw = pixels.shape[:2]
            uv = accessor_array(doc, buffers, prim['attributes']['TEXCOORD_' + str(tex.get('texCoord', 0))], True)
            changed = np.zeros((ih, iw), bool)
            filled = np.zeros((ih, iw), bool)
            gray = (pixels[:, :, 0] == pixels[:, :, 1]) & (pixels[:, :, 1] == pixels[:, :, 2]) & (pixels[:, :, 0] >= 40) & (pixels[:, :, 0] <= 83)
            regions, num = label(gray)
            sizes = np.bincount(regions.ravel())
            gray &= sizes[regions] >= 64
            nodeid = doc['nodes'][ni].get('extras', {}).get('source_node')
            swatch = (1490, 989, 1506, 1007)
            if nodeid in ['building-186', 'building-193', 'building-241', 'building-242', 'building-243', 'building-245', 'building-246', 'building-247', 'building-248', 'building-249', 'building-265', 'building-266']:
                swatch = (1290, 1108, 1320, 1120)
            if nodeid == 'building-244':
                swatch = (1390, 1129, 1402, 1137)
            donor = source[swatch[1]:swatch[3], swatch[0]:swatch[2]]
            for tri in idx:
                hit = raster(uv[tri] * [iw, ih], (ih, iw))
                if hit is None:
                    continue
                xx, yy, bary = hit
                neutral = gray[yy, xx]
                tone = pixels[yy, xx, 0] / 64
                tile = donor[yy % len(donor), xx % donor.shape[1]]
                pixels[yy[neutral], xx[neutral], :3] = np.clip(tile[neutral] * tone[neutral, None], 0, 255).astype(np.uint8)
                pixels[yy[neutral], xx[neutral], 3] = 0
                filled[yy[neutral], xx[neutral]] = True
                projected = bary @ q[tri]
                sx = np.clip(projected[:, 0].astype(int), 0, width - 1)
                sy = np.clip(projected[:, 1].astype(int), 0, height - 1)
                z = bary @ d[tri]
                ok = mask[sy, sx] & (np.abs(depth[sy, sx] - z) < 3) & (owners[sy, sx] == key)
                pixels[yy[ok], xx[ok], :3] = source[sy[ok], sx[ok]]
                pixels[yy[ok], xx[ok], 3] = 255
                changed[yy[ok], xx[ok]] = True
            count = int(changed.sum())
            if not count and (not filled.any()):
                continue
            stream = io.BytesIO()
            Image.fromarray(pixels).save(stream, format='PNG')
            newimage = len(doc['images'])
            doc['images'].append({'bufferView': blob(stream.getvalue()), 'mimeType': 'image/png', 'name': aid + ' ' + patch + ' revealed'})
            newtexture = copy.deepcopy(texture)
            newtexture['source'] = newimage
            ti = len(doc['textures'])
            doc['textures'].append(newtexture)
            newmat = copy.deepcopy(material)
            newmat['name'] += ' / ' + patch + ' revealed'
            newmat.setdefault('extras', {})['source_ownership_alpha'] = 'one=observed,zero=inferred;material remains opaque'
            newmat['extras']['interior_unseen_fill'] = 'tiled source swatch on connected neutral placeholders'
            newmat['extras']['interior_unseen_swatch'] = swatch
            newmat['pbrMetallicRoughness']['baseColorTexture']['index'] = ti
            mi = len(doc['materials'])
            doc['materials'].append(newmat)
            if ni not in copies:
                node = doc['nodes'][ni]
                mesh = copy.deepcopy(doc['meshes'][node['mesh']])
                meshindex = len(doc['meshes'])
                doc['meshes'].append(mesh)
                if not node.get('extras', {}).get('reveal_show_when_applied'):
                    replica = copy.deepcopy(node)
                    replica['name'] += ' / revealed material'
                    replica.setdefault('extras', {})['reveal_show_when_applied'] = ['appearance-1']
                    node.setdefault('extras', {})['reveal_hide_when_applied'] = ['appearance-1']
                    replica['mesh'] = meshindex
                    doc['nodes'][parents[ni]]['children'].append(len(doc['nodes']))
                    doc['nodes'].append(replica)
                else:
                    node['mesh'] = meshindex
                copies[ni] = mesh
            copies[ni]['primitives'][pi]['material'] = mi
            counts.append({'node': doc['nodes'][ni]['name'], 'texels': count, 'inferred_texels': int((filled & ~changed).sum())})
        binary.extend(b'\x00' * (-len(binary) % 4))
        doc['buffers'][0]['byteLength'] = len(binary)
        js = json.dumps(doc, separators=(',', ':')).encode()
        js += b' ' * (-len(js) % 4)
        (folder / 'model.glb').write_bytes(struct.pack('<4sII', b'glTF', 2, 28 + len(js) + len(binary)) + struct.pack('<II', len(js), 1313821514) + js + struct.pack('<II', len(binary), 5130562) + binary)
        report[aid] = counts
        print(aid, len(counts), sum((x['texels'] for x in counts)), flush=True)
    (OUT / 'bake-report.json').write_text(json.dumps(report, indent=2))
    return report


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(source, reference, output):
    source, reference, output = map(lambda p: Path(p).resolve(), (source, reference, output))
    output.mkdir(parents=True, exist_ok=False)
    inputs = {}
    for asset in SPECS:
        for name in ('model.glb', 'asset.json'):
            path = source / asset / name
            inputs[str(path)] = sha(path)
        document, _, _ = read_glb(source / asset / 'model.glb')
        if any(any(key.startswith('reveal_') for key in node.get('extras', {}))
               for node in document['nodes']):
            raise ValueError('Asset already contains reveal states: ' + asset)
    for name in ('layers.json', 'revealed.png', 'patch-001-alpha.png',
                 'patch-002-alpha.png', 'patch-003-alpha.png'):
        inputs[str(reference / name)] = sha(reference / name)
    jobs = cut_assets(source, reference, output)
    bake = bake_assets(reference, output)
    for asset in SPECS:
        before, buffers, _ = read_glb(source / asset / 'model.glb')
        after, updated, _ = read_glb(output / asset / 'model.glb')
        # Covered resources remain byte-for-byte, including every UV accessor.
        if updated[0][:len(buffers[0])] != buffers[0]:
            raise ValueError('Covered binary payload changed: ' + asset)
        for table in ('meshes', 'accessors', 'materials', 'images', 'textures'):
            if after[table][:len(before[table])] != before[table]:
                raise ValueError('Covered resource changed: ' + asset + '/' + table)
        for old, new in zip(before['nodes'], after['nodes']):
            for key, value in old.items():
                if key not in ('children', 'extras') and new.get(key) != value:
                    raise ValueError('Covered node changed: ' + old['name'])
        descriptor = json.loads((output / asset / 'asset.json').read_text())
        nodes = {node['name']: node for node in after['nodes']}
        for component in descriptor['components']:
            for key, value in nodes.get(component['name'], {}).get('extras', {}).items():
                if key.startswith('reveal_'):
                    component[key] = value
        (output / asset / 'asset.json').write_text(json.dumps(descriptor, indent=2)+'\n')
    for path, expected in inputs.items():
        if sha(path) != expected:
            raise ValueError('Source changed during staging: ' + path)
    report = {'version': 1, 'inputs': inputs, 'recipe_sha256': sha(__file__),
              'covered_resources_unchanged': True, 'states': jobs,
              'source_projection': 'First-hit surface, native patch alpha, depth tolerance 3 units',
              'unobserved_fill': 'Connected neutral placeholders >=64 texels; source swatches, inferred alpha=0',
              'outputs': {asset: {'model_sha256': sha(output / asset / 'model.glb'),
                                 'descriptor_sha256': sha(output / asset / 'asset.json')}
                          for asset in SPECS}}
    (output / 'integration.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('reference', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.source, args.reference, args.output)
