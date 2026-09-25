"""Round-2 review records for the Lincoln courtyard lane (pure Python).

Round-2 workspaces are prepared from the integrated round-1 scene, so their
baselines already hold the courtyard recipe's geometry. Assets reviewed
without geometry changes were re-projected with
`refine_courtyard.py --keep-geometry --packet --closeup --audit`; changed ones
with `refine_courtyard.py --packet --closeup --audit`. This writes
source-coverage-audit.json, review.md and candidate.json bound to the current
hashes, citing the round-1 refinement for unchanged assets.

Usage: python3 courtyard_finalize_r2.py --all | <asset-id> [...]
"""
import copy
import json
import sys
from pathlib import Path

import courtyard_finalize as r1

ROUND1 = r1.LINCOLN / 'round-1/assets'
HERE = Path(__file__).resolve().parent

ANNEX = ('Keep-annex neighbours (keep_north lane) intrude into the shed: terrace volumes 222/225 keep their '
         'native front faces at native y ~1502-1507 over x 1746-1922, up to 33 units in front of the shed '
         'back wall (drawn roof/back-wall line y 1519 -> 1472) and through its roof; round turret 206 '
         '(y to 1524) pierces the roof\'s north-west corner. The artwork shows the shed roof complete up to '
         'the castle wall (roof top edge pixel-matched), so the annex faces should sit at or behind the '
         'shed back edge. They occlude ~2,800 own px from the source camera.')
SPUR = ('Rock spur 434 (rocks lane) still spans x 1538-1747, y 1496-1599 up to z 381 in front of the shed\'s '
        'west end wall, which the artwork shows as dark timber; it occludes ~1,900 own px.')
GATE = ('Inner gatehouse tower 130 (east_gate lane) overlaps the privy 196 in plan (x 1957-2001, y 1460-1488); '
        'the artwork shows the privy\'s east face in front of the tower. ~560 own px occluded.')

R2 = {
    'lincoln-courtyard-shed': {
        'findings': [ANNEX, SPUR, GATE],
        'limitations': [ANNEX, SPUR, GATE,
                        '072 has no source-visible surface; it is a sub-surface strip recording the native '
                        'collision footprint (shows as a thin bar in isolated review renders).',
                        'Interior stall artwork inside the open front has no receiver in this asset.'],
    },
    'lincoln-bailey-thatched-cottage': {
        'findings': ['The shingle-cottage band caused by the old 364 box is gone in the integrated scene.',
                     'Its east verge (351) still covers ~250 px of the shingle cottage\'s drawn west gable edge '
                     'from the source camera (1-2 px sliver).'],
        'limitations': ['East verge 351 overlaps a 1-2 px sliver of the shingle cottage\'s drawn west gable.'],
    },
    'lincoln-bailey-shingle-cottage': {
        'changes': [
            'Fence 357 rails re-measured from mask 120 column runs (they were 8-12 units too high in round 1 and '
            'received no texture): top/bottom rails at native 249-252/232-235 (west bay) and 253-247/234-231 '
            '(east bay); rails 4.5 and posts 4 world units thick to match the drawn 4-5 px timbers.',
            'Working masks: stile 122 (thatched-cottage asset, drawn in front of the west corner) added to the '
            'exclusions of 352/353/354 alongside 168.',
            'Roof, walls and chimney unchanged from round 1 (rebuilt identically by the recipe).',
        ],
        'findings': ['The gray roof band from the old 364 box is gone: 364 is now a hidden core.',
                     'Fence rails were misplaced above the drawn rails (fixed).',
                     'Stile 355 occluded the west corner where no exclusion existed (mask fixed).'],
        'limitations': ['~250 px of the drawn west gable edge are covered by the thatched cottage\'s east verge '
                        '351 from the source camera.'],
    },
    'lincoln-bailey-trough': {'findings': [], 'limitations': []},
    'lincoln-bailey-hay-cart': {
        'findings': [],
        'limitations': ['Spindle gaps show ground, so the rack is open rather than a solid panel.'],
    },
    'lincoln-bailey-well': {
        'changes': [
            'Roof posts moved to the drawn posts measured from mask 163 (pixel columns 1724-1727 and '
            '1756-1758, feet at rows 1581/1593 on the rim) and thickened to 3.5 units; round 1 placed the '
            'right post ~4 px east so it covered drawn shaft pixels (red in the round-2 audit).',
            'Shaft and roof unchanged from round 1.',
        ],
        'findings': ['The refitted cameras showed both posts off the drawn posts (fixed).'],
        'limitations': [],
    },
    'lincoln-south-wall-cottage': {
        'findings': ['The curtain pillar occlusion is gone; only 1-2 px slivers along the refined curtain 110 '
                     'crenel caps remain (~1,000 px in the refitted view), i.e. the curtain\'s crenel edges sit a '
                     'pixel or two above the drawn ones.'],
        'limitations': ['Curtain 110 crenel caps occlude 1-2 px slivers of the drawn roof (south_gate lane).',
                        'The south gable runs into the curtain footprint (y ~1978+); hidden behind the curtain.'],
    },
    'lincoln-south-wall-lean-to': {
        'findings': ['The curtain pillar occlusion is gone (16 px remain on the refined curtain 099 edge).'],
        'limitations': [],
    },
    'lincoln-south-wall-thatched-store': {
        'findings': ['The curtain pillar occlusion is gone (54 px on the curtain 099 edge).',
                     'The south lean-to 368 roof (this lane) covers ~190 px of the store\'s drawn west eave '
                     'corner; the two roofs meet there and the store roof is drawn in front.'],
        'limitations': ['South lean-to 368\'s east verge covers ~190 px of the store\'s drawn west eave corner.'],
    },
    'lincoln-southeast-lean-to': {
        'findings': ['The corner-turret pillar occlusion is gone; the refined turret 083 walk edge still '
                     'covers a thin sliver along the roof\'s east edge (~860 px in the refitted view).'],
        'limitations': ['Refined corner turret 083 walk edge covers a thin sliver of the drawn roof '
                        '(south_gate lane).'],
    },
    'lincoln-northeast-yard-hutches': {
        'changes': [
            'Rebuilt from scratch after the user review ("needs refinement - model completely wrong"): the '
            'artwork shows two identical slatted wooden hutches, each a box rotated ~45 degrees in plan on four '
            'short legs under a flat planked lid with a slight overhang that rises slightly to the back corner. '
            'The round-1 model (a full-footprint block with a gabled lid on the inflated obstacle diamond) was '
            'wrong in shape and plan.',
            'Plan measured from the drawn lid corners (east hutch pixels W 2586,672 / N 2598,660 / E 2628,667 / '
            'S 2613,678) with the feet at pixel row ~707 on the plateau: the hutch sits ~10 native units north '
            'of the obstacle diamond. The west hutch is drawn identically, offset (-49,-10) native.',
            'Per hutch (168 east, 169 west): legs 220..227, box 227..247 inset 0.8 units under the lid (corner posts drawn at the lid corners), lid '
            '3 units thick at 249..252.',
        ],
        'feedback': ('needs refinement \u2014 model completely wrong',
                     'Re-examined the artwork from scratch: two separate slatted hutches (count 2, one per native '
                     'node) on legs with flat plank lids, rotated ~45 degrees; rebuilt both from measured lid '
                     'corners and foot rows instead of the obstacle footprints. Silhouette IoU against masks '
                     '185/186 is 0.82 (foliage-excluded pixels on the west hutch stay neutral).'),
        'findings': ['Round-1 hutch shape and plan were wrong (user review); rebuilt.'],
        'limitations': ['Tree foliage 157/161 is drawn over the west hutch; those pixels are excluded and neutral.'],
    },
    'lincoln-northeast-yard-props': {
        'findings': [],
        'limitations': ['179 stays neutral: the pale block drawn ~8 px west of it is not tied to it by any '
                        'reviewed mask.'],
    },
}
for _t in ('west', 'west-middle', 'east-middle', 'east'):
    R2[f'lincoln-archery-target-{_t}'] = {
        'findings': [], 'limitations': ['The disc is painted on the bale surface; no separate disc geometry.']}


def finalize(asset_id):
    spec = R2[asset_id]
    notes = copy.deepcopy(r1.NOTES[asset_id])
    notes['limitations'] = spec['limitations']
    no_change = None
    if 'changes' in spec:
        notes['changes'] = spec['changes']
    else:
        model = ROUND1 / asset_id / 'model.blend'
        no_change = (f"Geometry is the round-1 refinement, reviewed again in the integrated context with the "
                     f"refitted cameras: round-1 workspace {ROUND1 / asset_id}, model sha256 {r1.sha(model)} "
                     f"(recipe {r1.RECIPE}, ready-for-user in round 1). No new contact, gap or foreign-pixel "
                     f"problem required a geometry change. Round-1 changes: " + ' '.join(r1.NOTES[asset_id]['changes']))
    result = r1.finalize(asset_id, round_name='round-2', notes=notes, no_change_reason=no_change,
                         findings=spec['findings'] or ['No new problems in the integrated context.'],
                         auto_stale=False, finalizer=HERE / 'courtyard_finalize_r2.py')
    if 'feedback' in spec:
        path = r1.LINCOLN / 'round-2/assets' / asset_id / 'candidate.json'
        candidate = json.loads(path.read_text())
        candidate['user_feedback'] = {'exact_text': spec['feedback'][0], 'response': spec['feedback'][1]}
        path.write_text(json.dumps(candidate, indent=2) + '\n')
        review = path.parent / 'review.md'
        review.write_text(review.read_text() + f"\n## User feedback\n> {spec['feedback'][0]}\n\n{spec['feedback'][1]}\n")
    return result


if __name__ == '__main__':
    ids = sys.argv[1:]
    if ids == ['--all']:
        ids = json.loads((r1.LINCOLN / 'worker-assignments.json').read_text())['assignments']['courtyard']
    for asset in ids:
        print(json.dumps(finalize(asset)))
