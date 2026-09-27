"""Compile inspected Sherwood ownership rules with explicit unknown coverage.

An unresolved receiver gets a black bitmap. The shared source-mask API otherwise
leaves missing targets unconstrained, which is never acceptable for this scene.
This can produce an audit preview before all assignments are resolved; the report
explicitly prevents that preview from being used as a completed synthesis source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

EDITOR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EDITOR/'refinement/blender'))
from occlusion_constraints import SourceMaskConstraints, evidence_record

DEFAULT_RECIPE = Path(__file__).with_name('source-mask-candidates.json')
DEFAULT_GROUPING = EDITOR/'work/sherwood-refinement/grouping-review'
NATIVE = EDITOR.parent/'datadirs/fullgame_gog_hackable/Data/Levels/Sherwood.rhp.d/masks/manifest.json'
SOURCE = EDITOR.parent/'datadirs/fullgame_gog_hackable/Data/Levels/Day/sherwood.map.png'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def load_image(path):
    return np.asarray(Image.open(path).convert('L')) > 0


def effective_rule(candidate, reason=None):
    node = candidate['source_node']
    if candidate.get('reviewed') is not True or reason:
        return dict(source_node=node, reviewed=True, mask_indices=[10000],
                    ownership_status='unresolved', reason=reason or 'Assignment not inspected')
    if not isinstance(candidate.get('inspection'), dict):
        raise ValueError('Missing assignment inspection evidence: '+node)
    if candidate['inspection'].get('source_sha256') != sha(SOURCE):
        raise ValueError('Inspected artwork changed: '+node)
    if candidate['inspection'].get('inventory_sha256') != sha(NATIVE):
        raise ValueError('Inspected native inventory changed: '+node)
    inspected = candidate['inspection'].get('mask_sha256', {})
    card = candidate['inspection'].get('card')
    if not card or sha(EDITOR/card) != candidate['inspection'].get('card_sha256'):
        raise ValueError('Inspected assignment image changed or is missing: '+node)
    native = {r['index']: r for r in json.loads(NATIVE.read_text())['masks']}
    for index in candidate['mask_indices'] + candidate.get('exclude_mask_indices', []):
        if inspected.get(str(index)) != sha(NATIVE.parent/native[index]['png']):
            raise ValueError('Inspected native bitmap changed or is unbound: '+str(index))
    return {**candidate, 'ownership_status': 'reviewed'}


def verify_coverage(constraints, objects):
    missing = [o['name'] for o in objects if constraints.for_object(o) is None]
    if missing:
        raise ValueError('Unconstrained source receivers: '+', '.join(missing))
    return len(objects)


def main(recipe_path, grouping, output):
    recipe_path, grouping, output = map(lambda p: Path(p).resolve(), (recipe_path, grouping, output))
    output.mkdir(parents=True, exist_ok=True)
    recipe = json.loads(recipe_path.read_text())
    approval = json.loads((grouping/'grouping-approval.json').read_text())
    if approval['status'] != 'GROUPING_APPROVED':
        raise ValueError('Grouping is not approved')
    geometry = json.loads((grouping/'geometry.json').read_text())
    plan = json.loads((grouping/'plan.json').read_text())
    inventory = json.loads(NATIVE.read_text())
    for record in inventory['masks']:
        record['png'] = str((NATIVE.parent/record['png']).resolve())
    Image.new('L', (1, 1), 0).save(output/'unresolved.png')
    inventory['masks'].append(dict(index=10000, box_top_left=[0, 0], box_size=[1, 1], png='unresolved.png',
                                   purpose='Explicitly unknown source ownership; never unconstrained'))
    write(output/'inventory.json', inventory)
    by_node = {r['source_node']: r for r in recipe['assignments']}
    if len(by_node) != len(recipe['assignments']):
        raise ValueError('Duplicate recipe source node')
    nodes = sorted({r['source'] for r in geometry})
    assignments = []
    for node in nodes:
        candidate = by_node.get(node, {'source_node': node})
        reason = recipe['unresolved'].get(node)
        if node == 'ground':
            reason = 'Ground requires a separate terrain-domain and foreground-exclusion audit'
        if node == 'foliage-foreground-oak':
            reason = 'Canopy is a separate original animation layer, not Day artwork'
        assignments.append(effective_rule(candidate, reason))
    manifest = dict(version=1, mask_inventory='inventory.json', projections={
        'exterior': dict(source_sha256=sha(SOURCE), state=recipe['state'], assignments=assignments)})
    write(output/'source-masks.json', manifest)
    constraints = SourceMaskConstraints(output/'source-masks.json', 'exterior', sha(SOURCE),
                                        Image.open(SOURCE).size, image_loader=load_image)
    receivers = [dict(name=r['name'], source_node=r['source'], asset_group=plan['assignments'][r['name']],
                      projection_component=r['name'] if r['source'] in {'building-024', 'building-102'} else None)
                 for r in geometry]
    verify_coverage(constraints, receivers)
    unknown = {r['source_node']: r['reason'] for r in assignments if r['ownership_status'] == 'unresolved'}
    counts = {node: sum(r['source'] == node for r in geometry) for node in nodes}
    report = dict(status='PARTIAL_AUDIT' if unknown else 'MASK_ASSIGNMENTS_COMPLETE', synthesis_ready=not unknown,
        source_sha256=sha(SOURCE), recipe_sha256=sha(recipe_path), grouping_approval_sha256=sha(grouping/'grouping-approval.json'),
        grouped_worker_sha256=sha(grouping/'grouped-source-only.blend'), constrained_receivers=len(receivers),
        unconstrained_receivers=0, reviewed_source_nodes=len(nodes)-len(unknown),
        unresolved_source_nodes=len(unknown), unresolved_meshes=sum(counts[n] for n in unknown),
        unresolved=unknown, evidence=evidence_record(output/'source-masks.json'))
    report['evidence'][str(recipe_path)] = sha(recipe_path)
    for rule in assignments:
        if rule['ownership_status'] == 'reviewed':
            card = (EDITOR/rule['inspection']['card']).resolve()
            report['evidence'][str(card)] = sha(card)
    write(output/'coverage.json', report)
    print(json.dumps({k:v for k,v in report.items() if k not in {'unresolved', 'evidence'}}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recipe', default=DEFAULT_RECIPE)
    parser.add_argument('--grouping', default=DEFAULT_GROUPING)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    main(args.recipe, args.grouping, args.output)
