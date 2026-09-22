"""Source-counted West Tower parapet correction.

This is intentionally a separate checkpoint from the earlier Great Keep
battlement recipe.  It adds only the missing source-visible embrasures on the
three West Tower runs (131--133), preserving the run endpoints and inherited
source UVs.  The interval table is expressed in source-image pixels, just as
the original cutter recipe is; the runner validates each interval against the
selected source segment before changing geometry.
"""
from pathlib import Path
import json, runpy
import bpy

ASSET = 'derby-great-keep-west-tower'
RECIPE = 'great-keep-west-zigzag-v1'

# Existing intervals plus the additional source-visible gaps.  The extra gaps
# are the long uninterrupted embrasures visible on the roof-terrace source
# crop; endpoints are kept in source pixel space so projection stays aligned.
TARGET = {
    131: [
        (4, 11, 16, 15, [(222,230),(240,249),(258,267),(276,283),(294,301)], 27),
        (4, 0, 16, 23, [(215,224)], 27),
        (0, 2, 23, 27, [(244,262)], 27),
    ],
    132: [
        (0, 2, 23, 24, [(368,380),(384,392),(399,410)], 27),
        (82, 78, 32, 41, [(463,480)], 27),
        (41, 42, 78, 74, [(497,511)], 27),
        (52, 61, 66, 65, [(507,515)], 27),
    ],
    133: [
        (4, 0, 11, 15, [(289,299),(307,315)], 27),
    ],
}

def refine():
    working = bpy.data.collections['Derby Working']
    visible = {}
    for number in TARGET:
        node = f'building-{number:03}'
        candidates = [o for o in working.objects if o.type == 'MESH'
                      and o.get('source_node') == node and not o.hide_render]
        if len(candidates) != 1:
            raise ValueError(f'{node}: expected one visible source shell, got {len(candidates)}')
        visible[number] = candidates[0]
        if candidates[0].get('refinement_recipe') not in (None, RECIPE):
            raise ValueError(
                f'{node}: baseline already has {candidates[0].get("refinement_recipe")}; '
                'run this checkpoint from the pre-battlement West Tower worker baseline')
    if all(o.get('refinement_recipe') == RECIPE for o in visible.values()):
        return {'status':'already-applied', 'asset':ASSET}

    # Reuse the audited cutter, which preserves material slots and source UVs.
    cut = runpy.run_path(str(Path(__file__).with_name('derby_asset_east_hall.py')))['_refine']
    report=[]
    for number, source in visible.items():
        if source.get('refinement_recipe') == RECIPE:
            report.append({'source_node': source.get('source_node'), 'status':'already-refined'})
            continue
        result = cut(source, TARGET[number])
        replacement = bpy.data.objects[source['replaced_by']]
        replacement['refinement_recipe'] = RECIPE
        replacement['source_gap_count'] = sum(len(r[4]) for r in TARGET[number])
        replacement['zigzag_phase'] = 'source-endpoint-preserved'
        report.append({'source_node': source.get('source_node'), **result})
    return {'asset': ASSET, 'recipe': RECIPE, 'parts': report,
            'source_gap_counts': {str(k):sum(len(r[4]) for r in v) for k,v in TARGET.items()},
            'projection': 'reproject original source UVs after cut; no synthesized pixels'}
