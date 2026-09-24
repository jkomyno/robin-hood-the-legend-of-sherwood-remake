"""Per-asset geometry for the Lincoln south gate/wall lane (pure Python).

Every function returns native-coordinate meshes keyed by owned source node.
Footprints come from the frozen native sight obstacles (see the outline
constants, copied from the reviewed inventory top faces); heights and notch
positions come from the lane's corner traces. Nothing here reads Blender.
"""
import math

from south_gate_walls_geometry import (Mesh, prism, ribbon, crenellated_strip,
                                       polyline_length, point_at, lerp)

PLATEAU = 220.0     # castle-hill plateau top (terrain lane keeps it fixed)
EMBED = 2.0         # footings sink slightly below the plateau top


def profile_fn(profile):
    """Piecewise-linear ground z(t) from a trace ground profile."""
    rows = profile['samples']

    def f(t):
        if t <= rows[0]['t']:
            return rows[0]['z']
        for a, b in zip(rows, rows[1:]):
            if a['t'] <= t <= b['t']:
                u = (t - a['t']) / (b['t'] - a['t']) if b['t'] > a['t'] else 0
                return a['z'] + (b['z'] - a['z']) * u
        return rows[-1]['z']
    return f, [r['t'] for r in rows]


def run_by_name(trace, name):
    for r in trace['runs']:
        if r['run'] == name:
            return r
    raise KeyError(f'trace run {name} missing')


def profile_by_name(trace, name):
    for p in trace['ground_profiles']:
        if p['profile'] == name:
            return p
    raise KeyError(f'ground profile {name} missing')


def parapet(run, bottom, top=None, sill=None):
    return crenellated_strip(run['outer_polyline'], run['inner_polyline'],
                             [(n['t0'], n['t1']) for n in run['notches']], bottom,
                             run['merlon_top_z'] if top is None else top,
                             run['sill_z'] if sill is None else sill)


def body_strip(outer, inner, ground, stations, top):
    """Wall body between two polylines, footing following ground(t)."""
    cells = [(top, top)] * (len(stations) - 1)
    return ribbon(outer, inner, stations, ground, cells)


# ----------------------------------------------------------------------------
def central_wall(trace):
    front = run_by_name(trace, 'central-front')
    bastion = run_by_name(trace, 'central-bastion')
    ground, ts = profile_fn(profile_by_name(trace, 'central-front'))
    outer = front['outer_polyline']
    inner_walk = [(1333, 2024), (1773, 1978)]
    body = body_strip(outer, inner_walk, ground, sorted(set(ts) | {0.0, 1.0}), 320.0)
    par = Mesh()
    par.add_shell(parapet(front, 320.0))
    par.add_shell(parapet(bastion, 320.0))
    zs = [r['z'] for r in profile_by_name(trace, 'central-front')['samples']]
    return {
        'meshes': {'building-086': body, 'building-110': par},
        'ground': {'building-086': {'method': 'mask230 bottom edge along the south face, clamped to plateau-2',
                                    'z_min': min(zs), 'z_max': max(zs), 'datum_removed': 'native z=0 pillar'},
                   'building-110': {'rests_on': 'wall walk z=320 (building-086 top / bastion walk building-085)'}},
        'changes': [
            'Wall body 086 rebuilt as a closed strip from the walk (z=320) down to the measured masonry '
            f'footing ({min(zs):.0f}-{max(zs):.0f}); the native z=0 pillar is removed. The footing follows the '
            'bottom edge of native mask 230 along the south face, where the masonry visibly continues down the cliff.',
            'South face of body 086 moved onto the parapet front line so the face is flush (native 086 edge was 2-4 px behind 110).',
            f"Front parapet 110 rebuilt with {len(front['notches'])} measured crenels "
            f"(notch floor z={front['sill_z']}, merlon top z={front['merlon_top_z']}) from numbered corners; "
            'native flat 340 top and z=0 pillar replaced.',
            f"Half-round bastion parapet (east end of 110) rebuilt with {len(bastion['notches'])} crenels "
            f"(floor {bastion['sill_z']}, top {bastion['merlon_top_z']}) as a separate closed shell.",
        ],
        'inferred': [
            'Back (north) face of 086 and the buried footing below the plateau surface are inferred; only the south face is source-visible.',
            'Bastion returning (east) side of the parapet has no asserted notch (deep shadow).',
        ],
        'limitations': [
            'Masonry below z=220 on the south face lies inside the baseline inner-bailey plateau volume 062; '
            'the terrain lane must recede that cliff outline to the wall face or the lower wall remains occluded.',
            'Bastion notch positions are manual readings (1-2 px); the central run is automatic and regular (24.5 px period).',
            'The corbel/string-course band at z~305-320 is projected texture, not modelled relief.',
        ],
        'notes': {'building-086': {'role': 'curtain wall body under walk'},
                  'building-110': {'role': 'crenellated front parapet and bastion parapet'}},
    }


def x_profile_fn(*profiles):
    """Ground z as a function of image column x (profiles monotonic in x)."""
    pts = sorted((r['x'], r['z']) for p in profiles for r in p['samples'])

    def f(x, y=None):
        if x <= pts[0][0]:
            return pts[0][1]
        for (xa, za), (xb, zb) in zip(pts, pts[1:]):
            if xa <= x <= xb:
                return za + (zb - za) * ((x - xa) / (xb - xa) if xb > xa else 0)
        return pts[-1][1]
    return f, pts


FOLIAGE_153 = ('Native mask 153 is the bush/tree drawn over the west end of the SE curtain top (px x 1975-2050, '
               'y 1445-1500); its pixels are foliage, not masonry, and must not be projected onto the walk/parapet.')
FOLIAGE_66 = ('Native mask 66 is the bush drawn in front of the west gate tower foot (px x 950-1000, y 1775-1815); '
              'foliage pixels must not be projected onto the tower masonry.')


def southeast_curtain(trace):
    front = run_by_name(trace, 'se-front')
    turret = run_by_name(trace, 'se-turret')
    prof = profile_by_name(trace, 'se-front')
    ground, ts = profile_fn(prof)
    body = body_strip(front['outer_polyline'], [(1981, 1854), (2320, 1813)], ground,
                      sorted(set(ts) | {0.0, 1.0}), 350.0)
    par = Mesh()
    par.add_shell(parapet(front, 350.0))
    par.add_shell(parapet(turret, 350.0))
    zs = [r['z'] for r in prof['samples']]
    return {
        'meshes': {'building-084': body, 'building-099': par},
        'ground': {'building-084': {'method': 'bottom edge of native masks 231/232 along the south face, clamped to plateau-2',
                                    'z_min': min(zs), 'z_max': max(zs), 'datum_removed': 'native z=0 pillar'},
                   'building-099': {'rests_on': 'wall walk z=350 (084) and corner-turret walk z=350 (083)'}},
        'changes': [
            f'Wall body 084 rebuilt from the walk (z=350) down to the measured footing ({min(zs):.0f}-{max(zs):.0f}); '
            'the z=0 pillar is removed. South face moved onto the parapet front line.',
            f"Parapet 099 south run rebuilt with {len(front['notches'])} measured crenels (floor z={front['sill_z']}, "
            f"merlon top z={front['merlon_top_z']}; native flat top was 363).",
            f"Corner-turret parapet ring (east part of 099) rebuilt with {len(turret['notches'])} visible front crenels "
            'as a separate closed shell on the corner-turret walk.',
        ],
        'inferred': ['North face of 084 and the buried footing are inferred.',
                     'East-facing merlons of the corner ring are in shadow; the ring top is left solid there.'],
        'limitations': [
            'Masonry below z=220 lies inside the baseline plateau volumes (062/063); the terrain lane must recede the '
            'cliff outline to the wall face, otherwise the lowest courses stay occluded.',
            'Merlon faces are flat; stone relief is projected texture.',
            'The corner-turret parapet (east part of 099) belongs to this asset while the turret body/walk is 083 '
            '(lincoln-southeast-corner-turret): catalog composite, select both for the complete turret.',
        ],
        'notes': {'building-084': {'role': 'curtain wall body under walk'},
                  'building-099': {'role': 'south parapet and corner-turret parapet ring'}},
        'mask_revisions': {
            'building-099': {'add': [232], 'add_note': 'mask232 shared with 083 (SE corner turret) and 098 (east curtain).',
                             'exclude': [153], 'exclude_reason': FOLIAGE_153,
                             'evidence': 'inspection/coverage-audit.png; inspection/foreground-mask-153.png',
                             'note': 'the corner-turret parapet ring at the east end of 099 (x 2329-2397) lies inside '
                                     'native mask 232, not 231 (first coverage audit rejected the ring); mask 232 '
                                     'added under first-hit gating. Foreground bush mask 153 excluded.'},
            'building-084': {'exclude': [153], 'exclude_reason': FOLIAGE_153,
                             'evidence': 'inspection/foreground-mask-153.png',
                             'note': 'foreground bush mask 153 excluded from the walk/body.'}},
    }


def southeast_corner_turret(trace):
    f, pts = x_profile_fn(profile_by_name(trace, 'se-turret-front'), profile_by_name(trace, 'se-east-face'))
    poly = [(2320, 1814), (2328, 1811), (2450, 1654), (2488, 1664), (2387, 1810), (2396, 1814),
            (2390, 1844), (2369, 1850), (2343, 1850), (2329, 1843)]
    body = prism(poly, lambda x, y: f(x), 350.0, subdivide=6)
    zs = [z for _, z in pts]
    return {
        'meshes': {'building-083': body},
        'ground': {'building-083': {'method': 'bottom edge of native masks 231/232 along the turret front and the '
                                              'east face, clamped to plateau-2', 'z_min': min(zs), 'z_max': max(zs),
                                    'datum_removed': 'native z=0 pillar'}},
        'changes': [
            f'Corner turret and east-curtain walk body 083 rebuilt from walk z=350 down to the measured footing '
            f'({min(zs):.0f}-{max(zs):.0f}); native z=0 pillar removed.',
            'Turret front vertices moved onto the outer line of the parapet ring (099) so the tower face is flush '
            '(native 083 turret face was 3 px behind its parapet).',
        ],
        'inferred': ['Inner/back faces and the buried footing are inferred.'],
        'limitations': [
            'The crenellated parapet of this turret is part of 099 (lincoln-southeast-curtain-wall) and the east '
            'curtain parapet is node 098 (lincoln-east-curtain-wall-lower); 083 is only the body/walk.',
            'Masonry below z=220 lies inside baseline terrain volumes 062/063/064; terrain lane must expose it.',
            'The rounded turret keeps the native faceted outline.',
        ],
        'notes': {'building-083': {'role': 'corner turret body and east curtain walk body'}},
    }


def west_curtain(trace):
    a = run_by_name(trace, 'west-a')
    c = run_by_name(trace, 'west-c')
    ground = PLATEAU - EMBED
    skin = Mesh()
    skin.add_shell(parapet(a, ground))
    bump_outer = [(861, 1885), (843, 1894), (882, 1924), (899, 1915)]
    bump_inner = [(868, 1887), (852, 1895), (883, 1918), (899, 1911)]
    skin.add_shell(ribbon(bump_outer, bump_inner, [0.0, 1.0], ground, [(a['merlon_top_z'],) * 2]))
    skin.add_shell(parapet(c, ground))
    walk = [(763, 1806), (801, 1789), (1038, 1967), (997, 1985), (899, 1910), (882, 1917), (851, 1894), (868, 1886)]
    body = prism(walk, ground, 350.0)
    return {
        'meshes': {'building-375': body, 'building-376': skin},
        'ground': {'building-375': {'z': ground, 'method': 'stands on the west/inner-bailey plateau (z=220); the '
                                    'bottom edge of native mask 246 is at z~236-250 because the rock outcrop in '
                                    'front hides the footing, so the footing is set 2 below the plateau top',
                                    'datum_removed': 'native z=0 pillar'},
                   'building-376': {'z': ground, 'method': 'same footing as 375 (front skin of the wall)'}},
        'changes': [
            'Walk body 375 and front skin/parapet 376 trimmed from the native z=0 pillars to a footing at z=218 '
            '(plateau 220 minus 2).',
            f"Parapet 376 rebuilt with {len(a['notches'])} + {len(c['notches'])} measured crenels on the two straight runs "
            f"(notch floor z={a['sill_z']}, merlon top z={a['merlon_top_z']}; native flat top 365).",
            'Pilaster/buttress jog in the middle of the run kept as a solid, uncrenellated block to merlon height.',
        ],
        'inferred': ['Back (NE) face and walk body are inferred; the SW face and walk top are source-visible.',
                     'Buttress top detail (corbelled cap) is flattened to merlon height.'],
        'limitations': ['The flying arch/stair junction with the west gate tower at the SE end is not modelled '
                        '(belongs visually to the tower/garden side; no owned obstacle).',
                        'Footing below the rock outcrop is hidden; the rock itself is terrain-lane geometry.'],
        'notes': {'building-375': {'role': 'wall walk body'},
                  'building-376': {'role': 'front wall skin with crenellated parapet'}},
    }


def project_s(poly, p):
    """Arc length and distance of the closest point of polyline ``poly`` to p."""
    best, acc = (None, 1e18), 0.0
    for a, b in zip(poly, poly[1:]):
        L = math.dist(a, b)
        if L == 0:
            continue
        u = max(0.0, min(1.0, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (L * L)))
        q = lerp(a, b, u)
        d = math.dist(q, p)
        if d < best[1]:
            best = (acc + u * L, d)
        acc += L
    return best


def notch_params(poly, runs, tolerance=6.0, min_len=1.5):
    """Normalised notch intervals on ``poly`` from traced notch front points."""
    L = polyline_length(poly)
    out = []
    for run in runs:
        for n in run['notches']:
            (s0, d0), (s1, d1) = project_s(poly, n['front_left']), project_s(poly, n['front_right'])
            if max(d0, d1) > tolerance:
                continue
            s0, s1 = sorted((s0, s1))
            s0, s1 = max(0.0, s0), min(L, s1)
            if s1 - s0 >= min_len:
                out.append((s0 / L, s1 / L))
    return sorted(out)


def crenel_on(outer, inner, runs, bottom, top, sill, extra=(), inner_runs=()):
    params = notch_params(outer, runs) + notch_params(inner, inner_runs)
    return crenellated_strip(outer, inner, sorted(params), bottom, top, sill, extra_stations=extra)


def dense(n=40):
    return [i / n for i in range(1, n)]


def west_gate_tower(trace):
    front, back = run_by_name(trace, 'wt-front'), run_by_name(trace, 'wt-back')
    f, pts = x_profile_fn(profile_by_name(trace, 'wt-front'))
    # West facets pulled in by 4-5 px: the native outline (x 965) lies outside
    # the tower silhouette of mask 248 / the artwork (edge at x~970).
    outer = [(1065, 2049), (1016, 2049), (984, 2034), (969, 2012), (975, 1994), (985, 1982),
             (1001, 1972), (1044, 1966), (1092, 1977), (1110, 1994)]
    inner = [(1070, 2044), (1019, 2045), (986, 2030), (976, 2014), (979, 1996), (987, 1987),
             (1001, 1976), (1044, 1971), (1082, 1978), (1106, 2000)]
    Lo = polyline_length(outer)
    ground = lambda t: min(PLATEAU - EMBED, f(point_at(outer, t * Lo)[0]))
    ring = crenel_on(outer, inner, [front], ground, front['merlon_top_z'], front['sill_z'],
                     extra=dense(), inner_runs=[back])
    core_poly = [(976, 2015), (979, 1996), (987, 1987), (1001, 1976), (1044, 1970), (1081, 1978),
                 (1106, 1998), (1069, 2046), (1019, 2045), (986, 2031)]
    core = prism(core_poly, PLATEAU - EMBED, 400.0)
    zs = [z for _, z in pts]
    n_notch = len(notch_params(outer, [front])) + len(notch_params(inner, [back]))
    return {
        'meshes': {'building-121': ring, 'building-091': core},
        'ground': {'building-121': {'method': 'bottom edge of native mask 248 along the front arc, clamped to plateau-2',
                                    'z_min': min(zs), 'z_max': min(max(zs), PLATEAU - EMBED),
                                    'datum_removed': 'native z=0 pillar'},
                   'building-091': {'z': PLATEAU - EMBED, 'method': 'core stands on the plateau inside the ring'}},
        'changes': [
            f'Round-tower wall ring 121 rebuilt as a closed C-shaped shell from the measured footing '
            f'({min(zs):.0f}-{PLATEAU - EMBED:.0f}) to a crenellated parapet: {n_notch} crenels '
            f"({len(front['notches'])} front, {len(back['notches'])} far side) with notch floor z={front['sill_z']} and "
            f"merlon top z={front['merlon_top_z']} (native flat top 412).",
            'West facets of ring and core pulled in 3-5 px to the mask-248/artwork silhouette (native x 965 -> 969).',
            'Tower core/platform 091 trimmed from the z=0 pillar to the plateau (z=218..400).',
        ],
        'inferred': ['Far-side notches are traced on the inner face (mask 248/270 background test); '
                     'the outer north face and the core are not source-visible.'],
        'limitations': ['The ring keeps the native 10-facet outline; curvature is faceted.',
                        'Arrow slits and the corbel band are projected texture.',
                        'Masonry below z=220 on the front arc is inside the baseline plateau volume 062 (terrain lane).'],
        'notes': {'building-121': {'role': 'tower wall ring with parapet'},
                  'building-091': {'role': 'tower core and roof platform'}},
        'mask_revisions': {'building-121': {'exclude': [66], 'exclude_reason': FOLIAGE_66,
                                            'evidence': 'inspection/foreground-mask-66.png',
                                            'note': 'foreground bush mask 66 excluded from the tower ring.'}},
    }


def east_gate_tower(trace):
    front = run_by_name(trace, 'et-front')
    f, pts = x_profile_fn(profile_by_name(trace, 'et-front'))
    # East facets pulled in by ~5 px: the native outline (x 1352) overshoots
    # the tower silhouette of mask 248 / the artwork (edge at x~1346).
    outer = [(1206, 2088), (1217, 2106), (1264, 2118), (1295, 2117), (1320, 2112), (1339, 2095),
             (1347, 2076), (1342, 2059), (1327, 2042), (1295, 2031)]
    inner = [(1211, 2086), (1221, 2101), (1254, 2113), (1280, 2114), (1317, 2107), (1336, 2087),
             (1338, 2065), (1325, 2045), (1292, 2035)]
    Lo = polyline_length(outer)
    ground = lambda t: min(PLATEAU - EMBED, f(point_at(outer, t * Lo)[0]))
    ring = crenel_on(outer, inner, [front], ground, front['merlon_top_z'], front['sill_z'], extra=dense())
    g = PLATEAU - EMBED
    ramp = prism([(1285, 2010), (1293, 2034), (1344, 2058), (1334, 2023)], g,
                 lambda x, y: 294.0 + (x - 1289.0) / (1339.0 - 1289.0) * 26.0)
    pier = prism([(1309, 2052), (1317, 2041), (1339, 2047), (1331, 2057)], g, 312.0)
    zs = [z for _, z in pts]
    return {
        'meshes': {'building-111': ring, 'building-126': ramp, 'building-120': pier},
        'ground': {'building-111': {'method': 'bottom edge of native mask 248 along the front arc, clamped to plateau-2',
                                    'z_min': min(zs), 'z_max': PLATEAU - EMBED, 'datum_removed': 'native z=0 pillar'},
                   'building-126': {'z': g, 'datum_removed': 'native z=0 pillar'},
                   'building-120': {'z': g, 'datum_removed': 'native z=0 pillar'}},
        'changes': [
            f"East round-tower wall ring 111 rebuilt as a closed C-shaped shell from the measured footing to a "
            f"crenellated parapet with {len(front['notches'])} front crenels (floor z={front['sill_z']}, "
            f"top z={front['merlon_top_z']}; native flat 412).",
            'East facets of the ring pulled in ~5 px to the mask-248/artwork silhouette (native x 1352 -> 1347).',
            'Rear link ramp 126 (walk 294 -> curtain walk 320) and pier 120 trimmed from z=0 pillars to the plateau; '
            'the ramp keeps its native sloped top as an exact plane.',
            'Roof platform 087 (z 395-400) is unchanged: it is an elevated slab, not a datum pillar.',
        ],
        'inferred': ['NE far-side parapet behind the cone turret is left solid (no reliable notch evidence).',
                     'Ramp 126 and pier 120 are behind the tower and not source-visible in the covered state.'],
        'limitations': [
            'Patch01 (patch-005) reveals the tower interior (floor slab 112, owned by the arch asset); the revealed '
            'interior receivers are not reviewed and the ring is kept closed for the covered state.',
            'Masonry below z=220 on the front arc is inside the baseline plateau volume 062 (terrain lane).',
            'The ring keeps the native faceted outline.'],
        'notes': {'building-111': {'role': 'tower wall ring with parapet'},
                  'building-126': {'role': 'rear link ramp'}, 'building-120': {'role': 'rear pier'}},
        'states': {'patch-005 Patch01': 'covered state modelled (closed tower); revealed interior pending review'},
    }


def gatehouse_arch(trace):
    front, back = run_by_name(trace, 'gate-front'), run_by_name(trace, 'gate-back')
    g = PLATEAU - EMBED
    walk, top, sill = 400.0, front['merlon_top_z'], front['sill_z']
    btop, bsill = back['merlon_top_z'], back['sill_z']
    fo = [(1070, 2066), (1094, 2074), (1167, 2094), (1212, 2107)]
    fi = [(1071, 2062), (1095, 2070), (1168, 2090), (1213, 2103)]

    def seg(poly, i, j):
        return poly[i:j + 1]
    meshes = {}
    # West pier 092.
    m = Mesh()
    # The native 092 footprint starts at x=1017, in front of the west tower's
    # east front arc (tower face y~2049 vs pier face y~2057 at x=1040), so it
    # hid tower masonry that the artwork shows. The pier now starts at the
    # tower surface.
    m.add_shell(prism([(1066, 2048), (1080, 2044), (1112, 2053), (1094, 2074), (1070, 2066)], g, walk))
    m.add_shell(crenel_on(seg(fo, 0, 1), seg(fi, 0, 1), [front], walk, top, sill))
    meshes['building-092'] = m
    # Lintel 113 with a segmental arch soffit over the passage.
    spring, apex = 300.0, 318.0
    arch = lambda t: spring + (apex - spring) * math.sqrt(max(0.0, 1 - (2 * t - 1) ** 2))
    m = Mesh()
    m.add_shell(ribbon([(1094, 2074), (1167, 2094)], [(1112, 2052), (1186, 2073)],
                       [i / 16 for i in range(17)], arch, [(walk, walk)] * 16))
    m.add_shell(crenel_on(seg(fo, 1, 2), seg(fi, 1, 2), [front], walk, top, sill))
    meshes['building-113'] = m
    # East pier 089.
    m = Mesh()
    m.add_shell(prism([(1167, 2095), (1184, 2074), (1203, 2079), (1205, 2078), (1216, 2108)], g, walk))
    m.add_shell(crenel_on(seg(fo, 2, 3), seg(fi, 2, 3), [front], walk, top, sill))
    meshes['building-089'] = m
    # Rear parapets 115/116/114 (camera-facing south faces traced).
    for node, o, i, b in (('building-115', [(1107, 1998), (1146, 2009)], [(1109, 1995), (1149, 2005)], g),
                          ('building-116', [(1147, 2010), (1196, 2021)], [(1149, 2007), (1198, 2018)], 256.0),
                          ('building-114', [(1197, 2022), (1256, 2038)], [(1200, 2018), (1259, 2035)], g)):
        meshes[node] = crenel_on(o, i, [back], b, btop, bsill)
    return {
        'meshes': meshes,
        'ground': {'building-092': {'z': g, 'datum_removed': 'native z=0 pillar'},
                   'building-089': {'z': g, 'datum_removed': 'native z=0 pillar'},
                   'building-115': {'z': g, 'datum_removed': 'native z=0 pillar'},
                   'building-114': {'z': g, 'datum_removed': 'native z=0 pillar'},
                   'building-113': {'soffit': f'segmental arch, springing {spring}, apex {apex}'},
                   'building-116': {'z': 256.0, 'note': 'native bottom kept (rear arch over the passage)'}},
        'changes': [
            'West pier 092 footprint cut back to the west-tower surface (x>=1066): the native pier protruded '
            'in front of the tower front arc and occluded tower masonry visible in the artwork.',
            'Gate piers 092/089 trimmed from z=0 pillars to the plateau (218) and to the wall-walk level 400; the '
            'sloped native 092 top is replaced by the walk level.',
            f'Lintel 113 rebuilt with a segmental arch soffit (springing {spring:.0f}, apex {apex:.0f}) matching the '
            'arch visible above the raised drawbridge leaf; native flat soffit at 292.',
            f"Front parapet over 092/113/089 rebuilt as crenellated strips with {len(front['notches'])} measured "
            f'crenels (floor z={sill}, merlon top z={top}; native flat 428).',
            f"Rear parapets 115/116/114 rebuilt with {len(back['notches'])} crenels traced against the courtyard "
            f'(floor z={bsill}, top z={btop}); 114/115 trimmed to the plateau.',
            'Walk slabs 088/090/125 and the interior floor slab 112 are unchanged (elevated slabs).',
        ],
        'inferred': ['Passage side walls, rear faces and the walk interior are inferred.',
                     'Arch springing height is inferred from the leaf top; apex from the arch visible in the '
                     'lowered-drawbridge frame.'],
        'limitations': [
            'Walkway slab 112 (z 279-295) spans the gate block and the east tower (interior floor revealed by '
            'Patch01); it needs an authored component split before per-tower selection.',
            'Masks 248/270 are composite envelopes over both towers, the gate block and the turret; projection '
            'relies on first-hit gating.',
            'Machicolation holes and portcullis grooves are projected texture only.'],
        'notes': {n: {'role': r} for n, r in (('building-092', 'west gate pier + parapet'),
                                              ('building-113', 'arched lintel + parapet'),
                                              ('building-089', 'east gate pier + parapet'),
                                              ('building-115', 'rear parapet'), ('building-116', 'rear parapet over passage'),
                                              ('building-114', 'rear parapet'))},
        'states': {'patch-003 Pont_levis': 'arch soffit shaped for both leaf states; leaf is building-457 (drawbridge asset)'},
    }


def ellipse(cx, cy, r, a0, a1, n):
    """Native footprint of a world-space circle arc (native y is scaled by sin35)."""
    from south_gate_walls_geometry import SIN
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * SIN * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def half_cone(cx, cy, r, z_base, z_apex, a0, a1, n=12):
    """Closed half cone: arc a0..a1 (degrees), cut through the axis."""
    arc = ellipse(cx, cy, r, a0, a1, n)
    apex = (cx, cy, z_apex)
    m = Mesh()
    base = [(x, y, z_base) for x, y in arc]
    m.face(list(reversed(base)))
    for a, b in zip(base, base[1:]):
        m.face([a, b, apex])
    m.face([base[-1], base[0], apex])
    return m


def disk(cx, cy, r, z0, z1, n=24):
    return prism(ellipse(cx, cy, r, 0, 360, n)[:-1], z0, z1)


def gate_cone_turret(trace):
    g = PLATEAU - EMBED
    cx, cy = 1284.0, 2025.0
    eave_r, eave_lo, eave_hi, apex = 31.0, 455.0, 459.0, 505.0
    return {
        'meshes': {
            'building-117': prism([(1256, 2038), (1260, 2010), (1285, 2010), (1285, 2013), (1266, 2013), (1264, 2038)],
                                  g, 457.0),
            'building-128': prism([(1285, 2010), (1308, 2016), (1299, 2038), (1292, 2037), (1305, 2017), (1285, 2013)],
                                  g, 291.0),
            'building-129': prism([(1285, 2013), (1285, 2010), (1308, 2016), (1299, 2038), (1292, 2037), (1305, 2017)],
                                  355.0, 457.0),
            'building-124': disk(cx, cy, eave_r, eave_lo, eave_hi),
            'building-118': half_cone(cx, cy, eave_r - 1, eave_hi, apex, 90, 270),
            'building-119': half_cone(cx, cy, eave_r - 1, eave_hi, apex, -90, 90),
        },
        'ground': {'building-117': {'z': g, 'datum_removed': 'native z=0 pillar',
                                    'note': 'stair turret continues down behind the tower to the bailey'},
                   'building-128': {'z': g, 'datum_removed': 'native z=0 pillar'}},
        'changes': [
            'Cone roof rebuilt as a true circular cone (world radius 30, native y scaled by sin35) split at the '
            'axis into the two owned halves 118 (west) and 119 (east); native sloped wedges replaced.',
            'Eave plate 124 rebuilt as a round disk (z 455-459) under the cone.',
            'Centre (1284, 2025), eave z 459 and apex z 505 measured from covered.png: eave extremes at px x '
            '1253/1313, y 1566; body front foot at px y 1640 on the tower platform (z 400); apex collar at px 1520.',
            'Turret walls 117/128 trimmed from z=0 pillars to the plateau (218); upper walls 117/129 extended to '
            'the new eave (457). The open doorway between the west/east walls (native gap) is kept.',
        ],
        'inferred': ['Rear half of the cone and body are inferred by symmetry.',
                     'The needle finial above the cone (px 1470-1520) is not modelled: no owned obstacle and '
                     'sub-pixel width.'],
        'limitations': ['Masks 248/270 are composites; the turret relies on first-hit gating.',
                        'Body walls keep the native thin L-shaped footprints rather than a round drum.'],
        'notes': {n: {'role': r} for n, r in (('building-117', 'west turret wall'), ('building-128', 'east wall lower'),
                                              ('building-129', 'east wall upper'), ('building-124', 'eave disk'),
                                              ('building-118', 'cone west half'), ('building-119', 'cone east half'))},
    }


STAIR_STEPS = 12


def wall_stair(trace):
    diag = run_by_name(trace, 'diag')
    f, pts = x_profile_fn(profile_by_name(trace, 'bastion-front'), profile_by_name(trace, 'diag-front'))
    g = PLATEAU - EMBED
    walk_poly = [(1774, 1978), (1793, 1975), (1863, 1915), (1831, 1901), (1852, 1885), (1896, 1903),
                 (1898, 1898), (1888, 1893), (1943, 1852), (1955, 1882), (1916, 1912), (1922, 1914),
                 (1846, 1992), (1850, 2006), (1838, 2020), (1805, 2024), (1777, 2014)]
    walk = prism(walk_poly, lambda x, y: min(g, f(x)), 320.0, subdivide=6)
    rise = (321.0 - PLATEAU) / STAIR_STEPS
    stations = [i / STAIR_STEPS for i in range(STAIR_STEPS + 1)]
    stair = ribbon([(1793, 1974), (1863, 1915)], [(1761, 1962), (1831, 1902)], stations, g,
                   [(PLATEAU + (i + 1) * rise,) * 2 for i in range(STAIR_STEPS)])
    Ld = polyline_length(diag['outer_polyline'])
    skin = crenellated_strip(diag['outer_polyline'], diag['inner_polyline'],
                             [(n['t0'], n['t1']) for n in diag['notches']],
                             lambda t: min(g, f(point_at(diag['outer_polyline'], t * Ld)[0])),
                             diag['merlon_top_z'], diag['sill_z'], extra_stations=dense(20))
    p107 = prism([(1852, 1885), (1856, 1882), (1884, 1893), (1881, 1896)], 320.0, 336.0)
    p108 = prism([(1836, 1895), (1853, 1881), (1858, 1883), (1841, 1897)], 320.0,
                  lambda x, y: 327.0 + (x - 1838.5) / (1855.5 - 1838.5) * 9.0)
    zs = [z for _, z in pts]
    return {
        'meshes': {'building-085': walk, 'building-106': stair, 'building-109': skin,
                   'building-107': p107, 'building-108': p108},
        'ground': {'building-085': {'method': 'bottom edge of masks 230/231/408 along the bastion and diagonal '
                                              'faces, clamped to plateau-2', 'z_min': min(zs), 'z_max': g,
                                    'datum_removed': 'native z=0 pillar'},
                   'building-109': {'method': 'same profile along the diagonal wall face', 'z_min': min(zs)},
                   'building-106': {'z': g, 'note': 'stair foot on the bailey plateau (native ramp foot z=220)'},
                   'building-107': {'z': 320.0, 'note': 'stands on the landing/walk 085'},
                   'building-108': {'z': 320.0, 'note': 'stands on the landing/walk 085'}},
        'changes': [
            'Walk/bastion body 085 trimmed from the z=0 pillar to the measured footing; its bastion face moved '
            'onto the bastion parapet outer line (110) so the half-round face is flush.',
            f'Ramp 106 replaced by a closed stepped stair of {STAIR_STEPS} risers (z 220 -> 321) on the native footprint.',
            f"Diagonal wall skin 109 rebuilt from the measured footing ({min(zs):.0f}+) to a parapet with "
            f"{len(diag['notches'])} crenels (floor {diag['sill_z']}, top {diag['merlon_top_z']}; native flat 337).",
            'Landing parapets 107/108 set on the walk (z=320) instead of z=0 pillars; 108 keeps its sloped top.',
        ],
        'inferred': ['Stair riser count: about eight upper treads are visible above the wall, the lower flight is '
                     f'hidden; {STAIR_STEPS} equal risers are inferred from the visible tread pitch.',
                     'North faces and the buried footing are inferred.'],
        'limitations': ['The bastion parapet belongs to building-110 (central wall asset); the bastion body is 085.',
                        'Masks 230/231 are composite envelopes shared with the central wall, SE curtain and cone turret.',
                        'Masonry below z=220 is inside baseline plateau volume 062/070 (terrain lane).'],
        'mask_revisions': {n: {'add': [231], 'add_note': 'mask231 (turret stair envelope) shared with the cone turret and SE curtain.',
                               'evidence': 'inspection/coverage-audit.png',
                               'note': 'the upper stair treads and landing below the cone turret are drawn inside native '
                                       'mask 231 (its reviewed evidence c-s-curtain-231 lists the stair), not 230/408; '
                                       'the first coverage audit rejected 1394 of 1399 stair pixels. Mask 231 added '
                                       'under first-hit gating.'} for n in ('building-085', 'building-106')},
        'notes': {n: {'role': r} for n, r in (('building-085', 'walk and bastion body'), ('building-106', 'stair'),
                                              ('building-109', 'diagonal wall skin + parapet'),
                                              ('building-107', 'landing parapet'), ('building-108', 'landing parapet'))},
    }


def south_wall_cone_turret(trace):
    f, pts = x_profile_fn(profile_by_name(trace, 'turret-junction'))
    g = PLATEAU - EMBED
    # Native roof wedges float 31 units along the view ray above the walls they
    # crown; shifting (y, z) by -31 keeps every roof pixel and seats the roof on
    # the wall tops (z=373).
    d = 31.0
    L, B, M, F, Rr = (1881, 1926 - d), (1908, 1903 - d), (1910, 1937 - d), (1934, 1951 - d), (1961, 1925 - d)
    zb = 375.0
    apex = (1923.5, 1921.5 - d, 461.0 - d)

    def pyramid(base):
        m = Mesh()
        pts3 = [(x, y, zb) for x, y in base]
        m.face(list(reversed(pts3)))
        for a, b in zip(pts3, pts3[1:] + pts3[:1]):
            m.face([a, b, apex])
        return m
    top122 = {(1944, 1853): 320.0, (1969, 1849.5): 342.0, (1980, 1854): 350.0, (1991, 1881): 350.0, (1956, 1882): 320.0}
    top100 = {(1959, 1882): 332.0, (1992, 1881): 360.0, (1993, 1884): 360.0, (1959, 1884): 332.0}
    ground = lambda x, y: min(g, f(x))
    return {
        'meshes': {
            'building-103': pyramid([L, B, M]),
            'building-102': pyramid([B, Rr, F, M]),
            'building-104': prism([(1917, 1912), (1950, 1885), (1941, 1881), (1944, 1878), (1961, 1886), (1924, 1914)],
                                  g, 373.0),
            'building-127': prism([(1881, 1896), (1896, 1902), (1898, 1898), (1889, 1893), (1917, 1871), (1927, 1875),
                                   (1930, 1872), (1918, 1867)], g, 373.0),
            'building-122': prism(list(top122), ground, lambda x, y: top122[(x, y)]),
            'building-100': prism(list(top100), ground, lambda x, y: top100[(x, y)]),
        },
        'ground': {'building-104': {'z': g, 'datum_removed': 'native z=0 pillar'},
                   'building-127': {'z': g, 'datum_removed': 'native z=0 pillar'},
                   'building-122': {'method': 'mask 231 bottom edge along the junction face', 'z_min': min(z for _, z in pts)},
                   'building-100': {'method': 'mask 231 bottom edge along the junction face', 'z_min': min(z for _, z in pts)}},
        'changes': [
            'Pyramidal roof rebuilt as one closed pyramid split along the native seam into 103 (west) and 102 '
            '(east). The native roof wedges floated 31 units above the turret walls along the source view ray; '
            'both were shifted by (dy, dz) = (-31, -31), which leaves every roof pixel unchanged and seats the '
            'eaves on the wall tops (z 375, apex z 430).',
            'Turret walls 104/127 trimmed from z=0 pillars to the plateau (218).',
            'Junction blocks 122/100 (turret to SE curtain) trimmed to the measured footing, native sloped tops kept.',
            'Upper floor 105 and block 101 unchanged (elevated components).',
        ],
        'inferred': ['Rear roof slopes and hidden turret walls are inferred; eave overhang is not modelled.',
                     'The finial above the apex is not modelled (no owned obstacle, sub-pixel width).'],
        'limitations': ['Mask 231 is a composite envelope (turret, stair, SE curtain); first-hit gating required.',
                        'The turret doorway facing the stair is projected texture on the wall faces.'],
        'notes': {n: {'role': r} for n, r in (('building-103', 'roof west'), ('building-102', 'roof east'),
                                              ('building-104', 'turret walls SE'), ('building-127', 'turret walls NW'),
                                              ('building-122', 'junction block'), ('building-100', 'junction parapet'))},
    }


# Raised drawbridge leaf, measured from native mask 415 (Pont_levis initial
# silhouette): x 1095..1166, bottom px 1850 (x 1095) .. 1869 (x 1165), top px
# 1766 .. 1782, on the gate front line y = 2074 + 0.274 (x - 1094).
LEAF_X = (1095.0, 1166.0)
LEAF_BOTTOM, LEAF_TOP = 224.0, 309.0
LEAF_THICK = 4.0


def gate_line(x):
    return 2074.0 + (x - 1094.0) * 20.0 / 73.0


def leaf_raised():
    x0, x1 = LEAF_X
    a0, a1 = (x0, gate_line(x0) + 0.5), (x1, gate_line(x1) + 0.5)
    b0, b1 = (x0, gate_line(x0) + 0.5 + LEAF_THICK), (x1, gate_line(x1) + 0.5 + LEAF_THICK)
    return prism([a0, a1, b1, b0], LEAF_BOTTOM, LEAF_TOP)


def hinge():
    """Hinge along the leaf's bottom outer edge, in native coordinates."""
    x0, x1 = LEAF_X
    p0 = (x0, gate_line(x0) + 0.5 + LEAF_THICK, LEAF_BOTTOM)
    p1 = (x1, gate_line(x1) + 0.5 + LEAF_THICK, LEAF_BOTTOM)
    return p0, p1


def rotate_native(points, angle_deg):
    """Rotate native points about the hinge by angle (world space), toward the south."""
    from south_gate_walls_geometry import to_world, to_native
    p0, p1 = (to_world(p) for p in hinge())
    ax = [p1[i] - p0[i] for i in range(3)]
    n = math.sqrt(sum(c * c for c in ax))
    k = [c / n for c in ax]
    th = math.radians(angle_deg)
    out = []
    for p in points:
        v = [to_world(p)[i] - p0[i] for i in range(3)]
        kv = sum(k[i] * v[i] for i in range(3))
        cr = [k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0]]
        r = [v[i] * math.cos(th) + cr[i] * math.sin(th) + k[i] * kv * (1 - math.cos(th)) for i in range(3)]
        out.append(to_native(tuple(p0[i] + r[i] for i in range(3))))
    return out


def lowered_angle():
    """Sign of the 90 degree rotation that lays the leaf toward the approach."""
    top = [(LEAF_X[0], gate_line(LEAF_X[0]) + 2.5, LEAF_TOP)]
    for a in (90.0, -90.0):
        q = rotate_native(top, a)[0]
        if q[1] > gate_line(LEAF_X[0]) + 20:
            return a
    raise ValueError('no lowering direction')


def drawbridge(trace):
    deck_top, deck_thick, rail_h = 220.0, 6.0, 16.0
    foot = [(1053, 2108), (1128, 2128), (1078, 2188), (1004, 2167)]
    bridge = Mesh()
    bridge.add_shell(prism(foot, deck_top - deck_thick, deck_top))
    # Rails along the two long sides: three posts each and a handrail beam.
    for a, b in ((foot[3], foot[0]), (foot[2], foot[1])):
        d = (b[0] - a[0], b[1] - a[1])
        L = math.hypot(*d)
        u = (d[0] / L, d[1] / L)
        nrm = (-u[1], u[0])
        inward = 1 if (nrm[0] * (1066 - a[0]) + nrm[1] * (2148 - a[1])) > 0 else -1
        w = 2.5
        for t in (0.04, 0.5, 0.96):
            c = (a[0] + d[0] * t + nrm[0] * inward * w, a[1] + d[1] * t + nrm[1] * inward * w)
            post = [(c[0] + (i * u[0] + j * nrm[0]) * 1.5, c[1] + (i * u[1] + j * nrm[1]) * 1.5)
                    for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            bridge.add_shell(prism(post, deck_top, deck_top + rail_h - 0.01))
        s0 = (a[0] + nrm[0] * inward * w, a[1] + nrm[1] * inward * w)
        s1 = (b[0] + nrm[0] * inward * w, b[1] + nrm[1] * inward * w)
        rail = [(s0[0] - nrm[0] * 1.5, s0[1] - nrm[1] * 1.5), (s1[0] - nrm[0] * 1.5, s1[1] - nrm[1] * 1.5),
                (s1[0] + nrm[0] * 1.5, s1[1] + nrm[1] * 1.5), (s0[0] + nrm[0] * 1.5, s0[1] + nrm[1] * 1.5)]
        bridge.add_shell(prism(rail, deck_top + rail_h - 3.0, deck_top + rail_h))
    angle = lowered_angle()
    p0, p1 = hinge()
    from south_gate_walls_geometry import to_world
    return {
        'meshes': {'building-457': leaf_raised(), 'building-058': bridge},
        'ground': {'building-058': {'deck_top': deck_top, 'note': 'deck spans from the gate landing (059) to the '
                                    'south bank plateau (053), both at z=220; native z=0 pillar removed'},
                   'building-457': {'hinge_z': LEAF_BOTTOM, 'note': 'raised leaf stands on the gate threshold'},
                   'building-059': {'z': [216, 220], 'note': 'unchanged native landing / lowered-deck footprint'}},
        'changes': [
            'Raised drawbridge leaf 457 rebuilt as a 4-unit thick plank leaf in front of the gate arch, sized from '
            'native mask 415: x 1095-1166, z 224-309 on the gate front line. The native 80x60 block (z 0-309) '
            'filled the whole passage down to the datum and is removed.',
            'Hinge recorded on 457 (custom property south_gate_state_hinge) along the leaf foot; rotating the '
            f'leaf by {angle:+.0f} degrees about it gives the lowered (Pont_levis applied) pose lying on landing 059.',
            'Footbridge 058 rebuilt from a z=0 pillar into a 6-unit plank deck at z=220 with two railings '
            '(3 posts and a handrail each, rail top 16 above the deck from masks 179/180).',
            'Landing 059 (z 216-220) unchanged: it is the lowered-deck footprint and the rock ledge in the covered art.',
        ],
        'inferred': ['Leaf thickness (4) and rail post/handrail sizes are inferred.',
                     'The diagonal brace under the footbridge (visible at the SE rail) is not modelled.',
                     'Chains and the portcullis behind the leaf (lowered frame) are not modelled; no owned obstacle.'],
        'limitations': [
            'Footbridge 058 is reject-all in source-masks-v1 (terrain group) so it stays neutral gray; native rail '
            'masks 179/180 are unassigned and the deck has no occluder mask. Coordinator: review 058 ownership.',
            'Lowered pose: a 90 degree swing of the 85-unit leaf reaches about 13 native px past the art deck '
            'end onto the footbridge (the art lowered deck is shorter than the raised leaf); geometry keeps one '
            'rigid leaf.',
            'Only the covered (raised) state is projected in the eight-view packet; the lowered state is validated '
            'by the source-camera overlay in inspection/drawbridge-states.png.',
            'The mecanisme patch (doors 11-16) has no obstacle and is not modelled.'],
        'notes': {'building-457': {'role': 'drawbridge leaf (raised pose)'},
                  'building-058': {'role': 'footbridge deck and rails'}},
        'object_properties': {'building-457': {'south_gate_state_hinge': {
            'pivot_native': list(p0), 'axis_end_native': list(p1),
            'pivot_world': list(to_world(p0)), 'axis_end_world': list(to_world(p1)),
            'raised_angle_deg': 0.0, 'lowered_angle_deg': angle,
            'states': {'raised': 'covered.png initial (mask 415, sight obstacle 457 active)',
                       'lowered': 'Pont_levis transition last frame (masks 416/417 applied, obstacle 457 removed)'}}}},
        'states': {'patch-003 Pont_levis': {'raised': 'modelled pose (covered state, obstacle 457)',
                                            'lowered': f'hinge rotation {angle:+.0f} deg, validated by overlay'},
                   'patch-004 mecanisme': 'no obstacle; not modelled'},
    }


BUILDERS = {
    'lincoln-south-gate-drawbridge': drawbridge,
    'lincoln-south-wall-stair': wall_stair,
    'lincoln-south-wall-cone-turret': south_wall_cone_turret,
    'lincoln-south-gatehouse-cone-turret': gate_cone_turret,
    'lincoln-south-gatehouse-west-tower': west_gate_tower,
    'lincoln-south-gatehouse-east-tower': east_gate_tower,
    'lincoln-south-gatehouse-arch': gatehouse_arch,
    'lincoln-south-curtain-wall-west': west_curtain,
    'lincoln-southeast-curtain-wall': southeast_curtain,
    'lincoln-southeast-corner-turret': southeast_corner_turret,
    'lincoln-south-curtain-wall-central': central_wall,
}


def build(asset, trace):
    if asset not in BUILDERS:
        raise KeyError(f'No builder for {asset}')
    return BUILDERS[asset](trace)
