"""Record completed manual seven-building inspection after immutable proof checks."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
OBSERVATIONS = {
    'front-west-green': 'Front timber gable, open portico, roof and chimney retain the approved exterior; the cut party face and concealed rear remain neutral.',
    'front-brown': 'Timber gable, masonry doorway and barrel are visible and textured. Adjacent-roof occlusion leaves a neutral upper right wall wedge; the base cut is internal.',
    'front-red': 'Dormer, chimney, timber facade and masonry door retain the approved shape and source alignment. Neighbour-hidden roof regions and party faces remain neutral.',
    'front-east-green': 'Green gable and tiled lower entrance are preserved. Rear and partition surfaces remain neutral; no neighbouring rear roof is assigned here.',
    'rear-west-shingle': 'Both visible shingle roof slopes and the narrow exposed timber face match the source. The front-roof occluded region remains neutral.',
    'rear-central-tiled': 'Tall tiled roof and chimney retain the approved profile. The source-hidden lower body and reverse roof face remain neutral.',
    'rear-east-lean-roof': 'The visible low shingle roof and masonry wedge retain their source texture. Native open structural fragment is preserved rather than inventing a closed unseen house.',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    grouped = WORK / 'grouped/nottingham-grouped-v9.blend'
    comparison = json.loads(grouped.with_suffix('.market-validation.json').read_text())
    if comparison['status'] != 'PASS' or comparison['grouped_sha256'] != sha(grouped):
        raise ValueError('Grouped geometry proof changed')
    proposal = json.loads((WORK / 'town-audit/market-seven-building-grouping-proposal.json').read_text())
    if sha(ROOT / proposal['approved_geometry_model']) != proposal['approved_geometry_sha256']:
        raise ValueError('Approved parent changed')
    records = []
    for building in proposal['buildings']:
        identifier = building['proposed_id']
        workspace = WORK / 'round-10/assets' / identifier
        candidate = json.loads((workspace / 'candidate.json').read_text())
        validation = json.loads((workspace / 'validation.json').read_text())
        rgb = json.loads((workspace / 'known-rgb-validation.json').read_text())
        views = json.loads((workspace / 'modified/views.json').read_text())
        if validation['status'] != 'PASS' or rgb['status'] != 'PASS':
            raise ValueError('Workspace validation failed')
        if candidate['model_sha256'] != sha(workspace / 'model.blend') or candidate['modified_views_sha256'] != sha(workspace / 'modified/views.json'):
            raise ValueError('Reviewed packet changed')
        if rgb['packets'][0]['views_sha256'] != candidate['modified_views_sha256']:
            raise ValueError('RGB proof is stale')
        if {v['index'] for v in views['views']} != set(range(8)) or not all(v['counts']['source'] > 0 for v in views['views']):
            raise ValueError('Missing view or source pixels')
        observation = OBSERVATIONS[identifier.removeprefix('nottingham-market-')]
        report = {'version': 1, 'asset_id': identifier, 'status': 'PASS', 'inspected_views': list(range(8)),
                  'method': 'Manual comparison of all eight solid and source-textured views against original market artwork, followed by independent per-pixel source RGB checks.',
                  'observation': observation, 'model_sha256': candidate['model_sha256'], 'views_sha256': candidate['modified_views_sha256'],
                  'solid_sha256': sha(workspace / 'modified/solid.png'), 'textured_sha256': sha(workspace / 'modified/textured.png'),
                  'known_rgb_evidence': 'known-rgb-validation.json', 'grouped_world_geometry_evidence': str(grouped.with_suffix('.market-validation.json')),
                  'known_pixels': rgb['packets'][0]['known_pixels'], 'geometry_approval': 'pending-new-membership-review'}
        (workspace / 'market-review.json').write_text(json.dumps(report, indent=2) + '\n')
        candidate.update(status='ready-for-user', geometry_reviewed=True, geometry_refined=False, inspected_views=list(range(8)),
                         no_change_reason='The fresh V9 baseline already contains the exact approved exterior geometry and disjoint base partition. All eight views validate its new standalone membership; no additional mesh edit is warranted.',
                         review_scope='Grouping-only revision: approved exterior geometry, new disjoint source ownership, eight fixed views and exact source RGB.',
                         independent_source_review='market-review.json')
        (workspace / 'candidate.json').write_text(json.dumps(candidate, indent=2) + '\n')
        (workspace / 'review.md').write_text('# Market building grouping review\n\n' + observation + '\n\nAll eight solid and source-textured views were inspected. Outside objects and frozen input passed preservation guards. Every marked known pixel passed an independent fixed-camera ray and exact source RGB check. The partition source and regrouped scene passed a reopened world-coordinate comparison, with exact topology and UV preservation.\n\nThe earlier whole-terrace approval remains archived. This separate building requires approval of its new ownership and framing. No texture synthesis has started.\n\n' + '\n'.join(candidate['limitations']) + '\n')
        records.append({'asset_id': identifier, 'workspace': str(workspace.relative_to(WORK)), 'status': candidate['status'],
                        'model_sha256': candidate['model_sha256'], 'known_pixels': report['known_pixels']})
    (WORK / 'grouping/market-v9-ready-packets.json').write_text(json.dumps({'status': 'PASS', 'catalog': 'grouping/catalog-v9.json', 'packets': records}, indent=2) + '\n')
    print(json.dumps({'ready_packets': len(records), 'known_pixels': sum(r['known_pixels'] for r in records)}))


if __name__ == '__main__':
    main()
