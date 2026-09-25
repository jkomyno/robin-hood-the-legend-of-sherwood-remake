"""Reviewed working source-mask changes for the Lincoln rocks/terrain lane (pure data)."""

# Reviewed working source-mask changes for owned nodes. Only native inventory
# silhouettes are used; nothing is widened beyond a native mask. Evidence
# sheets are written by rocks_terrain_volumes_evidence.py into each asset's
# inspection/ directory.
FOLIAGE = ('foreground tree or bush canopy painted over this receiver; the pixels are '
           'foliage colour (low blue), so they are occlusion, not receiver texture')
WALLS = ('curtain wall, gatehouse or landing silhouette standing on the cliff top; those '
         'pixels belong to the neighbouring structure, not to the cliff face')
CLIFF_WALLS = [230, 231, 232, 233, 248, 408, 414]
CLIFF_FOLIAGE = [36, 61, 62, 63, 64, 65, 66, 72, 73]
# node -> {'include': [...] (None keeps the frozen include), 'exclude': [...],
#          'reason': str, 'note': str}
MASKS = {
    # Rock receivers: add foreground foliage exclusions to the frozen rows.
    436: {'exclude': [17, 27], 'reason': FOLIAGE},
    438: {'exclude': [27, 28], 'reason': FOLIAGE},
    439: {'exclude': [27, 28], 'reason': FOLIAGE},
    440: {'exclude': [28], 'reason': FOLIAGE},
    441: {'exclude': [28], 'reason': FOLIAGE},
    442: {'exclude': [28], 'reason': FOLIAGE},
    443: {'exclude': [57], 'reason': FOLIAGE},
    444: {'exclude': [57], 'reason': FOLIAGE},
    452: {'exclude': [84], 'reason': FOLIAGE},
    453: {'exclude': [74], 'reason': FOLIAGE},
    432: {'exclude': [273, 277, 154], 'reason': FOLIAGE + '; 273/277 keep the frozen south gate tower exclusion'},
    433: {'exclude': [273, 277, 154], 'reason': FOLIAGE + '; 273/277 keep the frozen south gate tower exclusion'},
    **{n: {'exclude': CLIFF_FOLIAGE + [282, 283, 284],
           'reason': FOLIAGE + '; 282/283/284 are the bastion wall silhouettes (western complex) painted '
                     'in front of the cliff'} for n in (423, 424, 425, 426, 427, 428, 429, 430, 431)},
    # Terrain receivers (frozen reject-all) given their native terrain silhouettes.
    52: {'include': [263], 'exclude': [35], 'reason': FOLIAGE,
         'note': 'Native terrain silhouette 263: rock slope between the upper cliff road and the lower road, '
                 'drawn on the front face of the road ledge.'},
    53: {'include': [269], 'exclude': [60], 'reason': FOLIAGE,
         'note': 'Native terrain silhouette 269: western south-bank top and its northern rim (IoU 0.95 with the '
                 'node top outline).'},
    54: {'include': [269], 'exclude': [60], 'reason': FOLIAGE,
         'note': 'Native terrain silhouette 269 also covers the road ramp at the western end of the south bank; '
                 'composite with node 053, first-hit gating partitions it.'},
    63: {'include': [268], 'exclude': [57, 58, 132], 'reason': FOLIAGE + '; 132 is the small rock pair standing on the bank',
         'note': 'Native terrain silhouette 268: eastern south-bank top (its top edge follows the node outline '
                 'within a few pixels).'},
    61: {'include': [264], 'exclude': [41, 44, 46, 47, 56], 'reason': FOLIAGE,
         'note': 'Native terrain silhouette 264: northern rock ridge and outer plateau rim; composite with 068.'},
    68: {'include': [264], 'exclude': [41, 44, 46, 47, 56], 'reason': FOLIAGE,
         'note': 'Native terrain silhouette 264: northern rock ridge and outer plateau rim; composite with 061.'},
    62: {'include': [259, 260], 'exclude': CLIFF_WALLS + [75], 'reason': WALLS + '; 75 is ' + FOLIAGE,
         'note': 'Native cliff silhouettes 259/260: the south and south-east castle-hill cliff faces below the '
                 'curtain walls, drawn on the plateau front faces.'},
    64: {'include': [260], 'exclude': CLIFF_WALLS + [75], 'reason': WALLS + '; 75 is ' + FOLIAGE,
         'note': 'Native cliff silhouette 260: south-east cliff face, composite with 062/070.'},
    70: {'include': [259, 260], 'exclude': CLIFF_WALLS + [75], 'reason': WALLS + '; 75 is ' + FOLIAGE,
         'note': 'Native cliff silhouettes 259/260 over the ravine ledge; composite with 062/064.'},
    65: {'include': [265], 'exclude': CLIFF_FOLIAGE + [282, 283, 284],
         'reason': FOLIAGE + '; 282/283/284 are the bastion wall silhouettes',
         'note': 'Moat-bank rock envelope 265 also covers the western plateau cliff face behind the bank rocks; '
                 'composite with nodes 423-431, first-hit gating partitions it.'},
    57: {'include': [152],
         'note': 'Round 3: 057 is the northern half of the ravine bridge deck (catalog v3); native bridge '
                 'silhouette 152 (parapet, arch and arch opening) lies mostly over it. Composite with 075; '
                 'first-hit gating partitions it.'},
    75: {'include': [152],
         'note': 'Native silhouette 152 is the south-western stone arch bridge; node 075 is its arch volume.'},
}
