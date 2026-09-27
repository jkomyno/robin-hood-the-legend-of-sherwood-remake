"""Explicit floor continuations where terrain stops at an asset's frontage."""
import json
import math
from pathlib import Path

from terrain_clip import prism


def load_contacts():
    return json.loads(Path(__file__).with_name('floor-contacts.json').read_text())['contacts']


def extension(identity, positions, contact):
    """Bound an inferred floor to one asset; never extend a terrace globally."""
    z = contact['floor_game_z'] / math.cos(math.radians(35))
    x0, y0 = [min(p[k] for p in positions)-1 for k in (0, 1)]
    x1, y1 = [max(p[k] for p in positions)+1 for k in (0, 1)]
    a, b, c, d = (x0,y0,z), (x1,y0,z), (x1,y1,z), (x0,y1,z)
    triangles = [[a,b,c], [a,c,d]]
    source = 'asset-floor:'+identity
    return dict(contact, source=source, height_scene=z, triangles=triangles)


def cutters(record):
    return [prism(triangle, record['source']) for triangle in record['triangles']]
