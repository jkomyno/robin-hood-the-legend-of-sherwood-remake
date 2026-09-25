"""Castle garden terrace, fountain and garden north (back) wall.

Artwork measurements (covered.png, native pixel = (x, y - z)):
- Garden ground: the planted terrace behind the upper curtain walkway is flat at
  native z 390 (native obstacle 416 top). Its fill is hidden below; it rests on
  the keep plateau (native z 220), which is the chosen fill bottom.
- Fountain basin 418: rim top ring matches the native octagon at z 405; the
  front wall foot meets the garden at pixel y ~1182 (z 390 at y 1574). The inner
  back wall shows ~8 px below the rim, so the water surface is set to z 397.
- Statue 419: native mask 331 covers a square two-step plinth (~30 px wide,
  top face at pixel y ~1152-1160) standing in the water, a ribbed square column
  (~15 px wide) and a pointed figure whose top reaches pixel y ~1110 at the
  native centre (917, 1553), i.e. native z ~442.
- Bench 422: seat top z 405 (native thin surface); stone supports reach the
  garden floor at z 390.
- North wall 415/421: coping top z 463 (native), inner face down to the garden
  at z 390. The wall retains the raised garden, so both 415 and the adjoining
  northern block 421 continue down to the keep plateau (z 220) behind it.
- Piers 417/420 stand on the garden floor (z 390) with native sloped caps.
"""
import math

from west_complex_geom import (PLATEAU_Z, Shape, extrude_profile, lathe, native_obstacles,
                               points, prism)

GARDEN_Z = 390.0
WATER_Z = 397.0


def _poly(obstacles, node):
    return [(x, y) for x, y, _, _ in points(obstacles, node)]


def fountain(obstacles):
    basin = _poly(obstacles, 418)
    cx = sum(p[0] for p in basin) / len(basin)
    cy = sum(p[1] for p in basin) / len(basin)
    # Basin: native octagon outer wall, inner wall inset 4 world units to the water.
    inset = []
    for x, y in basin:
        dx, dyw = x - cx, (y - cy) / math.sin(math.radians(35))
        length = math.hypot(dx, dyw)
        k = (length - 4.0) / length
        inset.append((cx + dx * k, cy + (y - cy) * k))
    n = len(basin)
    verts = ([(x, y, GARDEN_Z) for x, y in basin] + [(x, y, 405.0) for x, y in basin]
             + [(x, y, 405.0) for x, y in inset] + [(x, y, WATER_Z) for x, y in inset])
    faces = [list(reversed(range(n)))]                                       # base
    faces += [[i, (i + 1) % n, (i + 1) % n + n, i + n] for i in range(n)]   # outer wall
    faces += [[n + i, n + (i + 1) % n, 2 * n + (i + 1) % n, 2 * n + i] for i in range(n)]  # rim
    faces += [[2 * n + i, 2 * n + (i + 1) % n, 3 * n + (i + 1) % n, 3 * n + i] for i in range(n)]  # inner wall
    faces += [list(range(3 * n, 4 * n))]                                    # water surface
    statue_pts = _poly(obstacles, 419)
    sx = sum(p[0] for p in statue_pts) / 4
    sy = sum(p[1] for p in statue_pts) / 4
    # Statue 419 (mask 331 covers plinth, column and figure): a square plinth
    # stepping out of the water, a ribbed square column and a pointed figure,
    # aligned with the native diamond footprint.
    statue = lathe((sx, sy), [(0, WATER_Z), (15.0, WATER_Z), (15.0, 402.0), (11.0, 402.0),
                              (11.0, 405.0), (6.5, 405.0), (6.5, 432.0), (5.0, 432.0),
                              (5.0, 437.0), (0, 442.0)], segments=4)
    return {418: Shape.of(verts, faces), 419: statue}


def garden(obstacles):
    # Round 2 (integrated context): the refined upper curtain wall stands on a
    # traced south foot at z 392-423 over the rock face. A fill reaching the
    # plateau was exposed below the walkway (its south face, and with a sloped
    # bottom its underside) and received painted rock in the round-2 coverage
    # audit. The garden is therefore a 10-unit terrace slab (z 380-390) held
    # between the curtain wall (south) and the north retaining wall 415, whose
    # feet both lie below it; the mass underneath belongs to the terrain lane
    # (keep plateau z 220 and rock spur 432/433, which must rise to the traced
    # curtain-wall foot).
    poly = _poly(obstacles, 416)  # (1222,1499) (1003,1576) (841,1675) (738,1554) (1120,1409)
    ground = prism(poly, 380.0, GARDEN_Z)
    seat = _poly(obstacles, 422)  # (874,1503) (881,1508) (839,1524) (832,1518)
    edge_a = (seat[0], seat[3])
    edge_b = (seat[1], seat[2])
    bench = extrude_profile(edge_a, edge_b, [
        (0.0, GARDEN_Z), (0.18, GARDEN_Z), (0.18, 401.0), (0.82, 401.0), (0.82, GARDEN_Z),
        (1.0, GARDEN_Z), (1.0, 405.0), (0.0, 405.0)])
    return {416: ground, 422: bench}


def north_wall(obstacles):
    shapes = {415: prism(_poly(obstacles, 415), PLATEAU_Z, 463.0),
              421: prism(_poly(obstacles, 421), PLATEAU_Z, 463.0)}
    for node in (417, 420):
        pts = points(obstacles, node)
        shapes[node] = prism([(x, y) for x, y, _, _ in pts], GARDEN_Z, [zt for *_, zt in pts])
    return shapes


def build(asset):
    obstacles = native_obstacles()
    if asset == 'lincoln-garden-fountain':
        shapes = fountain(obstacles)
        info = {'ground_native_z': GARDEN_Z,
                'changes': [
                    'Removed the datum pillars: basin and statue now stand on the garden floor (native z 390) instead of reaching native z 0.',
                    'Rebuilt basin 418 as a closed octagonal cup: native outer octagon z 390-405, 4-unit rim, water surface at z 397.',
                    'Rebuilt statue 419 as the artwork\'s square two-step plinth (z 397-405) in the water, a square column and pointed figure reaching native z 442 (artwork peak pixel y ~1110).'],
                'limitations': [
                    'Water surface height (z 397) and rim width are estimated from the ~8 px of inner back wall visible in the artwork.',
                    'Statue figure detail (arms, drapery, column ribs) remains projected texture on a square-section proxy.']}
    elif asset == 'lincoln-garden':
        shapes = garden(obstacles)
        info = {'ground_native_z': GARDEN_Z,
                'changes': [
                    'Garden ground 416 trimmed from a native z 0-390 pillar to a 10-unit terrace slab (z 380-390) held between the curtain wall and the north retaining wall; round 2: the former z 220-390 fill showed below the curtain wall\'s raised south foot in the integrated scene and received painted rock.',
                    'Bench 422 rebuilt from a floating 3-unit slab into a closed stone bench: seat top z 405 on two end supports reaching the garden floor at z 390.'],
                'limitations': [
                    'The mass below the garden slab (between the curtain-wall foot and the plateau) is terrain-lane geometry: rock spur 432/433 must rise to the traced curtain-wall foot (z 392-423) or a gap shows under the walkway.',
                    'Planting beds and paths are flat projected texture on the z 390 surface.']}
    elif asset == 'lincoln-garden-north-wall':
        shapes = north_wall(obstacles)
        info = {'ground_native_z': {'415': PLATEAU_Z, '421': PLATEAU_Z, '417': GARDEN_Z, '420': GARDEN_Z},
                'changes': [
                    'Wall 415 and northern block 421 rebuilt as closed prisms from the keep plateau (z 220) to the coping (z 463) instead of the z 0 datum.',
                    'Piers 417 and 420 rebuilt as closed prisms standing on the garden floor (z 390) with their native sloped caps.'],
                'limitations': [
                    'The north face below the garden level is not visible in the covered artwork; continuing it to the plateau is inferred from the retaining role.',
                    'Coping, ivy and trellis detail are projected texture on flat wall faces.']}
    else:
        raise KeyError(asset)
    return shapes, info
