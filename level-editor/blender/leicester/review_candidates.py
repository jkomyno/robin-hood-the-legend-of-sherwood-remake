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
from endpoint_review import load_endpoint_mapping, endpoint_evidence


def collect(catalog_path, assets, output, decisions_path=None, ground_workspace=None,
            workspace_overrides=None, endpoint_mapping=None):
    catalog = json.loads(catalog_path.read_text())
    if catalog['map'] != 'Leicester':
        raise ValueError('Expected Leicester catalog')
    output.mkdir(parents=True, exist_ok=True)
    groups = [{**g, 'workspace': assets / g['id']} for g in catalog['groups']]
    if workspace_overrides is not None:
        override_path = Path(workspace_overrides).resolve(strict=True)
        overrides = json.loads(override_path.read_text())
        if overrides.get('version') != 1 or not isinstance(overrides.get('workspaces'), dict):
            raise ValueError('Expected workspace overrides version 1 and workspaces mapping')
        by_id = {g['id']: g for g in groups}
        if set(overrides['workspaces']) - set(by_id):
            raise ValueError('Workspace override references unknown catalog asset')
        for asset_id, location in overrides['workspaces'].items():
            if not isinstance(location, str) or not location.strip():
                raise ValueError('Workspace override requires a nonempty path')
            workspace = (override_path.parent / location).resolve(strict=True)
            config = json.loads((workspace / 'workspace.json').read_text())
            if config.get('map_name') != 'Leicester' or config.get('asset_id') != asset_id:
                raise ValueError('Workspace override identity does not match catalog asset')
            by_id[asset_id]['workspace'] = workspace
    if ground_workspace is not None:
        ground_workspace = Path(ground_workspace).resolve(strict=True)
        ground = json.loads((ground_workspace / 'workspace.json').read_text())
        if ground.get('map_name') != 'Leicester' or ground.get('part_ids') != ['ground']:
            raise ValueError('Supplemental ground workspace must own only Leicester ground')
        if ground['asset_id'] in {g['id'] for g in groups}:
            raise ValueError('Ground workspace duplicates a catalog asset')
        groups.append({'id': ground['asset_id'], 'name': 'Ground Background (Planar Receiver)',
                       'workspace': ground_workspace, 'supplemental': True})
    endpoint_specs = load_endpoint_mapping(endpoint_mapping, {g['id'] for g in groups})
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
        try:
            handoff = json.loads(handoff_path.read_text())
        except (ValueError, OSError):
            progress.append({**entry, 'status': 'validation-pending', 'incomplete_packet': True,
                             'missing_evidence': ['valid handoff.json']})
            continue
        required = ['model.blend', 'modified/solid.png', 'modified/textured.png',
                    'input/context.png', 'validation.json', 'review.md']
        required += [handoff.get(key) or '<missing '+key+' declaration>' for key in ('ownership', 'recipe')]
        required += [handoff[key] for key in ('revealed_solid', 'revealed_textured', 'revealed_context') if handoff.get(key)]
        missing = [name for name in required if not (workspace / name).is_file()]
        if missing:
            progress.append({**entry, 'status': 'validation-pending', 'incomplete_packet': True,
                             'missing_evidence': missing})
            continue
        status = handoff.get('status', 'validation-pending')
        if status not in ('ready-for-user', 'fix-needed', 'validation-pending'):
            raise ValueError(f'Unsupported handoff status for {group["id"]}: {status}')
        item = {**entry, 'status': status, 'notes': handoff.get('notes', []), 'user_approval': 'pending'}
        for key in ('source_review', 'texture_issue', 'texture_generation', 'generation_blocked'):
            if key in handoff:
                item[key] = handoff[key]
        if handoff.get('texture_generation') == 'blocked':
            item['generation_blocked'] = True
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
        endpoint_files = {}
        if group['id'] in endpoint_specs:
            records_for_group = endpoint_specs[group['id']]
            if records_for_group[0]['workspace'] != workspace.resolve():
                raise ValueError('Initial endpoint worker must match the catalog workspace')
            paired, endpoint_files, endpoint_errors = endpoint_evidence(records_for_group, group['id'], 'Leicester')
            item['endpoint_reviews'] = paired
            item['endpoint_review_errors'] = endpoint_errors
            if endpoint_errors:
                item['status'] = 'validation-pending'
                item['stored_material_validation'] = 'pending-or-failed'
        elif handoff.get('has_discrete_endpoint_state'):
            item['status'] = 'validation-pending'
            item['endpoint_review_errors'] = ['missing explicit paired endpoint mapping']
        recipe = (workspace / handoff['recipe']).resolve(strict=True)
        evidence = {key: Path(item[key]) for key in (
            'solid', 'textured', 'context', 'validation', 'review', 'ownership',
            'revealed_solid', 'revealed_textured', 'revealed_context') if key in item}
        evidence.update(recipe=recipe, handoff=handoff_path)
        evidence.update(material_files)
        evidence.update(endpoint_files)
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
        if item.get('generation_blocked') or item.get('texture_issue'):
            item['generation_eligible'] = item['publication_eligible'] = False
        archive_reviewed_revision(output, item, evidence)
        items.append(item)
        progress.append({**entry, 'status': item['status'], 'user_approval': item['user_approval']})
    archive_decisions(output, records)
    if decisions_path is not None:
        (output / 'decisions.json').write_text(json.dumps({'version': 1, 'decisions': records}, indent=2)+'\n')
    manifest = output / 'review-candidates.json'
    without_packets = [p for p in progress if p.get('incomplete_packet') or p['status'] in ('refinement-in-progress', 'not-prepared')]
    manifest.write_text(json.dumps({'map': 'Leicester', 'items': items,
                                   'total_groups': len(catalog['groups']),
                                   'supplemental_count': int(ground_workspace is not None),
                                   'without_packets': without_packets}, indent=2) + '\n')
    texture_reports = sorted({p.resolve() for root in (assets.parent / 'textures', assets.parent.parent / 'textures')
                              for p in root.glob('*/generation-*/generation.json')})
    (output / 'progress.json').write_text(json.dumps({'map': 'Leicester', 'groups': progress,
        'total': len(progress), 'catalog_groups': len(catalog['groups']),
        'supplemental_count': int(ground_workspace is not None),
        'packets': len(items), 'ready': sum(i['status'] == 'ready-for-user' for i in items),
        'geometry_approval': 'approved' if len(items) == len(progress) and items and all(i['user_approval'] == 'approved' for i in items) else 'pending',
        'approved': sum(i['user_approval'] == 'approved' for i in items),
        'rejected': sum(i['user_approval'] == 'rejected' for i in items),
        'texture_generation': 'attempts-recorded' if texture_reports else 'not-started',
        'texture_generation_attempts': len(texture_reports),
        'texture_generation_reports': len(texture_reports),
        'publication': 'not-started'}, indent=2) + '\n')
    build(manifest, output / 'gallery', pending_only=True)
    return {'manifest': str(manifest), 'groups': len(progress), 'packets': len(items)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', type=Path)
    parser.add_argument('assets', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--decisions', type=Path, help='Explicit geometry decision JSON; defaults to OUTPUT/decisions.json')
    parser.add_argument('--ground-workspace', type=Path, help='Separate planar ground packet, outside the obstacle catalog')
    parser.add_argument('--workspace-overrides', type=Path,
                        help='Version 1 JSON workspaces mapping; relative paths resolve beside this JSON')
    parser.add_argument('--endpoint-mapping', type=Path, help='Version 1 paired initial/applied worker groups; each endpoint is validated independently')
    args = parser.parse_args()
    print(json.dumps(collect(args.catalog.resolve(), args.assets.resolve(), args.output.resolve(),
                             args.decisions.resolve(strict=True) if args.decisions else None,
                             args.ground_workspace, args.workspace_overrides, args.endpoint_mapping)))
