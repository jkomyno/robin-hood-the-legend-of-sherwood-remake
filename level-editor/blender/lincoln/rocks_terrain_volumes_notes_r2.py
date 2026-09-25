"""Round-2 (integrated neighbours) review notes for the Lincoln rocks/terrain lane."""

UNHIDE = ('Neighbour-aware unhide: every column of the rebuilt volume (its top and its front face, '
          'z = base..top) is cut below the lowest point that would stand in front of the reviewed '
          'receiver of the neighbouring mesh directly behind it in the integrated round-2 scene '
          '(z-buffer at the source camera). Terrain top heights are otherwise unchanged.')
NO_HIDE = ('Re-audited in the integrated scene: the asset does not stand in front of any neighbour '
           'receiver and its accepted source pixels are unchanged; no geometry change is needed.')
GROUND_REVIEW = ('Blocked on the dedicated terrain ground-domain review: every native mask over the plateau '
                 'belongs to a structure standing on it and the plateau ground itself has no native '
                 'silhouette (re-checked against the round-2 mask manifest v2), so no source texture can be '
                 'accepted without widening masks.')

R2 = {
    'lincoln-stream-west-rock-outcrop': {'changes': [], 'no_change': NO_HIDE,
        'findings': ['Integrated context: no neighbour contacts; audit identical to round 1 (0 hidden receiver pixels).'],
        'audit': 'Unchanged accepted domain; neutral is only the rear face and the bush exclusions.',
        'limitations': ['Back faces are inferred and neutral gray.']},
    'lincoln-stream-south-tree-stump': {'changes': [], 'no_change': NO_HIDE,
        'findings': ['No neighbour interaction; the tree canopy (mask 21) still covers most of the stump.'],
        'audit': 'Visible cut face and bark side accepted; canopy exclusion unchanged.',
        'limitations': ['Stump radius and flare are estimated from the native footprint; partly hidden by the canopy.']},
    'lincoln-west-edge-rocks-north': {'changes': [], 'no_change': NO_HIDE,
        'findings': ['499 px of the audit now fall in neighbouring masks (village fence/bush envelopes) but none '
                     'belongs to a mesh behind the rocks, so nothing is hidden.'],
        'audit': 'Accepted domain unchanged; bush exclusions 27/28 cover most of the painted rock.',
        'limitations': ['Most of the rock is behind foreground bushes; its shape there is inferred.',
                        'Part of 438 lies beyond the left map edge and keeps its native height.']},
    'lincoln-west-edge-rocks-south': {'changes': [], 'no_change': NO_HIDE,
        'findings': ['No neighbour receiver hidden (53 foreign-mask px are envelope overlap only).'],
        'audit': 'Silhouette 128 accepted almost completely.',
        'limitations': ['Node 440 extends beyond the left map edge; that part keeps its native height.']},
    'lincoln-hall-northwest-rocks': {'changes': [], 'no_change': NO_HIDE,
        'findings': ['Refined west hall wall now stands between the view and part of 449/450 (2800 px own '
                     'surface hidden) exactly as in the art; no contact gap.'],
        'audit': 'Masks 134-136 accepted; the hall wall correctly first-hits its own envelope.',
        'limitations': ['449 floor height (z 15) is a measured estimate from the painted foot.']},
    'lincoln-castle-hill-inner-bailey-plateau': {
        'changes': ['062 front band: in addition to the round-1 wall rule, ' + UNHIDE,
                    'Resolves round-2 finding: the south-west part of 062 west of the gatehouse stood in front '
                    'of the refined moat-bank cliff rocks (envelope 265), the landing 414 and the courtyard '
                    'south-wall props, hiding their painted receivers (20,332 px before).',
                    'Faces ordered by projection-island height so the frozen ownership atlas stays within '
                    'its 16384-pixel limit (no geometric effect).'],
        'no_change': NO_HIDE,
        'findings': ['Before: 20,332 px of neighbour receivers hidden, mostly the SW moat-bank cliff (265) '
                     'behind 062\'s south-west rim; the refined south/east walls now meet the receded front.'],
        'audit': 'Cliff faces accepted from 259/260; plateau courtyard ground stays neutral (no native silhouette).',
        'limitations': ['Plateau courtyard top has no native silhouette; it needs the ground-domain review.']},
    'lincoln-castle-hill-north-bailey-plateau': {'status': 'fix-needed', 'audit_status': 'FAIL', 'changes': [],
        'no_change': 'Top and outline are consistent with the art; ' + GROUND_REVIEW,
        'findings': ['No neighbour receiver hidden in the integrated scene (0 px).', GROUND_REVIEW],
        'audit': GROUND_REVIEW, 'audit_limitations': ['Needs the terrain ground-domain review.'],
        'limitations': [GROUND_REVIEW]},
    'lincoln-castle-hill-keep-plateau': {'status': 'fix-needed', 'audit_status': 'FAIL', 'changes': [],
        'no_change': 'Top and outline are consistent with the art; ' + GROUND_REVIEW,
        'findings': ['810 px of the hall/keep receivers are hidden behind 066 where the refined hall/keep '
                     'feet now sit above the plateau rim; left for the ground-domain review together with '
                     'the plateau (geometry intentionally not changed while the asset is blocked).',
                     GROUND_REVIEW],
        'audit': GROUND_REVIEW, 'audit_limitations': ['Needs the terrain ground-domain review.'],
        'limitations': [GROUND_REVIEW, '066 hides 810 px of hall/keep receivers at its rim (to fix with the ground review).']},
    'lincoln-castle-hill-west-plateau': {
        'changes': ['065: ' + UNHIDE + ' Removes the rim that stood in front of the refined bastion and '
                    'round-tower receivers (282/283, 411, 249).', 'Face order for atlas packing (no geometric effect).'],
        'no_change': NO_HIDE,
        'findings': ['With the western complex trimmed, 065 now shows 4.6k source pixels (377 in round 1); the '
                     'bastion lower rooms are the terrace volumes 060/069 which overlap 065 in only 6 cells, so '
                     'the plateau does not need further trimming around them (west-lane request checked).'],
        'audit': 'Envelope 265 accepted where 065 is front-most; bastion walls excluded.',
        'limitations': ['Plateau top has no native silhouette (ground-domain review).',
                        'Envelope 265 is composite with the nine cliff-rock nodes.']},
    'lincoln-castle-hill-east-slope': {
        'changes': ['064: ' + UNHIDE, 'Face order for atlas packing (no geometric effect).'],
        'no_change': NO_HIDE,
        'findings': ['The refined east gate towers/curtain now stand on 064/062 with the front band receded '
                     '(about z 206 at the east gate south tower; painted rock foot z ~195).'],
        'audit': 'Cliff silhouette 260 accepted; slope grass has no silhouette.',
        'limitations': ['Slope grass top has no native silhouette (ground-domain review).']},
    'lincoln-south-ravine-cliff-ledge': {
        'changes': ['070: ' + UNHIDE + ' (no column needed lowering); rebuilt with the round-2 recipe.'],
        'no_change': NO_HIDE,
        'findings': ['No neighbour receiver hidden (0 px); refined south curtain feet meet the ledge top.'],
        'audit': 'Cliff silhouettes 259/260 accepted.',
        'limitations': ['Transparent native volume; composite cliff masks require first-hit gating.']},
    'lincoln-south-bank-plateau': {
        'changes': ['053/063: ' + UNHIDE + ' 063 recedes where it stood in front of the SE outcrop '
                    '(129-131) and the castle cliff (259/260); 053 where it covered the SW cliff rocks (265) '
                    'and the bridge arch 152.'],
        'no_change': NO_HIDE,
        'findings': ['Before: 3,651 px of neighbour receivers hidden by the bank tops.'],
        'audit': 'Bank tops accepted from 268/269.',
        'limitations': []},
    'lincoln-southwest-road-slope': {'changes': [], 'no_change': NO_HIDE,
        'findings': ['Only 47 px (055) of the refined bridge receiver are touched; below the review threshold.'],
        'audit': '054 accepted from 269; 055 has no native silhouette.',
        'limitations': ['055 is reject-all (no native silhouette).']},
    'lincoln-southwest-cliff-road': {
        'changes': ['052/057 (previously native): ' + UNHIDE + ' The road ledge block reached north under the '
                    'painted cliff; its back now recedes to the cliff foot. Top height unchanged (z 150).'],
        'no_change': NO_HIDE,
        'findings': ['Before: 6,329 px of the SW cliff rock receivers (envelope 265) and the bridge arch hidden '
                     'behind the road ledge.',
                     'Grouping: 057 is the northern half of the ravine bridge deck; grouping-proposal.json moves '
                     'it to lincoln-southwest-ravine-bridge (user feedback on the bridge card).'],
        'audit': '052 accepted from 263; 057 has no native silhouette.',
        'limitations': ['057 is reject-all (no native silhouette).']},
    'lincoln-southwest-ravine-bridge': {
        'changes': ['Parapets 074 and 076 were datum pillars reaching native z 0 through the ravine; they now '
                    'stand on the bridge deck/road surfaces (056, 057, 052-055; never below z 150) with their '
                    'native sloped tops (074 z ~158-202, 076 z ~155-191).',
                    'Deck 056 and arch wall 075 keep their native volumes (the painted arch wall reaches the '
                    'ravine floor).'],
        'no_change': NO_HIDE,
        'user_feedback': {
            'exact_text': 'lincoln-southwest-ravine-bridge: feedback \u2014 weird split more should be part of this moedl [review e5878d87184efa8a]',
            'addressed': ('The deck stopped halfway because node 057, catalogued under the cliff-foot road, is '
                          'the northern half of the painted bridge deck and carries most of the painted arch '
                          '(bridge silhouette 152). grouping-proposal.json (here and in the cliff-road workspace) '
                          'moves 057 into the bridge; 052 (road ledge), 054/055 (road ramp) and 053 (bank) stay '
                          'road/terrain. The parapet datum pillars were trimmed to sit on the deck. After the '
                          'catalog merge, round 3 should cut the arch passage through 057/075 at the painted '
                          'opening.')},
        'findings': ['Node 057 (cliff-road asset) is the northern half of the bridge deck; see grouping-proposal.json.',
                     '206 px of adjoining road/rock receivers touch the deck edge-on; below threshold.'],
        'audit': 'Arch 075 accepted from 152; deck and parapets have no native silhouette.',
        'limitations': ['Deck 056 and parapets 074/076 are reject-all (no native silhouette).',
                        'The painted arch passage is not cut yet: it lies mostly in 057, which belongs to the '
                        'cliff-road asset until the grouping proposal is merged.']},
    'lincoln-southwest-cliff-upper-rocks': {
        'changes': ['423-426, 431: rebuilt with the round-2 recipe (' + UNHIDE + ')'],
        'no_change': NO_HIDE,
        'findings': ['West-lane request (426 at about z 155 near the bastion east end): 426 is carved to the '
                     'painted cliff silhouette 265 with the bastion walls 282-284 excluded; where the bastion '
                     'wall masonry is painted the rock recedes below the wall foot, reaching z ~106 at its '
                     'lowest outline column, while the crest beside the bastion east end stays at the painted '
                     'rock edge. The art shows rock (not wall) down to that level, so it was not raised.'],
        'audit': 'Envelope 265 accepted; bastion walls excluded.',
        'limitations': ['Bastion wall feet come from the carve against native wall silhouettes, not traced corners.',
                        'Side faces of the carved lattice are faceted.']},
    'lincoln-southwest-cliff-lower-ledges': {
        'changes': ['427-430: rebuilt with the round-2 recipe (' + UNHIDE + ')'],
        'no_change': NO_HIDE,
        'findings': ['22 px residual edge contact with the road ledge only.'],
        'audit': 'Envelope 265 accepted.',
        'limitations': ['Side faces of the carved lattice are faceted.']},
    'lincoln-west-tower-hillside': {
        'changes': ['Round-1 recipe applied to the round-2 (native) baseline: 452/453 carved rocks, 455/456 '
                    'sight volumes receding where they would hide the painted rocks 138/139.'],
        'no_change': NO_HIDE,
        'findings': ['With the west-complex pillars 387/410/411 refined, rock 453 is now visible and accepted '
                     '(~800 px); 452 remains behind the west tower hall roofs as in the art; 455/456 are '
                     'non-solid sight volumes over painted grass slope with no native silhouette.'],
        'audit': '453 accepted from 139; 455/456 neutral (no native silhouette); no neighbour receiver hidden.',
        'limitations': ['455/456 are invisible sight volumes; their shape is the authored collision volume.',
                        '452 is hidden behind the west tower hall roofs from the source camera.']},
    'lincoln-southeast-rock-outcrop': {
        'changes': ['443/444 rebuilt with the round-2 recipe (' + UNHIDE + ')'],
        'no_change': NO_HIDE,
        'findings': ['No neighbour receiver hidden.'],
        'audit': 'Outcrop silhouettes 129-131 accepted.',
        'limitations': ['Part of 443 extends beyond the right map edge and keeps its native height.']},
    'lincoln-southeast-small-rocks': {
        'changes': ['445/446: ' + UNHIDE + ' Trims the rock skirt that covered the bank receiver 268.'],
        'no_change': NO_HIDE,
        'findings': ['Before: 328 px of the south-bank receiver hidden.'],
        'audit': 'Silhouette 132 accepted.',
        'limitations': []},
    'lincoln-castle-inner-rock-spur': {
        'changes': ['432/433: garden walls 212/213/220 and corner tower 322 now support (hide) rock, so the '
                    'spur crest rises to meet the refined upper curtain / garden wall foot (432 up to z ~420; '
                    'west-lane request); ' + UNHIDE,
                    '434: keeps the traced crest beside the keep-annex round turret (~z 383) but recedes where it '
                    'stood in front of the courtyard shed west wall (172/175), the hall east wing (254/413) and '
                    'the annex (256) (courtyard-lane request).',
                    '435: recedes where it stood in front of the hall approach ramp (279) and hall east wing.'],
        'no_change': NO_HIDE,
        'findings': ['Before: 9,751 px of neighbour receivers hidden (ramp 279, hall 254/413, annex 256, shed '
                     '172/175, cottages 166/168).',
                     '465 (provisional member): stands wholly on keep plateau 066 inside the great-hall envelopes; '
                     '176 px of keep receivers touch its top (z 422, matching the hall wing foot 420-430). '
                     'Recommend moving 465 to the great-hall group.'],
        'audit': '432/433 accepted from 267; 434/435 have no native mask; 465 accepted from the hall composite.',
        'limitations': ['434/435 have no matching native mask (reject-all rows unchanged).',
                        '465 assignment to this asset is provisional.']},
    'lincoln-north-outer-plateau': {'changes': [], 'no_change': NO_HIDE,
        'findings': ['Refined north curtain walls expose more of their envelopes over the plateau (64k '
                     'foreign-mask px) but none of it hides a neighbour mesh behind 068.'],
        'audit': 'Ridge silhouette 264 accepted; plateau ground beyond the rim has no silhouette.',
        'limitations': ['Plateau top has no native silhouette (ground-domain review).']},
    'lincoln-north-rock-ridge': {'changes': [], 'no_change': NO_HIDE,
        'findings': ['No neighbour receiver hidden.'],
        'audit': 'Ridge silhouette 264 accepted.',
        'limitations': ['Extends beyond the top map edge.']},
}
