#!/usr/bin/env python3
"""Recover Wychford's editable ground and paths from its published source assets.

Run from any directory. Requires the local published ground model. The old terrain
image is retained in maps/wychford for visual reference, never applied to the new
mesh: roads and materials are editable instead of being baked into that image.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SIN = math.sin(math.radians(35))
COS = math.cos(math.radians(35))


def load_ground(path):
    data = path.read_bytes()
    magic, version, length = struct.unpack_from('<III', data)
    assert magic == 0x46546C67 and version == 2 and length == len(data)
    json_length, kind = struct.unpack_from('<II', data, 12)
    assert kind == 0x4E4F534A
    gltf = json.loads(data[20:20 + json_length])
    binary = 28 + json_length
    primitive = gltf['meshes'][0]['primitives'][0]
    assert gltf['nodes'] == [{'name': 'ground', 'mesh': 0}], 'Unexpected ground transform'

    def accessor(index):
        a = gltf['accessors'][index]
        view = gltf['bufferViews'][a['bufferView']]
        count = {'VEC3': 3, 'VEC2': 2, 'SCALAR': 1}[a['type']]
        fmt = '<' + {5126: 'f', 5123: 'H', 5125: 'I'}[a['componentType']] * count
        stride = view.get('byteStride', struct.calcsize(fmt))
        offset = binary + view.get('byteOffset', 0) + a.get('byteOffset', 0)
        return [struct.unpack_from(fmt, data, offset + i * stride) for i in range(a['count'])]

    positions = accessor(primitive['attributes']['POSITION'])
    uvs = accessor(primitive['attributes']['TEXCOORD_0'])
    indices = [i[0] for i in accessor(primitive['indices'])]
    xs = sorted(set(p[0] for p in positions))
    ys = sorted(set(-p[1] for p in positions))
    assert len(xs) * len(ys) == len(positions), 'Ground is no longer a complete grid'
    columns = len(xs)
    vertices = []
    for i, ((x, y, z), uv) in enumerate(zip(positions, uvs)):
        assert x == xs[i % columns] and -y == ys[i // columns]
        vertices.append({'id': f'wych-v-{i}', 'position': [x, -y * SIN, z * COS], 'uv': list(uv)})
    cells = []
    expected = []
    for row in range(len(ys) - 1):
        for col in range(columns - 1):
            i = row * columns + col
            corners = [i, i + 1, i + columns + 1, i + columns]
            expected.extend([i, i + columns + 1, i + 1, i, i + columns, i + columns + 1])
            cells.append({'id': f'wych-cell-{row}-{col}', 'vertices': corners, 'material': 'grass_short'})
    assert indices == expected, 'Ground triangle diagonals changed; migration must preserve them'
    return {'version': 1, 'spacing': xs[1] - xs[0], 'vertices': vertices, 'cells': cells}, xs, ys


def resample_ground(source, xs, ys):
    """Refine a coarse grid where the published relief needs more resolution.

    Requires numpy/scipy (available in the terrain tooling environment). Shared
    Delaunay edges keep the irregular mesh connected without hanging vertices.
    Error is checked at every source vertex and every source triangle centroid and edge midpoint.
    """
    import numpy as np
    from scipy.spatial import Delaunay
    positions = np.array([v['position'] for v in source['vertices']])
    triangles = np.array([tri for c in source['cells'] for tri in
                          [[c['vertices'][0], c['vertices'][1], c['vertices'][2]],
                           [c['vertices'][0], c['vertices'][2], c['vertices'][3]]]])
    edges = np.unique(np.sort(np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]]), axis=1), axis=0)
    samples = np.concatenate([positions, positions[triangles].mean(axis=1), positions[edges].mean(axis=1)])
    chosen = {r*len(xs)+c for r in list(range(0, len(ys)-1, 5))+[len(ys)-1]
              for c in list(range(0, len(xs)-1, 5))+[len(xs)-1]}
    for iteration in range(20):
        points = samples[sorted(chosen)]
        mesh = Delaunay(points[:, :2])
        simplex = mesh.find_simplex(samples[:, :2])
        assert (simplex >= 0).all(), 'Resampling omitted part of the ground'
        bary = np.einsum('ijk,ik->ij', mesh.transform[simplex, :2], samples[:, :2]-mesh.transform[simplex, 2])
        bary = np.c_[bary, 1-bary.sum(axis=1)]
        error = abs((points[mesh.simplices[simplex], 2]*bary).sum(axis=1)-samples[:, 2])
        bad = np.where(error > 2)[0]
        if not len(bad):
            break
        # Insert the worst sample in each failing triangle, then retriangulate.
        chosen.update({int(simplex[i]): int(i) for i in bad[np.argsort(error[bad])]}.values())
    else:
        raise ValueError('Ground refinement did not reach the two-pixel tolerance')
    vertices = [{'id': f'wych-v-{i}', 'position': p.tolist(),
                 'uv': [float(p[0]/3600), float(p[1]/2400)]} for i, p in enumerate(points)]
    # Stable ordering keeps regeneration diffs readable. scipy emits CCW faces.
    faces = sorted(tuple(int(i) for i in tri) for tri in mesh.simplices)
    cells = [{'id': f'wych-cell-{i}', 'vertices': list(face), 'material': 'grass_short'} for i, face in enumerate(faces)]
    stats = {'samples': len(samples), 'maximumHeightError': float(error.max()),
             'meanHeightError': float(error.mean()), 'p95HeightError': float(np.quantile(error, .95))}
    return {'version': 1, 'spacing': 128, 'vertices': vertices, 'cells': cells}, stats


def path_points(d):
    """Sample the absolute SVG path commands used by the committed layout."""
    tokens = re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?', d)
    points = []
    i = 0
    while i < len(tokens):
        command = tokens[i]
        i += 1
        count = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'Q': 4, 'Z': 0}[command]
        values = list(map(float, tokens[i:i + count]))
        i += count
        if command in ('M', 'L'):
            points.append(tuple(values))
        elif command == 'H':
            points.append((values[0], points[-1][1]))
        elif command == 'V':
            points.append((points[-1][0], values[0]))
        elif command == 'Q':
            start = points[-1]
            for j in range(1, 33):
                t = j / 32
                points.append(tuple((1-t)**2*start[k] + 2*(1-t)*t*values[k] + t*t*values[k+2] for k in range(2)))
    return points


def distance_squared(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    length = dx*dx + dy*dy
    t = max(0, min(1, ((p[0]-a[0])*dx + (p[1]-a[1])*dy)/length)) if length else 0
    return (p[0]-a[0]-t*dx)**2 + (p[1]-a[1]-t*dy)**2


def simplify(points, tolerance=4):
    if len(points) < 3:
        return points
    distance, index = max((distance_squared(p, points[0], points[-1]), i) for i, p in enumerate(points[1:-1], 1))
    if distance <= tolerance*tolerance:
        return [points[0], points[-1]]
    return simplify(points[:index+1], tolerance)[:-1] + simplify(points[index:], tolerance)


def inside(point, polygon):
    x, y = point
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            result = not result
    return result


def svg_points(element):
    return [tuple(map(float, p.split(','))) for p in element.attrib['points'].split()]


def height_at(terrain, xs, ys, x, y):
    import bisect
    col = min(len(xs)-2, max(0, bisect.bisect_right(xs, x)-1))
    row = min(len(ys)-2, max(0, bisect.bisect_right(ys, y/SIN)-1))
    u = max(0, min(1, (x-xs[col])/(xs[col+1]-xs[col])))
    v = max(0, min(1, (y/SIN-ys[row])/(ys[row+1]-ys[row])))
    i = row*len(xs)+col
    heights = [terrain['vertices'][j]['position'][2] for j in (i, i+1, i+len(xs)+1, i+len(xs))]
    return ((1-u)*heights[0] + (u-v)*heights[1] + v*heights[2]) if u >= v else ((1-v)*heights[0] + u*heights[2] + (v-u)*heights[3])


def migrate(document, terrain, source, xs, ys, layout, svg):
    assert document['size'] == [3600, 2400]
    woodland = path_points(svg[1].attrib['d'])
    courtyard = svg_points(svg[39])
    bank = svg_points(svg[37])
    def classify_material(x, y):
        p = (x, y/SIN)
        material = 'ground_forest_floor' if inside(p, woodland) else 'grass_short'
        for element, preset in [(svg[2], 'ground_rocky'), (svg[3], 'grass_dry')]:
            a = element.attrib
            if ((p[0]-float(a['cx']))/float(a['rx']))**2 + ((p[1]-float(a['cy']))/float(a['ry']))**2 <= 1:
                material = preset
        if any(distance_squared(p, a, b) <= 90**2 for a, b in zip(bank, bank[1:])):
            material = 'shore_pebbles'
        if inside(p, courtyard):
            material = 'ground_bare'
        return material

    for vertex in terrain['vertices']:
        vertex['material'] = classify_material(*vertex['position'][:2])
    for cell in terrain['cells']:
        positions = [terrain['vertices'][i]['position'] for i in cell['vertices']]
        cell['material'] = classify_material(
            sum(v[0] for v in positions)/len(positions),
            sum(v[1] for v in positions)/len(positions))

    roads = []
    def add_road(name, points, width, material='path_dirt'):
        points = [[x, y, height_at(source, xs, ys, x, y)] for x, y in points]
        roads.append({'id': f'wych-editable-road-{len(roads)+1}', 'name': name, 'kind': 'road',
                      'points': points, 'closed': False, 'width': width, 'pointWidths': [width]*len(points),
                      'pointMaterials': [material]*len(points), 'repeatLength': 128})
    for name, width, points in layout['roads']:
        add_road(name, points, width)
    # The first fifteen polylines correspond to the named layout roads. Remaining
    # paths exist only in the drawing; simplify their sampled curves for editing.
    polylines = [e for e in svg if e.tag.endswith('polyline') and e.get('stroke') == '#b2986b']
    assert len(polylines) == 33 and len(layout['roads']) == 15
    for i, element in enumerate(polylines[15:], 1):
        points = [(x, y*SIN) for x, y in simplify(svg_points(element))]
        add_road(f'Doorstep lane {i}', points, float(element.get('stroke-width')))
    for name, element in zip(['Keep approach paving', 'Garrison courtyard paving'], svg[40:42]):
        points = [(x, y*SIN) for x, y in path_points(element.attrib['d'])]
        add_road(name, points, float(element.get('stroke-width')), 'floor_paving')
    document['terrain'] = terrain
    document['sceneAssets'] = [a for a in document.get('sceneAssets', []) if a['id'] != 'wychford-terrain']
    document['splines'] = [s for s in document['splines'] if not s['id'].startswith('wych-editable-road-')] + roads
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify committed migration without writing')
    args = parser.parse_args()
    scene = ROOT/'library/scenes/Wychford.rhlos-map.json'
    document = json.loads(scene.read_text())
    source, xs, ys = load_ground(ROOT/'library/3d-assets/wychford/wychford-terrain/model.glb')
    terrain, stats = resample_ground(source, xs, ys)
    result = migrate(json.loads(json.dumps(document)), terrain, source, xs, ys,
                     json.loads((ROOT/'maps/wychford/layout.json').read_text()),
                     ET.parse(ROOT/'maps/wychford/terrain-layout.svg').getroot())
    # These descriptors received gameplay updates while their pinned models and
    # all placement transforms remained unchanged. Refresh only their metadata.
    for reference in result['assetSources']:
        if reference['id'] not in {'leicester-southeast-cottage', 'leicester-watermill'}:
            continue
        model = ROOT/'library'/reference['model']
        assert hashlib.sha256(model.read_bytes()).hexdigest() == reference['model_sha256'], 'Pinned model changed'
        descriptor = ROOT/'library'/reference['descriptor']
        data = descriptor.read_bytes()
        parsed = json.loads(data)
        assert parsed['id'] == reference['id'] and descriptor.parent/parsed['model'] == model
        reference['descriptor_sha256'] = hashlib.sha256(data).hexdigest()
    # Everything besides ground and the reconstructed roads must survive verbatim.
    for key in document.keys() - {'terrain', 'splines', 'sceneAssets', 'assetSources'}:
        assert result[key] == document[key], key
    for before, after in zip(document['assetSources'], result['assetSources']):
        assert {k: v for k, v in before.items() if k != 'descriptor_sha256'} == {k: v for k, v in after.items() if k != 'descriptor_sha256'}
    assert [s for s in document['splines'] if s['kind'] != 'road'] == [s for s in result['splines'] if s['kind'] != 'road']
    assert len(source['vertices']) == 14541 and len(source['cells']) == 14300
    assert len(terrain['vertices']) < 1500 and stats['maximumHeightError'] <= 2
    assert len([s for s in result['splines'] if s['kind'] == 'road']) == 35
    if args.check:
        assert document == result, 'Saved Wychford differs from reproducible migration'
    else:
        scene.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'vertices': len(terrain['vertices']), 'cells': len(terrain['cells']),
                      'roads': 35, 'sampling': stats, 'materials': dict(Counter(c['material'] for c in terrain['cells'])),
                      'vertexMaterials': dict(Counter(v['material'] for v in terrain['vertices'])),
                      'heightRange': [min(v['position'][2] for v in terrain['vertices']), max(v['position'][2] for v in terrain['vertices'])]}, indent=2))


if __name__ == '__main__':
    main()
