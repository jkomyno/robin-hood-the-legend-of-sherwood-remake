"""Collect Leicester worker handoffs without promoting incomplete work to approval.

Each completed worker writes handoff.json with status, notes, recipe, ownership,
and optionally revealed_solid/revealed_textured/revealed_context paths. Paths in
handoff.json are relative to the worker directory. Unprepared jobs remain listed
in progress.json, never masquerade as completed gallery candidates.

Recording a future explicit user decision (never infer one from review status):
copy the asset's revision.sha256 from review-candidates.json into a JSON file:
{"version": 1, "decisions": [{"asset_id": "<stable asset ID>",
 "scope": "geometry", "decision": "approved",
 "revision_sha256": "<exact revision.sha256>",
 "exact_user_text": "<verbatim explicit user approval>"}]}
Use "rejected" for rejection. Append later decisions; the last per asset wins.
Invoke with --decisions PATH to persist this file as OUTPUT/decisions.json;
subsequent runs load that default automatically. Changed models, recipes,
sheets, handoffs or reports invalidate prior decisions. Decision records and
actual reviewed evidence are archived before approved cards are hidden.
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_review_gallery import build


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement'))
from review_evidence import (sha, load_decisions, bind_decision, archive_decisions,
                             archive_reviewed_revision, material_evidence)


def collect(catalog_path, assets, output, decisions_path=None, ground_workspace=None):
    catalog = json.loads(catalog_path.read_text())
    if catalog['map'] != 'Leicester':
        raise ValueError('Expected Leicester catalog')
    output.mkdir(parents=True, exist_ok=True)
    groups = [{**g, 'workspace': assets / g['id']} for g in catalog['groups']]
    if ground_workspace is not None:
        ground_workspace = Path(ground_workspace).resolve(strict=True)
        ground = json.loads((ground_workspace / 'workspace.json').read_text())
        if ground.get('map_name') != 'Leicester' or ground.get('part_ids') != ['ground']:
            raise ValueError('Supplemental ground workspace must own only Leicester ground')
        if ground['asset_id'] in {g['id'] for g in groups}:
            raise ValueError('Ground workspace duplicates a catalog asset')
        groups.append({'id': ground['asset_id'], 'name': 'Ground Background (Planar Receiver)',
                       'workspace': ground_workspace, 'supplemental': True})
    decision_path = decisions_path if decisions_path is not None else output / 'decisions.json'
    records = load_decisions(decision_path, {g['id'] for g in groups})
    items, progress = [], []
    for group in groups:
        workspace = group['workspace']
        handoff_path = workspace / 'handoff.json'
        entry = {'id': group['id'], 'name': group['name'], 'workspace': str(workspace),
                 'supplemental': group.get('supplemental', False)}
        if not handoff_path.exists():
            progress.append({**entry, 'status': 'refinement-in-progress' if workspace.exists() else 'not-prepared'})
            continue
        handoff = json.loads(handoff_path.read_text())
        status = handoff['status']
        if status not in ('ready-for-user', 'fix-needed', 'validation-pending'):
            raise ValueError(f'Unsupported handoff status for {group["id"]}: {status}')
        item = {**entry, 'status': status, 'notes': handoff['notes'], 'user_approval': 'pending'}
        for key, relative in {
            'solid': 'modified/solid.png', 'textured': 'modified/textured.png',
            'context': 'input/context.png', 'validation': 'validation.json', 'review': 'review.md',
            'ownership': handoff['ownership'],
        }.items():
            item[key] = str((workspace / relative).resolve(strict=True))
        for key in ('revealed_solid', 'revealed_textured', 'revealed_context'):
            if handoff.get(key):
                item[key] = str((workspace / handoff[key]).resolve(strict=True))
        validation = json.loads(Path(item['validation']).read_text())
        if status == 'ready-for-user':
            if validation.get('status') != 'PASS':
                raise ValueError(f'Failed validation cannot be ready: {group["id"]}')
            if not handoff.get('all_eight_views_inspected'):
                raise ValueError(f'Missing visual review: {group["id"]}')
            if handoff.get('has_revealed_state') and not all(key in item for key in
                    ('revealed_solid', 'revealed_textured', 'revealed_context')):
                raise ValueError(f'Missing revealed-state evidence: {group["id"]}')
        material_path = workspace / 'inspection/stored-materials/audit.json'
        model_sha256 = sha(workspace / 'model.blend')
        item['worker_status'] = status
        material_files, material_errors, material = material_evidence(
            workspace, material_path, workspace / 'modified/views.json', model_sha256, 'stored_material')
        states = handoff.get('stored_material_states', [])
        if handoff.get('has_revealed_state') and not states:
            material_errors.append('missing actual-material display-state audits')
        seen_states = set()
        item['stored_material_states'] = []
        for state in states:
            state_id = state['id']
            if not re.fullmatch(r'[a-zA-Z0-9_-]+', state_id) or state_id in seen_states:
                raise ValueError('Invalid or duplicate material state ID')
            seen_states.add(state_id)
            state_audit = (workspace / state['audit']).resolve()
            state_frame = (workspace / state['frame_manifest']).resolve()
            if not state_audit.is_relative_to(workspace.resolve()) or not state_frame.is_relative_to(workspace.resolve()):
                raise ValueError('State material evidence must stay inside workspace')
            files, errors, report = material_evidence(workspace, state_audit, state_frame,
                                                     model_sha256, 'stored_material_' + state_id)
            material_files.update(files)
            material_errors.extend(state_id + ': ' + error for error in errors)
            item['stored_material_states'].append({'id': state_id, 'audit': str(state_audit),
                'sheet': str(state_audit.parent / 'materials.png') if (state_audit.parent / 'materials.png').is_file() else None})
        if handoff.get('has_revealed_state') and not all(any(name.endswith(suffix) for name in seen_states) for suffix in ('-covered', '-revealed')):
            material_errors.append('both covered and revealed actual-material states are required')
        material_pass = not material_errors
        item['stored_material_errors'] = material_errors
        if material_path.is_file():
            item['stored_material_audit'] = str(material_path)
        if (material_path.parent / 'materials.png').is_file():
            item['stored_material_textured'] = str(material_path.parent / 'materials.png')
        if (material_path.parent / 'asset.glb').is_file():
            item['stored_material_glb'] = str(material_path.parent / 'asset.glb')
        item['stored_material_validation'] = 'PASS' if material_pass else 'pending-or-failed'
        if status == 'ready-for-user' and not material_pass:
            item['status'] = 'validation-pending'
            notes = item['notes'] if isinstance(item['notes'], list) else [item['notes']]
            item['notes'] = notes + ['Stored material atlas validation and actual material view review are pending or stale; source-projected sheets do not validate saved UVs.']
        recipe = (workspace / handoff['recipe']).resolve(strict=True)
        evidence = {key: Path(item[key]) for key in (
            'solid', 'textured', 'context', 'validation', 'review', 'ownership',
            'revealed_solid', 'revealed_textured', 'revealed_context') if key in item}
        evidence.update(recipe=recipe, handoff=handoff_path)
        evidence.update(material_files)
        item['revision'] = {'model_sha256': model_sha256,
                            'recipe': str(recipe), 'recipe_sha256': sha(recipe),
                            'handoff_sha256': sha(handoff_path),
                            'evidence': {key: {'path': str(path), 'sha256': sha(path)}
                                         for key, path in evidence.items()}}
        identity = {'asset_id': group['id'], 'model_sha256': item['revision']['model_sha256'],
                    'evidence': {key: value['sha256'] for key, value in item['revision']['evidence'].items()}}
        item['revision']['sha256'] = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        bind_decision(item, records)
        archive_reviewed_revision(output, item, evidence)
        items.append(item)
        progress.append({**entry, 'status': item['status'], 'user_approval': item['user_approval']})
    archive_decisions(output, records)
    if decisions_path is not None:
        (output / 'decisions.json').write_text(json.dumps({'version': 1, 'decisions': records}, indent=2)+'\n')
    manifest = output / 'review-candidates.json'
    without_packets = [p for p in progress if p['status'] in ('refinement-in-progress', 'not-prepared')]
    manifest.write_text(json.dumps({'map': 'Leicester', 'items': items,
                                   'total_groups': len(catalog['groups']),
                                   'supplemental_count': int(ground_workspace is not None),
                                   'without_packets': without_packets}, indent=2) + '\n')
    (output / 'progress.json').write_text(json.dumps({'map': 'Leicester', 'groups': progress,
        'total': len(progress), 'catalog_groups': len(catalog['groups']),
        'supplemental_count': int(ground_workspace is not None),
        'packets': len(items), 'ready': sum(i['status'] == 'ready-for-user' for i in items),
        'geometry_approval': 'approved' if len(items) == len(progress) and items and all(i['user_approval'] == 'approved' for i in items) else 'pending',
        'approved': sum(i['user_approval'] == 'approved' for i in items),
        'rejected': sum(i['user_approval'] == 'rejected' for i in items), 'texture_generation': 'not-started',
        'publication': 'not-started'}, indent=2) + '\n')
    if items:
        build(manifest, output / 'gallery', pending_only=True)
    return {'manifest': str(manifest), 'groups': len(progress), 'packets': len(items)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', type=Path)
    parser.add_argument('assets', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--decisions', type=Path, help='Explicit geometry decision JSON; defaults to OUTPUT/decisions.json')
    parser.add_argument('--ground-workspace', type=Path, help='Separate planar ground packet, outside the obstacle catalog')
    args = parser.parse_args()
    print(json.dumps(collect(args.catalog.resolve(), args.assets.resolve(), args.output.resolve(),
                             args.decisions.resolve(strict=True) if args.decisions else None,
                             args.ground_workspace)))
