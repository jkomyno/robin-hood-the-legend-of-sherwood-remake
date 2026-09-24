"""Western tower fortified terrace (bastion) south of the round tower.

Artwork measurements (covered.png, native pixel = (x, y - z)):
- 411 is a C-shaped outer wall and plain parapet (no crenels; the parapet cap is
  one continuous lit band) with the cap at native z 245. The paved roof 410 is
  the native slab z 217-220 inside it.
- The outer faces visibly continue down the cliff. Masonry feet read from the
  artwork: front corner (516,1804) at pixel y ~1665 (z ~139), (348,1770) at
  ~1657 (z ~113), (297,1774) at ~1655 (z ~119), east end (629,1780) where the
  masonry meets the grass at ~1625 (z ~155). The terrain lane's ledge volumes
  427/429/426 share these outer vertices at z 95-127; the chosen feet sit a few
  units below both the artwork foot and the ledge top so the wall is embedded
  in the rock (no floating gap). The hidden north-west return at the round
  tower (385,1565) stops at z 200 inside the western slope (456 top z 219).
- Interior (revealed by Patch02, hidden in the covered state): lower room floors
  60/69 at native z 147, partition walls 412/413 from those floors to the roof
  underside (z 217). The revealed artwork shows an arched doorway at the south
  end of 412: door leaf 462 (closed, covered-state Patch08 initial) fills it from
  the floor (z 147) to the arch (z 200); 414 is the lintel above (z 200-218,
  native). 463 is the open leaf (Patch08 applied), native sloped top.
- 409 is a small reject-all interior step at the round-tower foot (native tops
  z 147-156), kept as a closed block from z 140.
"""
from west_complex_geom import Shape, native_obstacles, points, prism

ROOM_FLOOR_Z = 147.0
ROOF_UNDERSIDE_Z = 217.0

# 411 outline, native order: outer face east->west->north, then inner face back.
# Foot heights (native z) chosen per vertex from artwork + terrain ledge contact.
WALL_FEET = {
    (629, 1780): 150.0, (516, 1804): 125.0, (348, 1770): 105.0, (297, 1774): 100.0,
    (256, 1739): 95.0, (280, 1713): 110.0, (267, 1621): 100.0, (314, 1570): 115.0,
    (385, 1565): 200.0, (389, 1575): 200.0, (323, 1580): 115.0, (282, 1623): 100.0,
    (295, 1716): 110.0, (274, 1739): 95.0, (302, 1765): 100.0, (357, 1760): 105.0,
    (517, 1794): 125.0, (626, 1769): 150.0,
}


def _poly(obstacles, node):
    return [(x, y) for x, y, _, _ in points(obstacles, node)]


def build(asset):
    if asset != 'lincoln-west-tower-terrace':
        raise KeyError(asset)
    obstacles = native_obstacles()
    wall = points(obstacles, 411)
    feet = []
    for x, y, _, _ in wall:
        key = min(WALL_FEET, key=lambda k: (k[0] - x) ** 2 + (k[1] - y) ** 2)
        if (key[0] - x) ** 2 + (key[1] - y) ** 2 > 4:
            raise ValueError(f'No measured foot for 411 vertex {(x, y)}')
        feet.append(WALL_FEET[key])
    shapes = {
        411: prism([(x, y) for x, y, _, _ in wall], feet, 245.0),
        410: prism(_poly(obstacles, 410), ROOF_UNDERSIDE_Z, 220.0),
        60: prism(_poly(obstacles, 60), 125.0, ROOM_FLOOR_Z),
        69: prism(_poly(obstacles, 69), 95.0, ROOM_FLOOR_Z),
        412: prism(_poly(obstacles, 412), ROOM_FLOOR_Z, ROOF_UNDERSIDE_Z),
        413: prism(_poly(obstacles, 413), ROOM_FLOOR_Z, ROOF_UNDERSIDE_Z),
        414: prism(_poly(obstacles, 414), 200.0, 218.0),
        462: prism(_poly(obstacles, 462), ROOM_FLOOR_Z, 200.0),
    }
    pts = points(obstacles, 463)
    shapes[463] = prism([(x, y) for x, y, _, _ in pts], ROOM_FLOOR_Z, [zt for *_, zt in pts])
    pts = points(obstacles, 409)
    shapes[409] = prism([(x, y) for x, y, _, _ in pts], 140.0, [zt for *_, zt in pts])
    info = {
        'ground_native_z': {
            'building-411': 'per-vertex wall feet on the cliff rock, z 95-150 (z 200 at the hidden return into the west slope)',
            'building-410': 'roof slab z 217-220 carried by the walls',
            'building-060': 'lower-room floor top z 147, fill from z 125', 'building-069': 'lower-room floor top z 147, fill from z 95',
            'building-412': ROOM_FLOOR_Z, 'building-413': ROOM_FLOOR_Z, 'building-462': ROOM_FLOOR_Z,
            'building-463': ROOM_FLOOR_Z, 'building-414': 200.0, 'building-409': 140.0},
        'states': {'building-462': 'closed door (covered state, Patch08 initial); hide_render False',
                   'building-463': 'open door (Patch08 applied, reject-all); hide_render False as delivered, kept unchanged',
                   'Patch02': 'roof slab 410 and parapet 411 cover the interior rooms 60/69/409/412/413/414/462/463'},
        'changes': [
            'Removed the z 0 datum pillars from every part.',
            'Outer wall/parapet 411 rebuilt as one closed C-shaped wall: plain parapet cap z 245 (no crenels in the artwork), outer faces continuing down the cliff to per-vertex feet z 95-150 measured from the artwork masonry foot and the terrain ledge contacts; hidden north-west return stops at z 200 in the western slope.',
            'Paved roof 410 kept as the native z 217-220 slab spanning the interior.',
            'Lower rooms: floors 60/69 rebuilt as closed fills topped at z 147 (were z 0-147 pillars); partition walls 412/413 now run from the room floor z 147 to the roof underside z 217 instead of z 0.',
            'Door 462 (closed) rebuilt as the leaf of the arched doorway at the south end of 412, z 147-200 (revealed artwork); lintel 414 kept at z 200-218; open leaf 463 now stands on the room floor with its native sloped top; 409 closed block z 140-156.'],
        'limitations': [
            'Interior rooms (60, 69, 409, 412, 413, 414, 462, 463) are hidden under Patch02 in the covered state; their shapes follow native footprints and the revealed artwork but are not reviewed revealed-state receivers.',
            'Covered-state mask 418 (closed bastion door, Patch08 initial) is a sprite drawn over the roof paving and parapet; physically the door lies inside the bastion, so its mask pixels are first hit by 410/411 and 462 receives no covered-state texture. Coordinator: the door belongs to a revealed/interior state packet.',
            'Wall feet are embedded a few units below the terrain-lane ledge tops (427/429/426); the east end (629,1780) foot z 150 is below terrain 426 (z 195 there) although the artwork shows masonry down to z ~155, so the terrain lane may need to lower that grass slope.',
            'West plateau volume 65 (z 220) overlaps the bastion interior footprint; the lower rooms (z 147-217) lie inside it. Terrain lane / coordinator should trim 65 around the bastion interior.',
            'Masonry courses, drains and stonework are projected texture on flat faces.'],
    }
    return shapes, info
