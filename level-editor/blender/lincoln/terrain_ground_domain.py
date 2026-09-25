"""Reviewed ground receiver domain for the Lincoln terrain (numpy/PIL, no bpy).

Domain = covered.png pixels where the refined ground is the front-most surface
of the integrated scene at the source camera (z-buffer, native (x, y, z) ->
pixel (x, y - z)), minus every covered-state native mask (buildings, walls,
props, trees and bushes; patch applied-only masks ignored; the reject-all
mask 428 is not a silhouette), minus every authored receiver domain of another
node (429-453), minus the manual carve-outs below (painted props and map-edge
plateau gaps found by inspection). Painted shadows stay ground. Unmasked
foliage stays in the domain (the ground is its only receiver) and is listed
for the tree/bush lane.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

H, W = 2176, 2944
REJECT_ALL = 428

# Pixel polygons in covered.png. Each was inspected at 2-3x nearest-neighbour zoom.
CARVEOUTS = {
    'east map-edge plateau gaps': [(2930, 0), (2944, 0), (2944, 2176), (2930, 2176)],
    'north-east top-edge plateau gaps': [(2180, 0), (2930, 0), (2930, 4), (2180, 4)],
    'north outer plateau pinholes': [(2362, 228), (2380, 228), (2380, 248), (2362, 248)],
    'pond landing stage and mooring pole (no 3D node, no mask)':
        [(484, 628), (530, 619), (539, 612), (548, 612), (548, 672), (540, 672), (510, 677), (500, 664), (484, 645)],
    'loose plank west of the landing stage': [(415, 638), (448, 636), (450, 654), (415, 655)],
    'tool beside the barn handcart': [(165, 615), (195, 612), (200, 640), (170, 645)],
    'log lying east of the longhouse yard': [(707, 461), (765, 466), (765, 475), (707, 470)],
    'two poles lying on the longhouse path': [(638, 440), (700, 405), (715, 408), (652, 452)],
    'stake on the pond south bank': [(308, 903), (322, 903), (322, 932), (308, 932)],
}
UNMASKED_FOLIAGE = {
    'west-bank stream bush': [1090, 120, 1150, 155],
    'east-bank stream shrub': [1290, 145, 1350, 190],
    'shrub south of the stream bend': [1195, 465, 1225, 495],
    'bush south of the pond': [400, 842, 445, 880],
    'fern tuft at the west edge': [40, 960, 80, 990],
    'grass between canopy-mask holes north of the keep': [1500, 0, 2000, 470],
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _bitmap(inventory_dir, record):
    a = np.array(Image.open(Path(inventory_dir) / record['png']).convert('L')) > 0
    full = np.zeros((H, W), bool)
    x, y = record['box_top_left']
    h, w = a.shape
    full[max(0, y):min(H, y + h), max(0, x):min(W, x + w)] = \
        a[max(0, -y):min(h, H - y), max(0, -x):min(w, W - x)]
    return full


def scenery_indices(inventory, layers):
    by_layer = {(r['layer'], r['layer_index']): r['index'] for r in inventory['masks'] if r.get('layer') is not None}
    initial, applied = set(), set()
    for patch in layers['patches']:
        initial |= {by_layer[(m['layer'], m['index'])] for m in patch['state']['old_masks']}
        applied |= {by_layer[(m['layer'], m['index'])] for m in patch['state']['new_masks']}
    return sorted(r['index'] for r in inventory['masks']
                  if r.get('png') is not None and r['index'] != REJECT_ALL and r['index'] not in applied - initial)


def author(label, names, *, source, inventory_path, layers_path, out_dir, scene_record):
    """Write inspection/ground-domain-ground.{png,json} and evidence sheets; return the record."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    inventory_path = Path(inventory_path)
    inventory = json.loads(inventory_path.read_text())
    records = {r['index']: r for r in inventory['masks']}
    indices = scenery_indices(inventory, json.loads(Path(layers_path).read_text()))
    scenery = np.zeros((H, W), bool)
    for i in indices:
        scenery |= _bitmap(inventory_path.parent, records[i])
    ground_ids = [k for k, n in enumerate(names) if n == 'ground']
    if len(ground_ids) != 1:
        raise ValueError(f'Expected one ground label, got {ground_ids}')
    first = label == ground_ids[0]
    carve = np.zeros((H, W), bool)
    for polygon in CARVEOUTS.values():
        image = Image.new('1', (W, H), 0)
        ImageDraw.Draw(image).polygon([tuple(p) for p in polygon], fill=1)
        carve |= np.array(image, bool)
    domain = first & ~scenery & ~carve
    ys, xs = np.nonzero(domain)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    png = out / 'ground-domain-ground.png'
    Image.fromarray((domain[y0:y1, x0:x1] * 255).astype(np.uint8)).save(png)
    src = np.array(Image.open(source).convert('RGB')).astype(float)
    vis = src * 0.45
    vis[domain] = src[domain] * 0.5 + np.array([0, 230, 230]) * 0.5
    removed = first & scenery
    vis[removed] = src[removed] * 0.5 + np.array([230, 0, 230]) * 0.5
    carved = first & carve & ~scenery
    vis[carved] = src[carved] * 0.3 + np.array([255, 140, 0]) * 0.7
    draw_img = Image.fromarray(vis.astype(np.uint8))
    draw = ImageDraw.Draw(draw_img)
    for name, box in UNMASKED_FOLIAGE.items():
        draw.rectangle(box, outline=(255, 255, 0), width=2)
    vis = np.array(draw_img).astype(float)
    evidence = {}
    for name, (bx0, by0, bx1, by1), scale in (('overview', (0, 0, W, H), 0.5),
                                               ('stream-village', (0, 0, 1450, 1150), 1.0),
                                               ('southwest-road', (0, 1050, 700, 2176), 1.0),
                                               ('keep-north', (1450, 0, 2200, 520), 1.0)):
        sheet = np.concatenate([src[by0:by1, bx0:bx1], np.full((by1 - by0, 6, 3), 30.0), vis[by0:by1, bx0:bx1]], 1)
        img = Image.fromarray(sheet.astype(np.uint8))
        if scale != 1.0:
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        path = out / f'ground-domain-ground-evidence-{name}.png'
        img.save(path)
        evidence[path.name] = sha(path)
    domain_full = out / 'ground-source-domain-full.png'
    Image.fromarray((domain * 255).astype(np.uint8)).save(domain_full)
    stats = {'first_hit': int(first.sum()), 'scenery_removed': int(removed.sum()),
             'carved': int(carved.sum()), 'domain': int(domain.sum()),
             'carved_by_region': {}}
    for name, polygon in CARVEOUTS.items():
        image = Image.new('1', (W, H), 0)
        ImageDraw.Draw(image).polygon([tuple(p) for p in polygon], fill=1)
        stats['carved_by_region'][name] = int((np.array(image, bool) & first & ~scenery).sum())
    record = {
        'version': 1, 'asset_id': 'lincoln-terrain', 'source_node': 'ground',
        'purpose': ('Authored receiver domain for the painted village/outer ground, stream water and banks of the '
                    'ground receiver. No native mask outlines walkable ground. Proposed for the next mask inventory '
                    'as a reviewed synthetic mask assigned to source node ground with first-hit gating.'),
        'source': str(source), 'source_sha256': sha(source),
        'coordinates': 'original full-image covered.png pixels (x right, y down)',
        'derivation': {
            'first_hit': ('Pixels where the refined ground (stream channel) is the front-most surface of the '
                          'integrated scene at the source camera; z-buffer over every render-visible working mesh.'),
            'first_hit_scene': scene_record,
            'scenery_removed': (f'Minus {len(indices)} covered-state masks: every native silhouette (patch '
                                'applied-only masks ignored, reject-all 428 excluded) and every authored receiver '
                                'domain of another node (429-453).'),
            'carveouts': CARVEOUTS,
            'shadows': 'Shadows cast on the ground are painted ground and stay in the domain.',
            'unmasked_foliage': UNMASKED_FOLIAGE,
            'unmasked_foliage_note': ('Unmasked foliage painted over the ground stays in the domain (flagged for the '
                                      'tree/bush lane and texture review, not carved).'),
            'gating': 'First-hit receiver gating stays mandatory; the domain never widens a neighbour.'},
        'bitmap': {'png': 'inspection/' + png.name, 'box_top_left': [x0, y0], 'box_size': [x1 - x0, y1 - y0],
                   'pixel_values': '0 = outside, 255 = ground domain (same convention as inventory-v1)',
                   'pixels': int(domain.sum()), 'sha256': sha(png)},
        'full_map_bitmap': {'png': 'inspection/' + domain_full.name, 'sha256': sha(domain_full)},
        'evidence': {'sheets': {'inspection/' + k: v for k, v in evidence.items()},
                     'legend': ('left unmarked covered.png; right cyan domain, magenta removed scenery, orange '
                                'manual carve-outs, yellow boxes unmasked foliage kept in the domain')},
        'statistics': stats,
        'scenery_mask_indices': indices,
        'mask_inventory': str(inventory_path), 'mask_inventory_sha256': sha(inventory_path),
    }
    (out / 'ground-domain-ground.json').write_text(json.dumps(record, indent=2) + '\n')
    return record
