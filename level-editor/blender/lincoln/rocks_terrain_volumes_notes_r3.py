"""Round-3 (catalog v3 regroup) review notes for the Lincoln rocks/terrain lane."""

BRIDGE_TEXT = ('lincoln-southwest-ravine-bridge: feedback — weird split more should be part of this moedl '
               '[review e5878d87184efa8a]')
GROUND_REVIEW = ('Blocked on the dedicated terrain ground-domain review: every native mask over the plateau '
                 'belongs to a structure standing on it and the plateau ground itself has no native silhouette '
                 '(re-checked against mask manifest v3), so no source texture can be accepted without widening masks.')

R3 = {
    'lincoln-southwest-ravine-bridge': {
        'changes': [
            'Membership (catalog v3): the bridge now owns 056 (southern deck), 057 (northern deck, moved from the '
            'cliff-foot road), 074/076 (parapets) and 075 (arched east wall). No foreign piece is included; 052 '
            '(road ledge), 053 (bank) and 054/055 (road ramp) stay road/terrain.',
            'Arch passage cut through 057 and 075: the painted arch opening was traced on the unmarked covered '
            'art (pixel x 673-708, apex y 1898, visible foot at the grass line) on 075\'s east face and pushed '
            'straight through the bridge perpendicular to that face (exact boolean). Both shells stay closed.',
            'Deck 057 rebuilt from its native volume: its north end, which stood in front of the painted SW cliff '
            'rocks (envelope 265), retreats in a clean straight step (424 cells) instead of the round-2 '
            'per-column sawtooth.',
            'Parapets 074/076 sit on the deck (056/057 tops, never below z 150) instead of on road volumes, which '
            'removes the jagged fringe at their ends.',
            'Working mask row for 057: include the native bridge silhouette 152 (composite with 075, first-hit '
            'gating) so the arch, the opening and the parapet painted over 057 can be accepted.'],
        'no_change': '',
        'user_feedback': {
            'exact_text': BRIDGE_TEXT,
            'addressed': ('The split came from node 057, the northern half of the painted bridge deck, being '
                          'catalogued under the cliff-foot road. Catalog v3 moves it into this asset, so the '
                          'bridge now runs continuously from the south bank to the cliff-foot road, and the '
                          'painted arch passage is now cut through the deck and arch wall.')},
        'findings': ['Neighbour receivers hidden by the bridge: 418 px (was 1,893 with a native 057 deck).',
                     'The painted arch interior (dark stonework) is received by the tunnel faces of 057/075.'],
        'audit': 'Arch wall 075 and deck 057 accepted from bridge silhouette 152; deck 056 and parapets 074/076 '
                 'have no native silhouette and stay neutral.',
        'limitations': ['Deck 056 and parapets 074/076 are reject-all (no native silhouette).',
                        'Arch passage depth and exit are inferred (only the east face opening is painted).']},
    'lincoln-southwest-cliff-road': {
        'changes': [
            'Membership (catalog v3): 057 moved to the ravine bridge; the asset is now the cliff-foot road ledge '
            '052 only.',
            '052 rebuilt with the round-3 recipe: the retreat behind the painted cliff (unhide) now uses a '
            'lower-only 3x3 despike, removing the one-cell sawtooth along the cut edge.'],
        'no_change': '',
        'user_feedback': {
            'exact_text': BRIDGE_TEXT,
            'addressed': ('Feedback on the neighbouring bridge card: node 057 was the northern half of the '
                          'bridge deck. It left this asset in catalog v3; 052 is the road ledge alone.')},
        'findings': ['Neighbour receivers hidden: 114 px (was 1,118).'],
        'audit': '052 accepted from its native rock-slope silhouette 263 (bush 35 excluded).',
        'limitations': []},
    'lincoln-castle-hill-north-bailey-plateau': {
        'status': 'fix-needed', 'audit_status': 'FAIL',
        'changes': [
            'Membership (catalog v3): gains 071, the thin marker slab removed from the NE tower stair (user: '
            '"weird long piece that should not be part of stairs").',
            '071 is a collision-only marker: its native footprint is kept and the slab is sunk to z 137-140 '
            'inside the NE tower footprint, below the plateau top, so it is never visible (1 px in the audit).',
            'Plateau 067 geometry unchanged (native, top z 220).'],
        'no_change': '',
        'user_feedback': {
            'exact_text': 'lincoln-northeast-tower-stair: needs refinement — weird long piece that should not be '
                          'part of stairs [review 317d80bc5dbbecf1]',
            'addressed': ('The long piece (071, a marker slab on the plateau top) now belongs to the north-bailey '
                          'plateau and is sunk out of sight as a collision-only marker.')},
        'findings': ['071 does not change the plateau status: ' + GROUND_REVIEW],
        'audit': GROUND_REVIEW, 'audit_limitations': ['Needs the terrain ground-domain review.'],
        'limitations': [GROUND_REVIEW]},
}
