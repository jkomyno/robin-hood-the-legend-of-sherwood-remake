"""Upper west curtain wall (walkway wall from the cone tower to the inner gate).

Nodes: 281 wall body, 282/283 south (front) parapet east/west runs, 284/285
north (garden-side) parapet east/west runs. Native pixel = (x, y - z).

Numbered-corner trace (inspection/corner-trace.json in the workspace, built by
``write_trace``): along every run the covered artwork shows regularly spaced
crenels. Each notch is recorded by its east shoulder (the right edge of the
dark, shadowed west side face of the next merlon, measured as a dark column run
in the band between notch floor and cap along the projected front edge), its
west shoulder (measured where the background/walkway shows through; on the
west runs the ~7 px opening width is inferred from the rectified strips), the
merlon cap and the notch floor. Pixel x equals native x, so t along a run is
(x - x_a) / (x_b - x_a); heights are z = y_edge(t) - pixel_y.

Measured heights (native z): walkway 435 (native 281 top, consistent with the
lit walkway strip between the parapets); caps 464.7 / 465.9 (south west/east),
462.7 / 465 (north west/east); notch floors 452.4 / 453.1 / 450.7 / 452.
Periods: 17 px on the west runs, 21 px on the east runs.

Wall foot: along the south face the painted masonry meets the rock spur between
native z ~392 (x 1076-1110) and ~423 (rock bulge at x 943-973); the body's south
foot follows that traced line (SOUTH_FOOT) so rock pixels are not projected on
the wall. The garden (z 390) abuts the north face, whose foot is z 388.
"""
from west_complex_geom import Shape, crenel_profile, extrude_profile, native_obstacles, points

WALKWAY_Z = 435.0
FOOT_Z = 390.0

# run: node, front edge point indices (a, b), back edge indices, cap, floor, notches (x_west, x_east)
RUNS = {
    'south-west': dict(node=283, front=(1, 2), back=(0, 3), cap=464.7, floor=452.4, period=17,
                       east_edges=[854, 871, 888, 906, 923, 939, 957, 973, 990, 1007, 1024], width=7,
                       west_measured=False),
    'south-east': dict(node=282, front=(1, 2), back=(0, 3), cap=465.9, floor=453.1, period=21,
                       east_edges=[1041, 1062, 1083, 1104, 1125, 1147, 1168], width=8,
                       west_measured=False),
    'north-west': dict(node=285, front=(1, 2), back=(0, 3), cap=462.7, floor=450.7, period=17,
                       east_edges=[843, 860, 878, 895, 912, 929, 945, 962, 979, 996], width=7,
                       west_measured=False),
    'north-east': dict(node=284, front=(1, 2), back=(0, 3), cap=465.0, floor=452.0, period=21,
                       notches=[(1005.3, 1013), (1026, 1035), (1047, 1055), (1068, 1076), (1088, 1097),
                                (1108, 1118), (1130, 1138), (1151, 1160)],
                       west_measured=True),
}


def run_notches(run):
    if 'notches' in run:
        return list(run['notches'])
    return [(e - run['width'], e) for e in run['east_edges']]


def edges(obstacles, run):
    p = [(x, y) for x, y, _, _ in points(obstacles, run['node'])]
    a, b = run['front']
    c, d = run['back']
    return (p[a], p[b]), (p[c], p[d])


def parapet(obstacles, run):
    front, back = edges(obstacles, run)
    (xa, _), (xb, _) = front
    intervals = []
    for lo, hi in run_notches(run):
        t0, t1 = sorted(((lo - xa) / (xb - xa), (hi - xa) / (xb - xa)))
        intervals.append((max(0.0, t0 if t0 > 1e-3 else 0.0), min(1.0, t1 if t1 < 1 - 1e-3 else 1.0)))
    profile = crenel_profile(WALKWAY_Z, run['cap'], run['floor'], intervals)
    return extrude_profile(front, back, profile)


# South-face masonry foot traced on the rectified face strips
# (scratch/west_complex/curtain/face-281-*.png): native x -> native z where the
# painted masonry meets rock or foliage. The north (garden) face foot is FOOT_Z.
SOUTH_FOOT = [(833, 393), (853, 395), (866, 405), (910, 406), (920, 417), (943, 423), (973, 423),
              (983, 417), (1006, 407), (1026, 404), (1043, 407), (1060, 403), (1076, 392), (1110, 392),
              (1126, 395), (1160, 400), (1198.5, 400)]


def _foot(x):
    for (x0, z0), (x1, z1) in zip(SOUTH_FOOT, SOUTH_FOOT[1:]):
        if x0 <= x <= x1:
            return z0 + (z1 - z0) * (x - x0) / (x1 - x0)
    return SOUTH_FOOT[0][1] if x < SOUTH_FOOT[0][0] else SOUTH_FOOT[-1][1]


def body(obstacles):
    """Closed quad-section tube along the bent wall; south foot follows the masonry line."""
    p = [(x, y) for x, y, _, _ in points(obstacles, 281)]
    # 281: 0 NE, 1 SE, 2 S-bend, 3 SW, 4 NW, 5 N-bend
    segments = [((p[3], p[2]), (p[4], p[5])), ((p[2], p[1]), (p[5], p[0]))]
    stations = []
    for index, ((s0, s1), (n0, n1)) in enumerate(segments):
        xs = sorted({s0[0], s1[0]} | {x for x, _ in SOUTH_FOOT if s0[0] < x < s1[0]})
        for x in xs if index == 0 else xs[1:]:
            t = (x - s0[0]) / (s1[0] - s0[0])
            south = (s0[0] + (s1[0] - s0[0]) * t, s0[1] + (s1[1] - s0[1]) * t)
            north = (n0[0] + (n1[0] - n0[0]) * t, n0[1] + (n1[1] - n0[1]) * t)
            stations.append((south, north, _foot(south[0])))
    verts, faces = [], []
    for south, north, foot in stations:
        verts += [(*south, foot), (*south, WALKWAY_Z), (*north, WALKWAY_Z), (*north, FOOT_Z - 2.0)]
    for i in range(len(stations) - 1):
        a, b = 4 * i, 4 * (i + 1)
        for k in range(4):
            faces.append([a + k, a + (k + 1) % 4, b + (k + 1) % 4, b + k])
    faces.append([3, 2, 1, 0])
    last = 4 * (len(stations) - 1)
    faces.append([last, last + 1, last + 2, last + 3])
    return Shape.of(verts, faces)


def build(asset):
    if asset != 'lincoln-west-upper-curtain-wall':
        raise KeyError(asset)
    obstacles = native_obstacles()
    shapes = {281: body(obstacles)}
    for run in RUNS.values():
        shapes[run['node']] = parapet(obstacles, run)
    counts = {name: len(run_notches(run)) for name, run in RUNS.items()}
    info = {
        'ground_native_z': {'281': {'south_face_masonry_foot': SOUTH_FOOT, 'north_face': FOOT_Z - 2.0}, '282': WALKWAY_Z, '283': WALKWAY_Z, '284': WALKWAY_Z, '285': WALKWAY_Z},
        'notch_counts': counts,
        'changes': [
            'Wall body 281 trimmed from a native z 0-435 pillar: the south face now ends at the traced masonry/rock line (native z 392-423 along the wall) and the garden face at z 388, so no rock artwork is projected onto the wall.',
            'Parapets 282-285 rebuilt from floating 3-unit strips (native z 442-447) into closed crenellated parapets standing on the walkway (z 435) with artwork-traced caps (z 463-466) and notch floors (z 451-453).',
            'Crenels phased from numbered source corners: south parapet 11 (west run, 17 px period) + 7 (east run, 21 px), north parapet 10 (west) + 8 (east, including the notch at the bend).'],
        'limitations': [
            'West shoulders of the notches on the south runs and the north-west run use the ~7-8 px opening width measured on rectified strips; only their east shoulders (shadowed merlon side faces) and floors are measured per notch.',
            'The parapet ends under the slate cone roof (x < 845 south, x < 836 north) are hidden by the roof; they are left as solid parapet (inferred).',
            'The south-east run east of x 1170 lies in shadow next to the inner gatehouse; no further notch is traced there.',
            'Below the traced south foot (z 392-423) the rock spur (terrain lane, volumes 432/433, currently lower at z 321-422) must rise to meet the wall; until then a gap under the wall is visible from off-source angles.'],
    }
    return shapes, info


def write_trace(workspace):
    """Numbered-corner trace JSON plus unmarked/annotated crops for the workspace."""
    import hashlib
    import json
    from pathlib import Path
    from PIL import Image, ImageDraw
    from west_complex_geom import REFINEMENT
    source = REFINEMENT / 'source-states/covered.png'
    obstacles = native_obstacles()
    corners = []
    for name, run in RUNS.items():
        front, _ = edges(obstacles, run)
        (xa, ya), (xb, yb) = front
        y_at = lambda x: ya + (yb - ya) * (x - xa) / (xb - xa)
        for k, (lo, hi) in enumerate(run_notches(run)):
            for role, x, z, conf in (
                    ('notch-west-shoulder-cap', lo, run['cap'], 'measured' if run['west_measured'] else 'inferred-width'),
                    ('notch-west-floor', lo, run['floor'], 'measured' if run['west_measured'] else 'inferred-width'),
                    ('notch-east-floor', hi, run['floor'], 'measured'),
                    ('notch-east-shoulder-cap', hi, run['cap'], 'measured')):
                if role == 'notch-west-shoulder-cap' and lo <= min(xa, xb) + 0.5:
                    continue  # notch open at the run end (bend): no west cap corner exists
                corners.append({'id': len(corners) + 1, 'run': name, 'source_node': f"building-{run['node']:03}",
                                'notch': k + 1, 'role': role, 'pixel': [round(x, 1), round(y_at(x) - z, 1)],
                                'native_z': z, 'confidence': conf, 'visibility': 'visible',
                                'cap_edge': 'front (near) cap edge of the camera-facing parapet face'})
    crop = (790, 1040, 1215, 1320)
    trace = {'version': 1, 'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
             'crop_origin': crop[:2], 'crop_box': crop, 'method': (
                 'East shoulders and floors: dark column runs (mean luminance < 55) in the band between notch floor and '
                 'cap along the projected front edge of each run, cross-checked against dark-component slot tops/bottoms '
                 'and the rectified strips (scratch/west_complex/curtain/rect-*.png). West shoulders: measured where '
                 'foliage shows through on the north-east run; elsewhere east shoulder minus the measured opening width.'),
             'runs': {k: {kk: vv for kk, vv in v.items()} for k, v in RUNS.items()},
             'corners': corners, 'typical_uncertainty_px': 1.5}
    out = Path(workspace) / 'inspection'
    out.mkdir(exist_ok=True)
    (out / 'corner-trace.json').write_text(json.dumps(trace, indent=2) + '\n')
    image = Image.open(source).convert('RGB').crop(crop)
    scale = 3
    plain = image.resize((image.width * scale, image.height * scale), Image.NEAREST)
    marked = plain.copy()
    draw = ImageDraw.Draw(marked)
    colours = {'south-west': (255, 60, 60), 'south-east': (255, 160, 0), 'north-west': (0, 220, 255), 'north-east': (80, 255, 80)}
    previous = {}
    for c in corners:
        x, y = (c['pixel'][0] - crop[0]) * scale, (c['pixel'][1] - crop[1]) * scale
        col = colours[c['run']]
        if c['run'] in previous:
            draw.line([previous[c['run']], (x, y)], fill=col, width=1)
        previous[c['run']] = (x, y)
        r = 2 if c['confidence'] == 'measured' else 1
        draw.ellipse((x - r, y - r, x + r, y + r), outline=col, fill=col if c['confidence'] == 'measured' else None)
        if c['role'].endswith('cap') and c['role'].startswith('notch-east'):
            draw.text((x + 2, y - 10), str(c['id']), fill=col)
    sheet = Image.new('RGB', (plain.width * 2 + 6, plain.height))
    sheet.paste(plain, (0, 0))
    sheet.paste(marked, (plain.width + 6, 0))
    sheet.save(out / 'corner-trace.png')
    return trace
