"""Per-asset review notes for the Lincoln rocks/terrain lane (pure data)."""

COMMON_LIMITATIONS = [
    'Covered (exterior) state only; no revealed-state receivers are reviewed for this lane.',
    'Neutral areas outside native silhouettes stay neutral by design; masks were never widened '
    'beyond a native inventory silhouette.',
]

ROCK_CARVE = ('Rebuilt as a closed heightfield solid: the native collision prism is rasterised '
              '(2 native units per cell), every column is lowered to the highest point whose '
              'source pixel lies inside the node\'s reviewed native silhouette (or behind a reviewed '
              'foreground exclusion), then smoothed with rounded shoulders on the camera-facing '
              'and side outlines; the north (back) crest keeps the painted silhouette height. '
              'The rebuilt rock never exceeds the native prism.')
FOLIAGE_MASKS = ('Reviewed foreground foliage exclusions added in the working source-masks.json '
                 '(native bush/tree silhouettes painted over the rock; evidence in '
                 'inspection/mask-review-*.png). Include masks are the frozen reviewed ones.')
TERRAIN_GROUND = ('The plateau top is painted courtyard/ground art that no native silhouette '
                  'covers; it stays neutral until the dedicated terrain ground-domain review.')
TERRAIN_FRONT = ('Front band rebuild: plateau top height is unchanged (native z 220). Only cells '
                 'in a 120-unit band directly south of the south/east (or west) lane walls are '
                 'lowered, and only while their top pixel lands on a reviewed wall silhouette: the '
                 'artwork shows that masonry, so the terrain recedes below the painted wall foot. '
                 'Cells under wall footprints and behind walls keep z 220.')

NOTES = {
    'lincoln-stream-west-rock-outcrop': {
        'changes': ['Replaced the flat 40-unit native prism of node 436 with a carved, rounded '
                    'heightfield boulder that follows the painted silhouette 125. ' + ROCK_CARVE,
                    FOLIAGE_MASKS + ' Masks 17 and 27 (bushes).'],
        'ground': 'Native z = 0 (generic ground plane; no terrain volume under the footprint; the '
                  'painted foot of silhouette 125 matches z 0 within about 8 units).',
        'audit': 'Accepted pixels cover the painted boulder; the reviewed bush exclusions account for '
                 'the magenta areas and the few red pixels are the rounded outline edge.',
        'inferred': 'The back (north) half of the boulder is not visible; it keeps the native crest '
                    'height and slopes down to the native outline.',
        'limitations': ['Back faces are inferred and neutral gray.'],
        'masks': FOLIAGE_MASKS,
    },
    'lincoln-stream-south-tree-stump': {
        'changes': ['Replaced the square 24-unit box with a round flared stump (16 segments, '
                    'world-space round) inscribed in the native footprint of node 454.'],
        'ground': 'Native z = 0 (grass beside the stream).',
        'audit': 'The stump silhouette 141 is small and mostly covered by the reviewed tree canopy '
                 'exclusion 21 in front of it; the visible cut face and the left bark side are accepted.',
        'inferred': 'The cut top and the rear bark are inferred; the stump is a simple frustum.',
        'limitations': ['Stump radius and flare are estimated from the 25x25 native footprint; the painted '
                        'stump is partly hidden behind the tree canopy (mask 21).'],
        'masks': 'Frozen row unchanged (include 141, exclude 21).',
    },
    'lincoln-west-edge-rocks-north': {
        'changes': ['Nodes 438/439 rebuilt as carved, rounded heightfield rocks. ' + ROCK_CARVE,
                    FOLIAGE_MASKS + ' Masks 27 and 28 (bushes).'],
        'ground': 'Native z = 0 at the western map edge.',
        'audit': 'The painted rocks are largely covered by the bushes 27/28, which are reviewed '
                 'exclusions; the remaining red area is outline slack at the map edge.',
        'inferred': 'Rock parts hidden under the bushes keep the native top (occlusion is not '
                    'evidence of absence).',
        'limitations': ['Most of the rock is behind foreground bushes; its shape there is inferred.',
                        'Part of 438 lies beyond the left map edge (x < 0) and keeps its native height.'],
        'masks': FOLIAGE_MASKS,
    },
    'lincoln-west-edge-rocks-south': {
        'changes': ['Nodes 440/441/442 rebuilt as carved, rounded heightfield rocks. ' + ROCK_CARVE,
                    FOLIAGE_MASKS + ' Mask 28 (bush).'],
        'ground': 'Native z = 0 at the western map edge.',
        'audit': 'Silhouette 128 is accepted almost completely; neutral areas are hidden rear faces.',
        'inferred': 'Rear faces and the part beyond the map edge are inferred.',
        'limitations': ['Node 440 extends beyond the left map edge; that part keeps its native height.'],
        'masks': FOLIAGE_MASKS,
    },
    'lincoln-hall-northwest-rocks': {
        'changes': ['Nodes 447-451 rebuilt as carved, rounded heightfield rocks. The two large native '
                    'blocks 449/450 shrink to the painted boulders of silhouette 135 (native silhouette '
                    'IoU 0.58 -> 0.82). ' + ROCK_CARVE],
        'ground': 'Native z = 0 for 447, 448, 450 and 451; 449 stands on the hillside with its painted '
                  'foot at native z 15 (measured from the silhouette foot, median 17).',
        'audit': 'Masks 134/135/136 are accepted; composite masks 251/374 of the west hall overlap '
                 '135 only where the hall wall stands in front and is correctly first-hit by the hall.',
        'inferred': 'Rear faces of the boulders are inferred.',
        'limitations': ['449 floor height (z 15) is a measured estimate from the painted foot.'],
        'masks': 'Frozen rows unchanged.',
    },
    'lincoln-southeast-rock-outcrop': {
        'changes': ['Nodes 443/444 rebuilt: the 273-unit native pillars standing through the south '
                    'bank now start on the bank top (z 220) and follow the painted outcrop '
                    'silhouettes 129/130/131 (IoU 0.52 -> 0.77). ' + ROCK_CARVE,
                    FOLIAGE_MASKS + ' Mask 57 (bush).'],
        'ground': 'South bank plateau 063 top, native z 220 (the buried part below it was removed).',
        'audit': 'Outcrop silhouettes are accepted; the right edge is cut by the map border.',
        'inferred': 'Rear (north) face of the outcrop is inferred.',
        'limitations': ['Part of 443 extends beyond the right map edge and keeps its native height.'],
        'masks': FOLIAGE_MASKS,
    },
    'lincoln-southeast-small-rocks': {
        'changes': ['Nodes 445/446 (native 242-unit pillars) rebuilt as small rocks on the bank top that '
                    'follow silhouette 132 (IoU 0.08 -> 0.63). ' + ROCK_CARVE],
        'ground': 'South bank plateau 063 top, native z 220.',
        'audit': 'Silhouette 132 is accepted; its pixels also sit inside the bank terrain silhouette '
                 '268, where the south bank excludes 132 so the rock owns them.',
        'inferred': 'Rear faces inferred.',
        'limitations': [],
        'masks': 'Frozen row unchanged (132).',
    },
    'lincoln-west-tower-hillside': {
        'status': 'fix-needed', 'audit_status': 'FAIL',
        'changes': ['Node 452 (rock behind the west tower hall roof) carved to silhouette 138 with the '
                    'cone-tower roof 291/297 as occluders and bush 84 excluded; node 453 carved to '
                    'silhouette 139 with bush 74 excluded.',
                    'Sight volumes 455/456 lowered wherever their top would hide the painted rocks '
                    '138/139 (otherwise native).'],
        'ground': '452/453 native z = 0 (north slope below the castle); 455/456 keep native base z 0 '
                  'on the western hillside beside the plateau outline.',
        'audit': 'From the source camera 452 is hidden behind the west tower hall roofs 392/388/391 '
                 '(as the catalog notes) and 453 behind the round-tower datum pillar 387 and plateau '
                 '065; 455/456 behind terrace pillars 410/411. Only 14 source pixels reach the packet, '
                 'identical to the input packet.',
        'audit_limitations': ['453 is painted visibly (silhouette 139) but occluded by the west '
                              'complex pillar 387 below its real ground (z < 220): needs the '
                              'west_complex lane datum trim, then a repacket here.'],
        'inferred': 'All four nodes are almost entirely unobserved; shapes follow the native volumes.',
        'limitations': ['Blocked on the west_complex lane: round tower 387 and terrace 410/411 still '
                        'extend to native z 0 and occlude rock 453 and the sight volumes from the '
                        'source camera.',
                        '455/456 are invisible sight volumes; their shape is the authored collision volume.'],
        'masks': 'Rows 452/453 add bush exclusions 84/74.',
    },
    'lincoln-southwest-cliff-upper-rocks': {
        'changes': ['Cliff rock faces 423/424/425/426/431 carved to the moat-bank envelope 265. '
                    'Bastion wall silhouettes 282/283/284 are reviewed exclusions that do not '
                    'support rock, so the cliff recedes below the painted bastion wall feet; '
                    'foliage exclusions 36, 61-66, 72, 73 support (hide) rock. The parts inside '
                    'the cliff road and plateau volumes are removed.'],
        'ground': 'Supporting terrain where present (cliff road 052 top z 150, ledge 057 z 150, '
                  'plateaus 062/065 z 220); elsewhere the native z 0 cliff foot.',
        'audit': 'Envelope 265 is shared by nine nodes and the western plateau front; first-hit '
                 'gating partitions it.',
        'inferred': 'Rear parts of the cliff behind its crest are inferred solid.',
        'limitations': ['Bastion wall feet heights come from the carve against native wall silhouettes, '
                        'not from traced corners.', 'Side faces of the carved lattice are faceted.'],
        'masks': FOLIAGE_MASKS + ' Bastion walls 282/283/284 excluded as foreign structures.',
    },
    'lincoln-southwest-cliff-lower-ledges': {
        'changes': ['Lower ledges 427-430 carved to envelope 265 with the same foliage and bastion '
                    'exclusions as the upper rocks.'],
        'ground': 'Native z = 0 at the foot of the cliff (no terrain volume beneath).',
        'audit': 'Envelope 265 is shared with the upper rocks and the western plateau front.',
        'inferred': 'Rear parts inferred.',
        'limitations': ['Side faces of the carved lattice are faceted.'],
        'masks': FOLIAGE_MASKS,
    },
    'lincoln-castle-inner-rock-spur': {
        'changes': ['432/433 carved to outcrop envelope 267 (tree canopy 154 excluded, south gate tower '
                    '273/277 exclusion kept). 434 trimmed to the bailey plateau and raised to the '
                    'painted rock crest traced beside the keep-annex round turret. 435 and 465 trimmed '
                    'to start on the plateau top (z 220) instead of z 0.'],
        'ground': 'Castle-hill plateaus 062/066 top, native z 220.',
        'audit': '465 is inside composite hall envelopes 254/373/413 and mostly first-hit by the hall '
                 'and keep annex; 434/435 have no native mask (reject-all) and stay neutral.',
        'inferred': 'The spur interior and the parts behind the inner west gate are inferred.',
        'limitations': ['434/435 have no matching native mask (reject-all rows unchanged).',
                        '465 assignment to this asset is provisional (see report).'],
        'masks': 'Rows 432/433 add tree 154; 434/435/465 unchanged.',
    },
    'lincoln-castle-hill-inner-bailey-plateau': {
        'changes': ['Front of plateau 062 in front of the south and east curtain walls recedes to the '
                    'painted wall feet (down to about z 165). ' + TERRAIN_FRONT,
                    'Frozen reject-all row replaced by the native cliff silhouettes 259/260 with the wall '
                    'silhouettes 230-233, 248, 408, 414 and bush 75 excluded.'],
        'ground': 'Top unchanged at native z 220; the carved front band steps down to the painted wall '
                  'feet (about z 165-205).',
        'audit': TERRAIN_GROUND + ' The south and east cliff faces are accepted from 259/260.',
        'inferred': 'The front band surface below the wall feet is a vertical-ish step to the native '
                    'cliff face.',
        'limitations': [TERRAIN_GROUND],
        'masks': 'Include 259/260 (native cliff silhouettes); walls and bush excluded.',
    },
    'lincoln-castle-hill-east-slope': {
        'changes': ['Front band of 064 in front of the east walls recedes where the painted wall masonry '
                    'shows. ' + TERRAIN_FRONT, 'Reject-all row replaced by cliff silhouette 260.'],
        'ground': 'Top unchanged at native z 220.',
        'audit': TERRAIN_GROUND,
        'inferred': 'None beyond the native volume.',
        'limitations': [TERRAIN_GROUND],
        'masks': 'Include 260, walls and bush excluded.',
    },
    'lincoln-south-ravine-cliff-ledge': {
        'changes': ['Ravine ledge 070 front band recedes to the painted wall feet. ' + TERRAIN_FRONT,
                    'Reject-all row replaced by cliff silhouettes 259/260.'],
        'ground': 'Top unchanged at native z 220 (transparent native volume).',
        'audit': 'The ledge lies inside cliff silhouettes 259/260 shared with 062/064.',
        'inferred': 'None beyond the native volume.',
        'limitations': ['Transparent native volume; composite cliff masks require first-hit gating.'],
        'masks': 'Include 259/260, walls and bush excluded.',
    },
    'lincoln-south-bank-plateau': {
        'changes': ['Front band checked against the walls. ' + TERRAIN_FRONT,
                    'Reject-all rows replaced by native terrain silhouettes: 053 <- 269 (bush 60 '
                    'excluded), 063 <- 268 (bushes 57/58 and rock 132 excluded).'],
        'no_change_reason': 'The bank top outlines already follow the painted bank rims (top edge within a '
                            'few pixels of silhouettes 268/269) and no bank column hides wall masonry '
                            '(front carve lowered 0 columns); only the source domain was missing.',
        'ground': 'Top unchanged at native z 220.',
        'audit': 'The bank top is accepted from its native silhouettes 268/269; neutral areas are the '
                 'bank front faces seen edge-on and the map edge.',
        'inferred': 'None beyond the native volume.',
        'limitations': [],
        'masks': 'Native terrain silhouettes 268/269.',
    },
    'lincoln-castle-hill-west-plateau': {
        'changes': ['Plateau 065: cells shared with the bastion lower-room terrace volumes 060/069 '
                    '(floor z 147) are cut out (only 6 cells overlap; the rooms lie almost wholly outside '
                    '065) and the front band recedes where western-complex wall masonry is painted '
                    '(2 columns). Top unchanged at z 220.',
                    'Reject-all row replaced by the moat-bank envelope 265 (foliage and bastion walls '
                    'excluded).'],
        'ground': 'Top unchanged at native z 220; bastion lower rooms stand on their own terrace volumes.',
        'audit': TERRAIN_GROUND + ' The western cliff face is accepted from envelope 265.',
        'inferred': 'None beyond the native volume.',
        'limitations': [TERRAIN_GROUND, 'Envelope 265 is composite with the nine cliff-rock nodes.'],
        'masks': 'Include 265; foliage and bastion walls excluded.',
    },
    'lincoln-castle-hill-keep-plateau': {
        'status': 'fix-needed', 'audit_status': 'FAIL',
        'changes': [], 'no_change_reason': 'Top and outline match the painted plateau beneath the hall and '
                    'keep; no wall masonry is hidden by it and no native silhouette exists to refine against.',
        'ground': 'Top unchanged at native z 220.',
        'audit': 'Every native mask over 066 belongs to a building standing on it; the visible plateau '
                 'is painted courtyard ground with no native silhouette, so no source texture can be '
                 'accepted without widening masks.',
        'audit_limitations': ['Needs the terrain ground-domain review to supply its courtyard ground.'],
        'inferred': 'None.',
        'limitations': ['Reject-all terrain node with no native silhouette: requires the dedicated '
                        'ground-domain review before it can carry source texture.'],
    },
    'lincoln-castle-hill-north-bailey-plateau': {
        'status': 'fix-needed', 'audit_status': 'FAIL',
        'changes': [], 'no_change_reason': 'Native plateau top and outline are consistent with the art; '
                    'no native silhouette exists for its ground.',
        'ground': 'Top unchanged at native z 220.',
        'audit': 'All native masks over 067 are buildings, walls and trees standing on it; the plateau '
                 'ground has no native silhouette.',
        'audit_limitations': ['Needs the terrain ground-domain review.'],
        'inferred': 'None.',
        'limitations': ['Reject-all terrain node with no native silhouette: requires the ground-domain review.'],
    },
    'lincoln-north-outer-plateau': {
        'changes': [], 'no_change_reason': 'Native outline and z 220 top already match the painted rock '
                    'rim of silhouette 264; no wall masonry is hidden by it.',
        'ground': 'Top unchanged at native z 220.',
        'audit': 'Accepted from the native ridge silhouette 264 (trees 41/44/46/47/56 excluded); the '
                 'plateau top beyond the rim is ground without a silhouette.',
        'inferred': 'None.',
        'limitations': [TERRAIN_GROUND],
        'masks': 'Include 264; trees excluded.',
    },
    'lincoln-north-rock-ridge': {
        'changes': [], 'no_change_reason': 'The ridge volume already spans the painted rock ridge of '
                    'silhouette 264 and extends beyond the top map edge.',
        'ground': 'Top unchanged at native z 220.',
        'audit': 'Accepted from silhouette 264 (trees excluded); the part above the map edge is off-image.',
        'inferred': 'None.',
        'limitations': ['Extends beyond the top map edge.'],
        'masks': 'Include 264; trees excluded.',
    },
    'lincoln-southwest-road-slope': {
        'changes': [], 'no_change_reason': 'Road ramp 054/055 outlines and heights follow the painted '
                    'road; nothing hides neighbouring masonry.',
        'ground': 'Native heights unchanged (road ramp up to z 180-220).',
        'audit': '054 is accepted from the western bank silhouette 269 (composite with 053); 055 has no '
                 'native silhouette and stays neutral.',
        'inferred': 'None.',
        'limitations': ['055 is reject-all (no native silhouette).'],
        'masks': '054 <- 269 (bush 60 excluded); 055 unchanged.',
    },
    'lincoln-southwest-cliff-road': {
        'changes': [], 'no_change_reason': 'Cliff road ledge 052/057 heights (z 150) and outlines match '
                    'the painted road ledge.',
        'ground': 'Native heights unchanged (z 150).',
        'audit': '052 is accepted from its native rock-slope silhouette 263 (bush 35 excluded); 057 has '
                 'no native silhouette.',
        'inferred': 'None.',
        'limitations': ['057 is reject-all (no native silhouette).'],
        'masks': '052 <- 263 (bush 35 excluded); 057 unchanged.',
    },
    'lincoln-southwest-ravine-bridge': {
        'changes': [], 'no_change_reason': 'Bridge deck and arch volumes already coincide with the '
                    'painted stone bridge; only its source domain was missing.',
        'ground': 'Native heights unchanged.',
        'audit': 'Arch 075 is accepted from the native bridge silhouette 152; 056/074/076 have no '
                 'native silhouette and stay neutral.',
        'inferred': 'None.',
        'limitations': ['Deck 056 and parapets 074/076 are reject-all (no native silhouette).'],
        'masks': '075 <- 152 (native bridge silhouette).',
    },
}
