"""Round-4 (masks v4 ground domains 433-452) review notes for the rocks/terrain lane."""

Q = 'shouldn’t there be more texture'
DOMAIN = ('Masks v4 add the reviewed ground/rock domain(s) authored in the ground-domain review '
          '(inspection/ground-domain-<node>.json in the earlier workspace): first-hit painted surface minus every '
          'scenery silhouette and hand carve-outs. The packet now textures the painted ground on this asset.')
NOCHANGE = 'Geometry is unchanged in round 4; only the source domain changed (masks v4).'
FOLIAGE = ('FLAG (unmasked foliage): bushes/tree canopies painted over the ground that have no native silhouette '
           'are inside the domain and now project flat onto the terrain top: ')


def fb(text, how):
    return {'exact_text': text, 'addressed': how}


def entry(nodes, gain, findings, limitations, feedback=None, status=None, audit=''):
    e = {'changes': [], 'no_change': NOCHANGE,
         'findings': [f'{DOMAIN} Nodes: {nodes}. {gain}'] + findings,
         'audit': audit or 'Accepted pixels come from the v4 ground domains plus the earlier native masks; '
                           'rejected front pixels are foreign scenery silhouettes or unowned foliage masks.',
         'limitations': limitations}
    if feedback:
        e['user_feedback'] = feedback
    if status:
        e['status'] = status
    return e


R4 = {
    'lincoln-castle-hill-east-slope': entry('064 (mask v4)', 'Accepted front pixels 174k of 188k (round 3: 11k).',
        [FOLIAGE + 'a few bush clumps on the slope east of the east gate (about 2-3k px).'],
        ['Bush clumps without native silhouettes are textured onto the slope surface (flagged).'],
        fb(f'lincoln-castle-hill-east-slope: approved — {Q} [review 3e2af1130e68cffd]',
           'Yes: the slope grass/rock had no native mask. The v4 ground domain now textures the whole visible '
           'slope (174k accepted front pixels, was 11k).')),
    'lincoln-castle-hill-inner-bailey-plateau': entry('062', 'Accepted 466k of 530k front pixels (round 3: 183k); '
        'courtyard dirt, the cliff faces and the south bank edge are textured.',
        [FOLIAGE + 'small bushes against the curtain walls and cottages (about 1-2k px).',
         'Sawhorse by the thatched cottage carved out (no native mask).'],
        ['Small unmasked bushes along the walls are flattened onto the ground (flagged).']),
    'lincoln-castle-hill-keep-plateau': entry('066', 'Only 1.7k px of the plateau is painted ground visible from '
        'the source camera; the rest is covered by the great hall, keep and garden (their silhouettes, 22k '
        'foreign front px, correctly rejected).',
        ['Now unblocked: no longer reject-all; the remaining gray is surface hidden under buildings in the art.'],
        ['Almost the entire top is under the hall/keep; texture elsewhere is unobservable and stays neutral.'],
        fb('(user comment on the keep/north-bailey plateaus, relayed by the coordinator) shouldn’t there be more '
           'texture', 'The painted ground now has a reviewed domain; only 1.7k px of the plateau is actually visible '
           'in the art, the rest lies under the hall and keep.')),
    'lincoln-castle-hill-north-bailey-plateau': entry('067', 'Accepted 239k of 298k front pixels (was 0).',
        [FOLIAGE + 'the tree/bush fringe along the north curtain and around the NE tower (roughly 5-10k px of '
         'foliage texture on the yard edge).', 'Cart wheel/timber/barrel group carved out; hutches and props '
         'with native silhouettes stay excluded; 071 marker remains buried.'],
        ['Unmasked foliage at the yard edges is textured onto the plateau top (flagged).'],
        fb('(user comment on the keep/north-bailey plateaus, relayed by the coordinator) shouldn’t there be more '
           'texture', 'Unblocked: the whole visible north-bailey yard now receives its painted ground.')),
    'lincoln-castle-hill-west-plateau': entry('065', 'Accepted 8.4k of 15k front pixels (round 3: 0.5k).',
        ['Most of 065 is covered by the western complex; remaining rejects are bastion/round-tower silhouettes.'],
        ['Most of the plateau lies under the western complex and stays neutral.'],
        fb(f'lincoln-castle-hill-west-plateau: approved — {Q} [review c20b863af31bad70]',
           'The plateau rim and the cliff behind the bastion now take their painted ground/rock (8.4k accepted '
           'px, was 0.5k); the remainder is hidden under the western complex in the art.')),
    'lincoln-castle-inner-rock-spur': entry('434, 435', 'Accepted 42k of 71k front pixels (round 3: 34k).',
        ['434 domain includes the lowest band of its south face where rock meets the painted courtyard ground '
         '(a few rows of ground texture on rock, flagged).', FOLIAGE + 'one bush beside the shed on 434 (<1k px).'],
        ['434/435 texture comes from authored domains, not native silhouettes.',
         '465 is covered by great-hall envelopes (provisional member; move to the great-hall group recommended).'],
        fb(f'lincoln-castle-inner-rock-spur: approved — {Q} [review e497b0ff342d5a0b]',
           'Rock masses 434/435 had no native mask; their v4 domains add ~8.5k px. Much of the spur is behind '
           'the hall, ramp and inner gate in the art, so those faces remain neutral.')),
    'lincoln-north-outer-plateau': entry('068', 'Accepted 175k of 299k front pixels (round 3: 102k).',
        [FOLIAGE + 'large autumn tree/bush masses north of the curtain walls that are not in any native mask '
         '(tens of thousands of px): they now appear as foliage texture flat on the plateau top. Proper fix '
         'would be foliage proxy geometry (outside this lane).'],
        ['Significant unmasked foliage textured onto the plateau top (flagged; needs foliage proxies).']),
    'lincoln-north-rock-ridge': entry('061', 'Accepted 62k of 78k front pixels (round 3: 39k).',
        [FOLIAGE + 'shrubs on the ridge crest (a few k px).'], ['Extends beyond the top map edge.']),
    'lincoln-south-bank-plateau': entry('053, 063', 'Accepted 656k of 698k front pixels (round 3: 503k).',
        ['Remaining rejects are the SE rock/bush exclusions.'], []),
    'lincoln-south-ravine-cliff-ledge': entry('070', 'Accepted 49.3k of 51k front pixels.', [], []),
    'lincoln-southwest-cliff-road': entry('052', 'Accepted 48k of 52k front pixels (round 3: 27k).', [], []),
    'lincoln-southwest-ravine-bridge': entry('056, 057, 074, 076', 'Accepted 19.5k of 19.9k front pixels '
        '(round 3: 3.7k): road deck, both parapets and the arch wall are textured.',
        ['No foreign scenery on the deck; deck is painted road dirt and the parapets painted stone.'],
        ['Arch passage interior and depth are inferred (only the east opening is painted).'],
        fb(f'lincoln-southwest-ravine-bridge: needs refinement — {Q} [review 3b246100cd17b71e]',
           'Yes: deck 056/057 and parapets 074/076 had no native mask. Their reviewed v4 domains now texture the '
           'whole visible bridge (19.5k of 19.9k front px accepted, was 3.7k). Geometry unchanged from round 3.')),
    'lincoln-southwest-road-slope': entry('054, 055', 'Accepted 60k of 61k front pixels (round 3: 8.6k).', [], [],
        fb('lincoln-southwest-road-slope: approved — why so much model and so little texture? '
           '[review 1db892295df2dbb8]', 'The road ramp now has its ground domain (60k accepted px, was 8.6k).')),
    'lincoln-west-tower-hillside': entry('456', 'Accepted 7.4k of 13k front pixels (round 3: 0.8k).',
        ['452 stays behind the west tower hall roofs; 455 not front-most.'],
        ['455/456 are sight volumes; 456 now carries the painted slope surface it stands in.'],
        fb(f'lincoln-west-tower-hillside: approved — {Q} [review 35995394f306410a]',
           'Sight volume 456 now receives the painted hillside (v4 domain); rock 453 kept its native mask; the rest '
           'is hidden by the western complex.')),
}
