"""Reconcile a review manifest with the verified, promoted publication chain."""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def reconcile(stage_directory, manifest_path, evidence_path):
    latest = Path(stage_directory).resolve()
    if read(latest / 'promotion.json')['status'] != 'APPLIED':
        raise ValueError('Only a promoted publication can mark review items integrated')
    for report in ('asset-verification.json', 'handoff-verification.json', 'browser-result.json'):
        if read(latest / report)['status'] != 'PASS':
            raise ValueError('Publication verification incomplete: ' + report)
    manifest = read(manifest_path)
    items = {item['id']: item for item in manifest['items']}
    approvals = {key: item.get('user_approval') for key, item in items.items()}
    evidence = {}
    stage_path = latest / 'stage.json'
    visited = set()
    while stage_path.exists():
        if stage_path in visited:
            raise ValueError('Cyclic publication baseline chain')
        visited.add(stage_path)
        stage = read(stage_path)
        plan = read(stage['plan'])
        for imported, source in zip(stage['imports'], plan['imports'], strict=True):
            if imported['asset_id'] != source['asset_id']:
                raise ValueError('Stage/import plan ordering differs')
            asset = source.get('source_asset_id', source['asset_id'])
            if asset not in items:
                asset = source['asset_id']
            if asset not in items:
                continue
            evidence.setdefault(asset, []).append({
                'stage': str(stage_path),
                'stage_sha256': hashlib.sha256(stage_path.read_bytes()).hexdigest(),
                'source_blend': imported['source_blend'],
                'source_blend_sha256': imported['source_blend_sha256'],
                'source_nodes': source.get('source_nodes'),
                'destination_asset': source['asset_id'],
            })
        baseline = Path(plan['baseline'])
        if plan.get('baseline_sha256') and hashlib.sha256(baseline.read_bytes()).hexdigest() != plan['baseline_sha256']:
            raise ValueError('Publication baseline hash changed: ' + str(baseline))
        stage_path = baseline.parent / 'stage.json'
    coverage = read(latest / 'asset-verification.json')
    generated = {entry['asset_id'] for entry in coverage['asset_material_coverage'] if entry['generated_material_count']}
    for asset, records in evidence.items():
        item = items[asset]
        if item.get('status') != 'approved' or not approvals[asset]:
            raise ValueError('Integration cannot grant missing user approval: ' + asset)
        current = {'publication': str(latest), 'state': 'live', 'handoffs': records}
        if item.get('publication_evidence') != current:
            item.setdefault('publication_status_history', []).append({
                key: item.get(key) for key in ('status', 'ai_texture', 'publication_evidence')})
        item['publication_evidence'] = current
        owner = records[0]['destination_asset']
        item['ai_texture'] = ('Reviewed texture bake integrated; raw output retained. ' if owner in generated else
                              'Integrated; generated texture provenance is not established. ')
        item['ai_texture'] += 'Live in ' + latest.name + '. Unobserved surfaces and preserved source-art limitations remain as documented.'
    assert approvals == {key: item.get('user_approval') for key, item in items.items()}
    Path(manifest_path).write_text(json.dumps(manifest, indent=2) + '\n')
    Path(evidence_path).write_text(json.dumps({'publication': str(latest), 'items': evidence,
        'asset_material_coverage': coverage['asset_material_coverage']}, indent=2) + '\n')
    return {'review_items': len(items), 'integrated_review_items': len(evidence),
            'groups': coverage['groups'], 'groups_with_generated_provenance': len(generated)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage_directory')
    parser.add_argument('manifest')
    parser.add_argument('evidence')
    args = parser.parse_args()
    print(json.dumps(reconcile(args.stage_directory, args.manifest, args.evidence)))
