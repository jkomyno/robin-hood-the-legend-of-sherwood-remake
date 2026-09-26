"""Measured Lincoln village geometry, per canonical source node.

``build(asset_id)`` returns ``{source_node: [(label, vertices, faces), ...]}`` in world
coordinates plus a notes dict.  Pure Python; consumed by ``refine_village.py`` and by
offline overlay checks against ``source-states/covered.png``.
"""
import math

from village_shapes import SIN, COS  # noqa: F401
from village_shapes import mound, extrude_between, hip_roof, ring, bowl, loft  # noqa: E402
from village_shapes import lathe as _lathe  # noqa: F401,E402
from village_shapes import (Frame, extrude, frame_box, box, lathe, post, merge, roof_halves,
                            gable_walls, add, sub, mul, lerp, unit, length, weld)

GROUND_Z = 0.0  # Village terrain is the flat map ground plane (lincoln Terrain ground, Z = 0).


def _house(frame, x0, x1, depth, ridge_y, ridge_z, front, back, thickness, gable_overhang,
           bulge=0.0, steps=1, x_over=None):
    xo0, xo1 = x_over if x_over else (x0 - gable_overhang, x1 + gable_overhang)
    fr, bk, under = roof_halves(frame, xo0, xo1, ridge_y, ridge_z, front, back, thickness, bulge, steps)
    walls = gable_walls(frame, x0, x1, depth, under(0.0), under(depth), ridge_y, under(ridge_y))
    return walls, fr, bk


def northwest_cottage():
    # Front (south) wall ground line measured from the native obstacle and the
    # artwork wall foot; the gable at x < 0 lies beyond the western map edge.
    f = Frame((0.7, -612.1, 0.0), (92.8, 14.3))
    walls, front, back = _house(f, 0.0, 93.9, 94.4, ridge_y=53.0, ridge_z=141.4,
                                front=(-1.0, 74.5), back=(98.5, 60.0), thickness=4.0,
                                gable_overhang=13.0, bulge=1.5, steps=3)
    return {'building-000': [('timber walls', *walls)],
            'building-002': [('front thatch slope', *front)],
            'building-001': [('rear thatch slope (inferred)', *back)]}, {
        'ground_z': GROUND_Z,
        'inferred': ['Rear thatch slope and rear wall are not visible from the source camera; the rear eave follows the native obstacle height.',
                     'The western gable lies beyond the map edge; its overhang mirrors the measured eastern overhang.']}


def ladder_cottage():
    f = Frame((228.4, -580.7, 0.0), (146.4, 86.2))
    walls, front, back = _house(f, -4.5, 167.0, 114.1, ridge_y=67.2, ridge_z=110.5,
                                front=(-6.0, 63.0), back=(121.0, 63.0), thickness=7.0,
                                gable_overhang=4.0, bulge=2.5, steps=3)
    # Chimney stack on the rear slope beside the west ridge end; the native
    # sight pillar reached the ground through the roof.
    chimney = frame_box(f, 20.5, 33.5, 50.5, 63.0, 88.0, 126.0)
    cap = frame_box(f, 19.5, 34.5, 49.5, 64.0, 126.0, 129.5)
    # Porch: small gable roof perpendicular to the house over the door, on two posts.
    p = Frame((233.0, -547.0, 0.0), (0.4903, -0.8716))  # porch axis points out of the front wall (-ey)
    pl, pr, _ = roof_halves(p, 0.0, 36.0, 0.0, 80.0, (-22.0, 46.0), (22.0, 49.0), 3.0)
    # porch roof built in a frame whose x runs outward from the wall; halves are
    # left (006) and right (005) slopes seen from the front.
    post_l = post(f.at(3.0, -4.5, 0.0), f.at(3.0, -4.5, 50.0), 2.4)
    post_r = post(f.at(40.0, -4.5, 0.0), f.at(40.0, -4.5, 51.0), 2.4)
    finial = post(f.at(168.0, 67.2, 100.0), f.at(168.0, 67.2, 123.0), 1.6)
    lumber = extrude(Frame((261.6, -421.6, 0.0), (-97.3, 69.2)),
                     # Round 2 (user: "that wall piece shouldn't be part of the house"): a
                     # free-standing low dry-stone wall behind the rear eave, on the native
                     # footprint with battered faces; proposed as its own asset.
                     [(0.0, 0.0), (15.5, 0.0), (13.2, 36.0), (2.3, 36.0)], 0.0, 140.0)
    return {'building-003': [('timber walls', *walls)],
            'building-004': [('front thatch slope', *front), ('rear thatch slope', *back),
                             ('east ridge finial post', *finial)],
            'building-007': [('chimney stack on the roof', *merge(chimney)), ('chimney cap', *cap)],
            'building-006': [('porch roof west slope', *pl)],
            'building-005': [('porch roof east slope', *pr)],
            'building-008': [('porch west post', *post_l)],
            'building-009': [('porch east post', *post_r)],
            'building-041': [('free-standing dry-stone wall behind the rear eave', *lumber)]}, {
        'ground_z': GROUND_Z,
        'inferred': ['Rear thatch slope and rear wall are hidden; heights follow the native obstacle.',
                     'The damaged thatch opening with exposed rafters under the ladder is left as projected texture.',
                     'The ladder has no sight obstacle and remains projected texture on the front slope.']}


def west_cottage():
    # Long axis runs south -> north along the ridge; the visible eastern slope is
    # the frame front (y = 0), the hidden western slope the back.
    f = Frame((66.8, -1060.9, 0.0), (38.5, 170.0))
    walls, front, back = _house(f, 0.0, 170.3, 106.4, ridge_y=60.0, ridge_z=132.5,
                                front=(-12.0, 85.0), back=(114.0, 94.0), thickness=6.0,
                                gable_overhang=0.0, bulge=1.5, steps=3, x_over=(-6.0, 173.5))
    chimney = box((11.1, -1025.5, 118.0), (12.6, -2.8, 0.0), (2.9, 13.4, 0.0), (0.0, 0.0, 32.2))
    finial = post(f.at(174.0, 60.0, 128.0), f.at(174.0, 60.0, 145.0), 1.8)
    return {'building-010': [('timber walls', *walls), ('eastern thatch slope', *front),
                             ('north ridge finial post', *finial)],
            'building-011': [('western thatch slope (hidden)', *back)],
            'building-012': [('stone chimney on the western slope', *chimney)]}, {
        'ground_z': GROUND_Z,
        'inferred': ['The western slope and west wall face away from the source camera; their eave height follows the native obstacle.',
                     'The chimney base is embedded in the thatch; the native sight pillar reached the ground inside the house.']}


def open_barn():
    # Frame: x along the ridge from the south-west gable, y from the visible
    # south-east eave (y = 0) to the rear eave (y = 185.2).
    f = Frame((325.9, -1170.1, 0.0), (106.2, 131.1))
    L = 168.7
    front, back, under = roof_halves(f, -3.0, L - 0.5, 99.2, 165.3, (0.0, 71.0), (185.2, 69.6), 8.0,
                                     bulge=3.0, steps=3)
    posts_front = merge(post(f.at(2.0, 23.0, 0.0), f.at(2.0, 23.0, under(23.0) + 1), 2.6),
                        post(f.at(154.0, 23.0, 0.0), f.at(154.0, 23.0, under(23.0) + 1), 2.6),
                        post(f.at(0.0, 99.2, 160.0), f.at(0.0, 99.2, 187.0), 2.2),
                        post(f.at(L - 6.0, 99.2, 160.0), f.at(L - 6.0, 99.2, 186.0), 2.2))
    # South-west gable: a diagonal brace (visible from the rear eave post down to
    # the front post) carries the king post under the ridge.
    brace = extrude_between([f.at(-1.5, 185.0, 48.0), f.at(1.5, 185.0, 48.0), f.at(1.5, 185.0, 52.0), f.at(-1.5, 185.0, 52.0)],
                            [f.at(-1.5, 24.0, 11.0), f.at(1.5, 24.0, 11.0), f.at(1.5, 24.0, 15.0), f.at(-1.5, 24.0, 15.0)])
    king = frame_box(f, -1.5, 1.5, 97.2, 101.2, 28.0, under(99.2) + 1)
    posts_back = merge(post(f.at(-4.3, 164.0, 0.0), f.at(-4.3, 164.0, under(164.0) + 1), 2.6),
                       post(f.at(152.0, 164.0, 0.0), f.at(152.0, 164.0, under(164.0) + 1), 2.6))
    # Plank lean-to against the rear (north-west) side, sloping outward.
    lean = extrude(f, [(184.0, 52.5), (184.0, 59.8), (238.5, 48.8), (238.5, 44.0)], -8.0, 103.0)
    lean_posts = merge(post(f.at(-6.2, 221.0, 0.0), f.at(-6.2, 221.0, 49.0), 2.2),
                       post(f.at(99.0, 228.0, 0.0), f.at(99.0, 228.0, 48.0), 2.2))
    return {'building-015': [('front thatch slope', *front), ('front posts and ridge finials', *posts_front)],
            'building-016': [('rear thatch slope', *back), ('south-west gable brace', *brace),
                             ('south-west gable king post', *king), ('rear posts', *posts_back)],
            'building-014': [('plank lean-to roof', *lean), ('lean-to posts', *lean_posts)],
            'building-022': [('straw heap at the front eave', *mound((329.0, -1071.0, 0.0), f.ex, 40.0, 36.0, 30.0))],
            'building-023': [('straw heap, rear lobe under the roof', *mound((298.0, -1018.0, 0.0), f.ex, 24.0, 26.0, 26.0))]}, {
        'ground_z': GROUND_Z,
        'inferred': ['Post positions come from visible post feet; hidden rear posts mirror them.',
                     'The straw heap follows the native footprint; the part under the roof is hidden and its rounded top is inferred.',
                     'Rafters and the remaining timber frame are left as projected texture on posts and roof.',
                     'The native thatch slopes floated without supports; posts now carry both slopes to the ground.']}


def _slab(frame, x0, x1, pts, thickness):
    """Closed roof slab swept along frame x from an outer (y, z) polyline lowered by thickness."""
    return extrude(frame, list(pts) + [(y, z - thickness) for y, z in reversed(pts)], x0, x1)


def _chimney(M, split_z=72.0):
    def side(z):
        # 30 at the foot, smooth (smoothstep) thinning from z 30 to z 110, 15.8 at the crown.
        t = min(1.0, max(0.0, (z - 30.0) / 80.0))
        return 30.0 - (30.0 - 16.6) * t * t * (3 - 2 * t) - 0.8 * max(0.0, z - 110.0) / 40.0

    def centre(z):
        return (528.0 + 1.5 * z / 150.0, -722.0, z)

    def ring_at(z):
        c = centre(z)
        h = side(z) / 2
        return [add(c, add(mul(M.ex, sx * h), mul(M.ey, sy * h))) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    zs = [0.0, 15.0, 30.0, 40.0, 50.0, 60.0, split_z]
    zu = [split_z, 80.0, 90.0, 100.0, 110.0, 125.0, 150.0]
    return loft([ring_at(z) for z in zs]), loft([ring_at(z) for z in zu])


def longhouse():
    # Main range frame M: x from the north-west ridge end towards the south-east
    # hip, y from the ridge (0) towards the rear (+) / front (-).  Wing frame W:
    # x from the main ridge towards the south-west front of the wing, y towards
    # the east (W.y == M.x).
    M = Frame((486.0, -591.0, 0.0), (175.0, -105.0))
    W = Frame((486.0, -591.0, 0.0), (-0.5145, -0.8575))
    t = 7.0
    main_roof = hip_roof(M, 0.0, 214.0, -95.0, 50.0, 61.0, 74.7, 0.0, 126.0, 0.0, 44.0, t)

    def main_under(y):
        return (61.0 + (126.0 - 61.0) * (y + 95.0) / 95.0 if y <= 0 else 126.0 - (126.0 - 74.7) * y / 50.0) - t

    # Walls stop at the eaves; the hipped roof shell closes the attic above them.
    walls = extrude(M, [(-88.0, 0.0), (42.0, 0.0), (42.0, main_under(42.0)), (-88.0, main_under(-88.0))], 60.0, 205.0)
    annex = frame_box(M, -64.0, 60.0, -30.0, 37.0, 0.0, 54.0)
    # Wing slopes keep the measured native ridge and eave lines (they match the
    # artwork silhouette); both are now thick slabs so the cart bay stays open.
    # One closed wing roof: measured west (-70, 73) and east (56.5, 78) eaves, a
    # hip at the rear that dies into the main ridge and covers the annex.
    wing_roof = hip_roof(W, -40.0, 186.0, -70.0, 56.5, 73.0, 78.0, 0.0, 126.0, 40.0, 0.0, t)
    catslide = _slab(W, 1.0, 184.0, [(55.5, 79.0), (74.0, 49.0)], 5.0)
    lean_to = _slab(W, 168.0, 196.0, [(-66.0, 76.0), (-88.6, 60.0)], 5.0)
    # Timber gable infill above the open cart-bay front, under both wing slopes.
    gable = extrude(W, [(-58.0, 74.0), (50.0, 74.0), (50.0, 82.0), (0.0, 118.0), (-58.0, 76.0)], 176.0, 179.0)
    bay_posts = merge(post(W.at(182.0, -35.0, 0.0), W.at(182.0, -35.0, 100.0), 2.6),
                      post(W.at(182.0, 62.0, 0.0), W.at(182.0, 62.0, 57.0), 2.6))
    # External stone chimney (round-2 user feedback): one smooth taper, measured
    # from the per-row width of chimney mask 103 (41 px at the base, 22 px from
    # py 330 up to the top at py 288), square section on the main-range axes.
    chimney_lower, chimney_upper = _chimney(M)
    return {'building-024': [('main range timber walls', *walls)],
            'building-025': [('main range thatch, hipped south-east end', *main_roof)],
            'building-026': [('wing thatch, hipped into the main ridge', *wing_roof), ('wing front gable infill', *gable)],
            'building-027': [('wing east catslide over the chimney yard', *catslide)],
            'building-028': [('west lean-to over the cart bay', *lean_to),
                             ('cart bay posts', *bay_posts)],
            'building-029': [('north-west annex walls (hidden)', *annex)],
            'building-030': [('chimney tapering lower shaft', *chimney_lower)],
            'building-031': [('chimney upper shaft', *chimney_upper)]}, {
        'ground_z': GROUND_Z,
        'inferred': ['The wing bay is open (cart and tub stand under it); only its front posts are visible.',
                     'The annex and the rear main-range wall face away from the camera; they follow the native obstacles.',
                     'Main range and wing roofs are separate closed shells that interpenetrate at the valley.']}


def barrel(base, axis, ref, length_, radius, segments=14):
    """Bulged stave barrel along ``axis`` from ``base``."""
    rings = [(0.0, radius * 0.84), (length_ * 0.2, radius * 0.95), (length_ * 0.5, radius),
             (length_ * 0.8, radius * 0.95), (length_, radius * 0.84)]
    return lathe(base, axis, ref, rings, segments)


def barn_barrels():
    standing = barrel((296.2, -1171.5, 0.0), (0, 0, 1), (1, 0, 0), 29.0, 10.6)
    # Lying barrel: axis follows the long side of the native footprint.
    a = (287.3, -1194.5, 8.2)
    b = (317.7, -1185.0, 8.2)
    axis = sub(b, a)
    lying = barrel(a, axis, (0, 0, 1), length(axis), 8.2)
    return {'building-018': [('standing open barrel', *standing)],
            'building-017': [('barrel lying on its side', *lying)]}, {
        'ground_z': GROUND_Z, 'inferred': ['Hidden rear staves follow the visible barrel profile.']}


def barn_cart():
    # Wheelbarrow-style handcart: tilted slatted tray (020), handles resting on
    # the ground behind it (021) and a loose wheel leaning in front (019).
    tray = extrude_between([(168.0, -1032.0, 0.5), (195.0, -1052.0, 0.5), (195.0, -1052.0, 8.0), (168.0, -1032.0, 8.0)],
                           [(192.0, -999.0, 18.0), (219.0, -1019.0, 18.0), (219.0, -1019.0, 30.0), (192.0, -999.0, 30.0)])
    rack = extrude_between([(192.0, -999.0, 22.0), (219.0, -1019.0, 22.0), (219.0, -1019.0, 30.0), (192.0, -999.0, 30.0)],
                           [(214.0, -969.0, 0.0), (241.0, -989.0, 0.0), (241.0, -989.0, 6.0), (214.0, -969.0, 6.0)])
    legs = merge(post((175.0, -1030.0, 0.0), (175.0, -1030.0, 4.0), 1.5), post((190.0, -1042.0, 0.0), (190.0, -1042.0, 4.0), 1.5))
    hub = (190.6, -1080.6, 15.3)
    rim_axis = unit((17.0, 27.0, 0.0))
    rim = ring(hub, rim_axis, (0, 0, 1), 11.5, 15.8, 4.4)
    nave = lathe(sub(hub, mul(rim_axis, 3.0)), rim_axis, (0, 0, 1), [(0.0, 2.6), (6.0, 2.6)], 8)
    up = (0.0, 0.0, 1.0)
    side = unit((27.0, -17.0, 0.0))
    spokes = merge(*[post(add(hub, mul(d, 2.4)), add(hub, mul(d, 11.7)), 0.9, 4)
                     for d in (up, mul(up, -1), side, mul(side, -1),
                               unit(add(up, side)), unit(sub(up, side)), mul(unit(add(up, side)), -1), mul(unit(sub(up, side)), -1))])
    wheel = merge(rim, nave, spokes)
    return {'building-020': [('tilted slatted tray', *tray), ('tray feet', *legs)],
            'building-021': [('slatted rack and handles resting on the ground', *rack)],
            'building-019': [('leaning cart wheel', *wheel)]}, {
        'ground_z': GROUND_Z,
        'inferred': ['Tray slats, spokes and load are projected texture on simplified solids.']}


def longhouse_props():
    # Wooden tub (032) and stool (035): measured from the tub rim ellipse and base.
    tub = lathe((468.4, -756.0, 0.0), (0, 0, 1), (1, 0, 0),
                [(0.0, 14.0), (13.0, 14.8), (27.0, 15.6)], 16)
    top = frame_box(Frame((500.5, -765.0, 0.0), (19.0, -3.0)), -9.0, 9.0, -9.0, 9.0, 15.0, 18.0)
    stool_legs = merge(*[post((500.5 + dx, -765.0 + dy, 0.0), (500.5 + dx, -765.0 + dy, 15.0), 1.1, 4)
                         for dx, dy in ((-7, -7), (7, -7), (-7, 7), (7, 7))])
    # Stone cart (033): the native wedge body (load rising to the front) on a
    # large wheel at its east side, front.
    # The native wedge ran 138 units back under the roof; only the front ~70 is
    # visible, so the body is shortened to a plausible cart length.
    body = extrude_between([(460.8, -690.1, 8.0), (408.8, -662.1, 8.0), (408.8, -662.1, 34.0), (460.8, -690.1, 34.0)],
                           [(428.0, -752.0, 5.0), (376.0, -724.0, 5.0), (376.0, -724.0, 49.0), (428.0, -752.0, 49.0)])
    axle = unit((119.0, -63.0, 0.0))
    hub = (433.0, -744.0, 28.0)
    spokes = merge(*[post(add(hub, mul(d, 3.5)), add(hub, mul(d, 22.5)), 1.4, 4)
                     for d in ((0, 0, 1), (0, 0, -1), unit((-63.0, -119.0, 0.0)), unit((63.0, 119.0, 0.0)))])
    wheel = merge(ring(hub, axle, (0, 0, 1), 22.0, 27.5, 4.5), spokes,
                  lathe(sub(hub, mul(axle, 3.5)), axle, (0, 0, 1), [(0.0, 4.0), (7.0, 4.0)], 8))
    back_leg = merge(post((456.0, -686.0, 0.0), (456.0, -686.0, 9.0), 2.0), post((414.0, -665.0, 0.0), (414.0, -665.0, 9.0), 2.0))
    # Log pile (034): two layers of logs along the long side of the native footprint.
    d = unit((27.0, -16.0, 0.0))
    n = (-d[1], d[0], 0.0)
    start = (572.0, -789.0, 0.0)
    logs = []
    for k, (off, z) in enumerate(((3.2, 3.2), (9.6, 3.2), (16.0, 3.2), (22.4, 3.2), (28.8, 3.2),
                                  (6.4, 8.8), (12.8, 8.8), (19.2, 8.8), (25.6, 8.8))):
        b = add(add(start, mul(n, off)), (0.0, 0.0, z))
        logs.append(lathe(add(b, mul(d, 0.5 + (k % 3))), d, (0, 0, 1), [(0.0, 3.2), (29.0, 3.2)], 8))
    # Barrel right of the house (036), from its mask ellipse; the native box was oversized.
    barrel_r = barrel((651.0, -741.6, 0.0), (0, 0, 1), (1, 0, 0), 20.5, 8.2)
    # Stone and firewood heap against the east end wall (037).
    heap = mound((703.0, -676.0, 0.0), (37.0, -24.0, 0.0), 24.0, 12.0, 31.0)
    return {'building-032': [('wooden water tub', *tub)],
            'building-035': [('stool top', *top), ('stool legs', *stool_legs)],
            'building-033': [('stone cart body and load', *body), ('stone cart wheel', *wheel), ('cart rests', *back_leg)],
            'building-034': [('log pile', *merge(*logs))],
            'building-036': [('barrel', *barrel_r)],
            'building-037': [('heap against the east wall', *heap)]}, {
        'ground_z': GROUND_Z,
        'inferred': ['Hidden sides of the tub, cart load and heap mirror their visible halves.',
                     'The stone cart has one visible wheel; the second wheel on its hidden west side is not modelled.']}


def west_yard_props():
    # Split-log stack (013) leaning against the west cottage's south wall.
    stack = extrude_between([(1.0, -1079.0, 0.0), (22.0, -1073.0, 0.0), (22.0, -1073.0, 21.0), (1.0, -1079.0, 21.0)],
                            [(-2.0, -1060.0, 0.0), (17.0, -1055.0, 0.0), (17.0, -1055.0, 31.0), (-2.0, -1060.0, 33.0)])
    # Chopping block (044) with the axe handle standing up from it.
    block = lathe((38.5, -1110.5, 0.0), (0, 0, 1), (1, 0, 0), [(0.0, 7.6), (16.0, 7.0), (17.0, 6.6)], 12)
    axe = post((38.0, -1110.0, 16.0), (45.0, -1112.0, 29.0), 1.2, 5)
    # Hand cart (042 body on 043 wheel): slatted box raised on its axle; the
    # far end rests on two short legs.
    body = box((-20.0, -1227.0, 15.0), (50.0, -24.0, 0.0), (19.0, 39.0, 0.0), (0.0, 0.0, 34.0))
    legs = merge(post((38.0, -1200.0, 0.0), (38.0, -1200.0, 15.5), 1.8), post((26.0, -1224.0, 0.0), (26.0, -1224.0, 15.5), 1.8))
    hub = (4.4, -1243.3, 15.8)
    axle = unit((-6.0, 18.0, 0.0))
    side = unit((18.0, 6.0, 0.0))
    spokes = merge(*[post(add(hub, mul(d, 3.0)), add(hub, mul(d, 12.5)), 1.0, 4)
                     for d in ((0, 0, 1), (0, 0, -1), side, mul(side, -1))])
    wheel = merge(ring(hub, axle, (0, 0, 1), 12.3, 15.8, 4.0), spokes,
                  lathe(sub(hub, mul(axle, 3.0)), axle, (0, 0, 1), [(0.0, 3.0), (6.0, 3.0)], 8))
    return {'building-013': [('split-log stack against the cottage wall', *stack)],
            'building-044': [('chopping block', *block), ('axe handle', *axe)],
            'building-042': [('hand cart slatted body', *body), ('hand cart rests', *legs)],
            'building-043': [('hand cart wheel', *wheel)]}, {
        'ground_z': GROUND_Z,
        'inferred': ['The cart and log stack continue beyond the western map edge; hidden parts mirror the visible ones.',
                     'Only the visible cart wheel is modelled; its twin on the hidden side is not.']}


def _fence(a, b, height, post_height, spacing, thickness=3.0, post_radius=1.6):
    """Wattle panel from ground point a to b with round stakes rising above it."""
    d = sub(b, a)
    L = length(d)
    u = unit(d)
    n = (-u[1], u[0], 0.0)
    panel = box(add(a, mul(n, -thickness / 2)), d, mul(n, thickness), (0.0, 0.0, height))
    count = max(2, round(L / spacing) + 1)
    stakes = [post(add(a, mul(u, L * k / (count - 1))), add(add(a, mul(u, L * k / (count - 1))), (0.0, 0.0, post_height)),
                   post_radius, 5) for k in range(count)]
    return merge(panel, *stakes)


def field_wattle_fence():
    # Round 2: the run now starts at the ladder cottage east gable instead of
    # inside its wall corner (found against the refined neighbour).
    west = _fence((373.1, -492.3, 0.0), (549.5, -198.5, 0.0), 32.0, 42.0, 21.0)
    corner = _fence((549.0, -199.5, 0.0), (580.0, -191.5, 0.0), 32.0, 42.0, 16.0)
    north = _fence((579.5, -192.0, 0.0), (931.0, -359.5, 0.0), 30.0, 42.0, 22.0)
    return {'building-038': [('western wattle run with stakes', *west)],
            'building-039': [('corner wattle panel with stakes', *corner)],
            'building-040': [('northern wattle run with stakes', *north)]}, {
        'ground_z': GROUND_Z,
        'inferred': ['Stake spacing is regularised from the visible stakes; panels are thin closed slabs.']}


# Round 5 (new heightfield terrain, round-4): the painted water surface is the
# terrain stream bed at world Z -58.  The punt floats with BOAT_DRAFT below it.
# Moving a measured object down along the source-camera ray keeps its artwork
# pixels: dY = -dZ * cos35 / sin35.
BOAT_WATER_Z = -58.0
BOAT_DRAFT = 2.0  # inner floor (keel + 4) stays 2 above the water surface
BOAT_REFIT_TO_WATER = True


def stream_boat():
    if BOAT_REFIT_TO_WATER:
        parts, notes = _stream_boat_datum()
        dz = BOAT_WATER_Z - BOAT_DRAFT
        dy = -dz * COS / SIN
        moved = {n: [(label, [(p[0], p[1] + dy, p[2] + dz) for p in v], f) for label, v, f in items]
                 for n, items in parts.items()}
        notes = dict(notes, ground_z=BOAT_WATER_Z, water_z=BOAT_WATER_Z, draft=BOAT_DRAFT,
                     reseat_shift_along_source_ray=[0.0, round(dy, 3), dz])
        return moved, notes
    return _stream_boat_datum()


def _stream_boat_datum():
    # Flat-bottomed punt with raked ends; the gunwale rises towards the north-east
    # end as the native obstacle and the artwork show.  Water level = ground datum.
    f = Frame((428.3, -1284.0, 0.0), (59.0, 108.0))
    L, hw = 124.5, 12.2

    def loop(x0, x1, w, z0, z1):
        return [f.at(x0, -w, z0), f.at(x1, -w, z1), f.at(x1, w, z1), f.at(x0, w, z0)]

    hull = bowl([loop(7.0, L - 7.0, hw - 1.0, 0.0, 0.0),
                 loop(0.0, L, hw, 11.0, 21.0),
                 loop(2.5, L - 2.5, hw - 2.5, 11.2, 20.6),
                 loop(8.0, L - 8.0, hw - 3.5, 4.0, 4.0)])
    thwarts = merge(*[frame_box(f, x, x + 4.0, -hw + 2.5, hw - 2.5, 4.0 + 0.0, 8.5 + 7.0 * x / L)
                      for x in (30.0, 62.0, 94.0)])
    return {'building-051': [('punt hull', *hull), ('punt thwarts', *thwarts)]}, {
        'ground_z': GROUND_Z,
        'inferred': ['The hull underside is below the painted water line and not visible; it follows the raked ends.']}


def north_edge_rock():
    # The obstacle is a rock mass running north-west off the map edge; only its
    # south-east end is visible (mask 126).  No rail-fence geometry belongs to it.
    rock = mound((284.0, -99.0, 0.0), (54.0, 45.7, 0.0), 66.0, 33.0, 50.0, rings=6, segments=16, top=0.5)
    return {'building-437': [('north-edge rock mass', *rock)]}, {
        'ground_z': GROUND_Z,
        'inferred': ['Everything north of the map edge is outside the source; the rock continues as a rounded ridge.']}


BRIDGE_WATER_Z = -58.5  # round 5: terrain stream bed is world Z -58 (native -47.5); pier foot 0.5 below it
# Round 5: fill under the deck ends (outside the abutment faces) down to this
# level so the new terrain's bank trenches (x 0..12 and 156..168) never show a
# gap under the bridge; buried wherever the bank is higher.
# Off by default: the artwork paints grass bank there, so the proper fix is the
# terrain bank rising to the datum; enable only if the terrain keeps the trenches.
BRIDGE_ABUTMENT_FILL = False
BRIDGE_ABUTMENT_FILL_Z = -40.0
# The painted arches and pier reach below the flat ground plane (z = 0) into the
# painted stream channel.  Round 2 (user: "the surface of the bridge is missing as
# is the pillar") enables them; the workspace declares a reviewed ground
# exclusion so the flat plane does not occlude them from the source camera.
# The terrain still needs a stream channel for them to show in the map.
BRIDGE_STREAM_CHANNEL = True


# Round 5 numbered-corner trace of the front parapet west end (source px ->
# front-face frame x, z; scratch/village-r5/west-parapet-trace.json): the painted
# cap drops from the round-3 parabola at x ~25 to the end stone at x -7.7.
BRIDGE_WEST_CAP_TRACE = ((-7.67, 11.36), (3.02, 20.28), (18.46, 31.01))
BRIDGE_WEST_CAP_JOIN = 25.6


def _bridge_curves():
    def cap_parabola(x):
        return 44.0 - 0.0027 * (x - 78.0) ** 2

    def cap_front(x):
        if x >= BRIDGE_WEST_CAP_JOIN:
            return cap_parabola(x)
        pts = list(BRIDGE_WEST_CAP_TRACE) + [(BRIDGE_WEST_CAP_JOIN, cap_parabola(BRIDGE_WEST_CAP_JOIN))]
        if x <= pts[0][0]:
            (xa_, za), (xb_, zb) = pts[0], pts[1]
        else:
            (xa_, za), (xb_, zb) = next((p, q) for p, q in zip(pts, pts[1:]) if p[0] <= x <= q[0])
        return za + (zb - za) * (x - xa_) / (xb_ - xa_)

    def deck(x):
        return max(0.0, cap_front(x) - 9.0)

    def cap_rear(x):
        return 52.0 - 0.0024 * (x - 95.0) ** 2
    return cap_front, deck, cap_rear


def _arc(cx, cz, r, a0, a1, steps):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
             cz + r * math.sin(math.radians(a0 + (a1 - a0) * i / steps))) for i in range(steps + 1)]


def stone_footbridge():
    # Frame B: x along the front (south) face from its west end, y towards the
    # rear parapet.  Arch soffits, pier and caps are measured on the front face.
    B = Frame((628.0, -1090.0, 0.0), (145.0, -93.0))
    cap_front, deck, cap_rear = _bridge_curves()
    w = BRIDGE_WATER_Z
    deck_t = 2.5
    # Deck ends where the underside (deck - 2.5) is 0.5 above the bank datum.
    half = math.sqrt((cap_front(78.0) - 9.0 - deck_t - 0.5) / 0.0027)
    xb = 78.0 + half
    # West end: the deck underside meets the datum at the traced parapet end.
    xa = next(x / 20 for x in range(-600, 1600) if deck(x / 20) - deck_t >= 0.5)
    xs_w = [xa + (85.0 - xa) * i / 16 for i in range(17)]
    xs_e = [85.0 + (xb - 85.0) * i / 16 for i in range(17)]
    # West body: deck underside, west abutment, left arch (springs 18 / 76), half pier;
    # the east arch springs from the pier (95) and the east abutment (150); crowns ~11.
    west = [(x, deck(x) - deck_t) for x in xs_w]
    east = [(x, deck(x) - deck_t) for x in xs_e]
    if BRIDGE_STREAM_CHANNEL:
        # Below the bank datum only the channel masonry is built: arch legs, the
        # pier and 6-unit abutment faces; the banks themselves are terrain.
        fz = BRIDGE_ABUTMENT_FILL_Z if BRIDGE_ABUTMENT_FILL else 0.0
        west += [(85.0, w), (76.0, w)] + _arc(47.0, -18.5, 29.0, 0.0, 180.0, 12) + [(18.0, w), (12.0, w), (12.0, fz), (xa + 10.0, fz)]
        east += [(xb - 10.0, fz), (156.0, fz), (156.0, w), (150.0, w)] + _arc(122.5, -16.5, 27.5, 0.0, 180.0, 14) + [(95.0, w), (85.0, w)]
    else:
        west += [(85.0, 0.0), (xa, 0.0)]
        east += [(xb, 0.0), (85.0, 0.0)]
    # The profiles start with the deck line (x ascending); remove the duplicated corners.
    west = [p for i, p in enumerate(west) if i == 0 or p != west[i - 1]]
    def elevation(points, y0, y1):
        # Side elevation (x along the bridge, z) swept across the bridge width
        # (frame B's y from y0 to y1): frame S has x = B.y and y = -B.x.
        S = Frame(B.o, (B.ey[0], B.ey[1]))
        return extrude(S, [(-x, z) for x, z in points], y0, y1)

    body_w = elevation(west, -1.0, 81.0)
    body_e = elevation(east, -1.0, 81.0)
    deck_w = elevation([(x, deck(x)) for x in xs_w] + [(x, deck(x) - deck_t) for x in reversed(xs_w)], 7.0, 72.0)
    deck_e = elevation([(x, deck(x)) for x in xs_e] + [(x, deck(x) - deck_t) for x in reversed(xs_e)], 7.0, 72.0)
    fx0 = BRIDGE_WEST_CAP_TRACE[0][0]
    fx_w = [fx0 + (85.0 - fx0) * i / 16 for i in range(17)]
    fx_e = [85.0 + 93.0 * i / 12 for i in range(13)]
    front_w = elevation([(x, cap_front(x)) for x in fx_w] + [(x, deck(x) - deck_t) for x in reversed(fx_w)], -1.0, 7.0)
    front_e = elevation([(x, cap_front(x)) for x in fx_e] + [(x, deck(x) - deck_t) for x in reversed(fx_e)], -1.0, 7.0)
    # Round 5: rear parapet ends trimmed to the painted cap ends (source px ~665
    # west, ~812 east); the round-3 ends projected onto bush and bank (267/155 px).
    rx_w = [-5.0 + 90.0 * i / 12 for i in range(13)]
    rx_e = [85.0 + 83.0 * i / 12 for i in range(13)]
    rear_w = elevation([(x, cap_rear(x)) for x in rx_w] + [(x, deck(x) - deck_t) for x in reversed(rx_w)], 72.0, 81.0)
    rear_e = elevation([(x, cap_rear(x)) for x in rx_e] + [(x, deck(x) - deck_t) for x in reversed(rx_e)], 72.0, 81.0)
    return {'building-045': [('west arch, abutment and half pier', *body_w), ('front parapet, west half', *front_w)],
            'building-046': [('east arch, abutment and half pier', *body_e), ('front parapet, east half', *front_e)],
            'building-047': [('rear parapet, west half', *rear_w)],
            'building-048': [('rear parapet, east half', *rear_e)],
            'building-049': [('walking deck, west half', *deck_w)],
            'building-050': [('walking deck, east half', *deck_e)]}, {
        'ground_z': GROUND_Z,
        'stream_bed_z': BRIDGE_WATER_Z, 'stream_channel_variant': BRIDGE_STREAM_CHANNEL,
        'inferred': ['Arch soffits, pier and parapet caps are measured on the front face; the rear face repeats the same arches.',
                     'Arch legs, pier and abutments continue below the bank datum to the painted stream bed (z = -60); the '
                     'terrain needs a stream channel under the bridge for them to show in the integrated map.',
                     'The deck top is reject-all in the mask manifest and stays neutral.']}


def _ladder_all():
    return ladder_cottage()


def ladder_cottage_house():
    # Round 3 (catalog v3): node 041 moved to its own asset; the cottage keeps 003-009.
    parts, notes = _ladder_all()
    parts.pop('building-041')
    return parts, notes


def ladder_cottage_rear_stone_wall():
    parts, notes = _ladder_all()
    return {'building-041': parts['building-041']}, {
        'ground_z': GROUND_Z,
        'inferred': ['Most of the wall runs behind the cottage roof and the bushes; its hidden course and length follow the native footprint.']}


ASSETS = {
    'lincoln-village-ladder-cottage-rear-stone-wall': ladder_cottage_rear_stone_wall,
    'lincoln-village-stone-footbridge': stone_footbridge,
    'lincoln-village-stream-boat': stream_boat,
    'lincoln-village-north-rail-fence': north_edge_rock,
    'lincoln-village-field-wattle-fence': field_wattle_fence,
    'lincoln-village-west-yard-props': west_yard_props,
    'lincoln-village-longhouse-props': longhouse_props,
    'lincoln-village-barn-barrels': barn_barrels,
    'lincoln-village-barn-cart': barn_cart,
    'lincoln-village-longhouse': longhouse,
    'lincoln-village-open-barn': open_barn,
    'lincoln-village-west-cottage': west_cottage,
    'lincoln-village-ladder-cottage': ladder_cottage_house,
    'lincoln-village-northwest-cottage': northwest_cottage,
}


def build(asset_id):
    parts, notes = ASSETS[asset_id]()
    return parts, notes
