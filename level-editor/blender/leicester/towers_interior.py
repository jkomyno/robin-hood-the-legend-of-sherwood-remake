"""Replace native ladder slabs with open rails and source-visible steps."""
import json
import math
from pathlib import Path
from mathutils import Vector
from towers_hatch import join_beams
from towers import write_mesh, diagnostics


def refine_ladder(obj):
    n = int(obj['source_node'].split('-')[1])
    fractions = {
        181: [0.43 + i * 0.055 for i in range(10)],
        185: [0.08, 0.16] + [0.55 + i * 0.067 for i in range(7)],
        211: [0.06, 0.13, 0.20],
    }[n]
    native = Path(__file__).resolve().parents[3] / 'datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.json'
    points = json.loads(native.read_text())['sight_obstacles'][n]['points']
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    world = [Vector((p['x'], -p['y']/sine, p['z_top']/cosine)) for p in points]
    beams = [(world[0], world[1], 3, 3), (world[3], world[2], 3, 3)]
    for t in fractions:
        beams.append((world[0].lerp(world[1], t), world[3].lerp(world[2], t), 3, 3))
    before = diagnostics(obj)
    write_mesh(obj, *join_beams(beams), obj.name+' open ladder rails and rungs')
    return dict(source_node=obj['source_node'], before=before, after=diagnostics(obj),
                rung_fractions=fractions, world_rail_anchors=[list(p) for p in world],
                evidence='Paired northeast tower source and east-ladders-detail.png: lower ladder ten visible steps; upper ladder seven lower steps plus two hatch steps; inner tower three partial hatch steps.',
                limitations=['Native rail endpoints retained. Source step spacing and three-unit timber section are measured approximations requiring fixed-view review.',
                             'Covered portions retain rails but no invented hidden steps.'])
