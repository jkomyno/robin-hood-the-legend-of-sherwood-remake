"""Normalize current Nottingham approvals for the shared texture preparation driver.

Approval provenance remains explicit. No worker, decision or reviewed image is
modified; each output directory is a new immutable preparation contract.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
sys.path.insert(0, str(Path(__file__).parent))
import build_gallery as collector


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


sha = collector.sha


def validate_approval(item, evidence, approval, fresh):
    require(approval.get('decision') == 'approved', 'Explicit geometry approval missing')
    require(approval.get('exact_text', '').strip(), 'Exact approval text missing')
    require(approval.get('asset_id') == item['id'], 'Approval asset differs')
    require(approval.get('model_sha256') == fresh['model_sha256'] == evidence['model_sha256'],
            'Geometry approval model is stale')
    require(approval.get('modified_views_sha256') == fresh['packet_hashes']['modified']['views.json'],
            'Geometry approval camera packet is stale')
    require(fresh['packet_hashes'] == evidence['packet_hashes'], 'Collector evidence packets changed')
    for key in ('state_bundle_sha256', 'lighting_review_sha256'):
        require(approval.get(key) == evidence.get(key), 'Geometry approval is stale: ' + key)
    require(item.get('user_approval') == 'approved' and evidence.get('user_decision_matches_revision') is True,
            'Gallery does not identify this revision as approved')


def normalize(asset_id, output, *, state='covered', material_audit=None,
              manifest=WORK/'gallery-candidates.json', approvals=WORK/'approvals.json',
              generation_lighting=None, state_binding=None):
    # Use the same frozen validation modules as the Nottingham collector.
    from freeze_tooling import select_tooling
    select_tooling(WORK/'tooling/58744eeaf71a21e9')
    manifest, approvals = Path(manifest).resolve(), Path(approvals).resolve()
    gallery = read(manifest)
    items = [i for i in gallery['items'] if i['id'] == asset_id]
    require(len(items) == 1, 'Expected one current parent gallery item')
    item = items[0]
    workspace = Path(item['workspace']).resolve(strict=True)
    catalog = read(WORK/'grouping/catalog-v15.json')
    matches = [g for g in catalog['groups'] if g['id'] == asset_id]
    if asset_id == 'nottingham-terrain-ground':
        matches = [{'id': asset_id, 'role': 'terrain', 'parts': []}]
    require(len(matches) == 1, 'Asset absent from current canonical catalog')
    _, _, fresh, _ = collector.inspect(workspace, matches[0])
    require(fresh['status'] == 'ready-for-user', 'Current collector technical checks are incomplete')
    evidence_path = Path(item['ownership']).resolve(strict=True)
    evidence = read(evidence_path)
    decisions = [a for a in read(approvals)['approvals'] if a['asset_id'] == asset_id]
    require(len(decisions) == 1, 'Expected exactly one current approval record')
    approval = decisions[0]
    validate_approval(item, evidence, approval, fresh)
    states = evidence.get('state_packets', {})
    for entry in states.values():
        require(collector.file_hashes(Path(entry['directory'])) == entry['hashes'], 'State packet changed')
    require(collector.state_bundle_hash(states, fresh.get('complete_state_contracts')) == evidence.get('state_bundle_sha256'),
            'Approved state bundle changed')
    full_height = state.endswith('-full-height')
    state_key = state.removesuffix('-full-height') if full_height else state
    if state == 'covered':
        packet = Path(states['covered']['directory']) if 'covered' in states else workspace/'modified'
    else:
        require(state_key in states and state_key != 'revealed_input', 'Requested state has no approved packet')
        packet = Path(states[state_key]['directory'])
        if full_height:
            require(state_key.startswith('animation-'), 'Full-height selection requires an explicit endpoint')
            packet = packet/'full-height'
            require('full-height/views.json' in states[state_key]['hashes'], 'Full-height frame absent from approved state bundle')
    frame_path = packet/'views.json'
    frames = read(frame_path)
    # Saved endpoint and complete-state models are selected through hash-bound
    # lighting records or explicit state manifests, never guessed from names.
    model = workspace/'model.blend'
    selected_binding = None
    for path in (workspace/'inspection/state-models/manifest.json', workspace/'inspection/endpoints-v6/states.json'):
        if path.exists():
            for binding in read(path)['states']:
                frame = binding.get('frame_manifest') or binding.get('views')
                if frame and (Path(frame).resolve() == frame_path.resolve() or
                              (full_height and Path(frame).resolve().parent/'full-height/views.json' == frame_path.resolve())):
                    selected_binding = binding
                    model = Path(binding['model'])
                    require(sha(model) == binding['model_sha256'], 'Saved state model changed')
    reconstruction = None
    if state_binding:
        reconstruction_path = Path(state_binding).resolve(strict=True)
        reconstruction = read(reconstruction_path)
        require(reconstruction.get('version') == 1 and reconstruction.get('status') == 'PASS'
                and reconstruction.get('asset_id') == asset_id, 'Invalid state reconstruction proof')
        rows = [r for r in reconstruction['states'] if Path(r.get('frame_manifest', Path(r.get('packet', ''))/'views.json')).resolve() == frame_path.resolve()]
        require(len(rows) == 1, 'Reconstruction does not identify selected exact frame')
        selected_binding = rows[0]
        require(selected_binding.get('frame_manifest_sha256', selected_binding.get('frames_sha256')) == sha(frame_path), 'Reconstructed state frame changed')
        model = Path(selected_binding['source_blend']).resolve(strict=True)
        require(sha(model) == selected_binding['source_blend_sha256'], 'Reconstructed state model changed')
        require(set(selected_binding['render_object_names']) == set(frames['object_names']), 'Reconstructed state visibility differs')
        require(all(selected_binding.get(k) is True for k in ('source_rgb_preserved', 'solid_pixels_preserved', 'ownership_buffers_reproduced')),
                'State reconstruction lacks exact source/solid/ownership proof')
        require(selected_binding.get('approved_inputs_unchanged') is True, 'Reconstruction changed approved inputs')
        comparisons = selected_binding.get('comparisons', [])
        expected_comparisons = {'solid.png', 'textured.png'} | {
            f'views/view-{i}-{kind}.png' for i in range(8) for kind in ('solid','known','textured')}
        require(expected_comparisons <= {r['relative'] for r in comparisons}, 'Reconstruction omits eight-view evidence')
        for comparison in comparisons:
            require(comparison.get('pixels_equal') is True and
                    comparison['approved_sha256'] == comparison['reproduced_sha256'] == sha(packet/comparison['relative']),
                    'Reconstructed state does not preserve approved pixels')
        actual = selected_binding.get('actual_material_check', {})
        require(actual.get('status') == 'STRUCTURAL-PASS' and sha(actual['path']) == actual['sha256'],
                'State actual material proof changed')
        if material_audit is None: material_audit = actual['path']
        for path, digest in selected_binding.get('artifact_sha256', {}).items():
            artifact = Path(path)
            if not artifact.is_absolute(): artifact = reconstruction_path.parent/artifact
            require(sha(artifact) == digest, 'State reconstruction artifact changed')
    profile = WORK/'lighting-calibration/map-lighting.json'
    from lighting_review import load_lighting_review
    original_solid = str((packet/'solid.png').resolve())
    if generation_lighting:
        lighting_path = Path(generation_lighting).resolve(strict=True)
        lighting_report = read(lighting_path)
        require(lighting_report.get('version') == 1 and lighting_report.get('status') == 'PASS'
                and lighting_report.get('asset_id') == asset_id, 'Invalid generation lighting report')
        require(lighting_report.get('model_sha256') == fresh['model_sha256'], 'Generation lighting primary model changed')
        require(lighting_report.get('lighting_config_sha256') == sha(profile)
                and lighting_report.get('lighting') == read(profile)['lighting'], 'Generation lighting configuration differs')
        require(lighting_report.get('authorization_scope'), 'Generation lighting authorization provenance missing')
        records = [r for r in lighting_report['packets'] if Path(r['original_solid']).resolve() == Path(original_solid)]
        require(len(records) == 1, 'Generation lighting lacks selected state')
        record = records[0]
        require(record.get('inspected_views') == list(range(8)), 'Generation lighting not inspected in all views')
        for field in ('original_solid', 'frame_manifest', 'source_blend', 'solid'):
            require(sha(record[field]) == record[field+'_sha256'], 'Generation lighting artifact changed: '+field)
        require(Path(record['frame_manifest']).resolve() == frame_path.resolve(), 'Generation lighting frame path differs')
        lighting = {'path':str(lighting_path), 'sha256':sha(lighting_path)}
        solid = Path(record['solid']).resolve(strict=True)
    else:
        lighting, replacements = load_lighting_review(workspace, evidence, profile)
        require(lighting is not None, 'Generation requires map-calibrated lighting evidence')
        require(lighting['sha256'] == evidence.get('lighting_review_sha256'), 'Approved lighting differs')
        require(original_solid in replacements, 'Selected state has no approved lighting')
        solid = Path(replacements[original_solid])
        lighting_report = read(lighting['path'])
        record = next(p for p in lighting_report['packets'] if p['original_solid'] == original_solid)
    if state != 'covered':
        require(selected_binding is not None, 'Selected state requires a saved-state binding or exact reconstruction proof')
    require(Path(record['source_blend']).resolve() == model.resolve(), 'Lighting selected a different state model')
    require(sha(model) == record['source_blend_sha256'], 'Lighting and preparation model differ')
    require(record['frame_manifest_sha256'] == sha(frame_path), 'Lighting cameras differ')
    solid_views = [Path(p) for p in record['solid_view_paths']] if record.get('solid_view_paths') else [solid.parent/f'view-{i}-solid.png' for i in range(8)]
    # Per-view hashes are bound into the derived revision. Their assembly is
    # checked against the explicitly approved supplemental sheet by preparation.
    audit_paths = [Path(material_audit)] if material_audit else list(workspace.glob('inspection/**/audit.json'))
    if material_audit is None:
        from generation_material_audits import existing
        generated = existing({'workspace':str(workspace), 'asset_id':asset_id,
                              'saved_state_model_sha256':sha(model), 'frame_manifest':str(frame_path),
                              'frame_manifest_sha256':sha(frame_path)})
        if generated: audit_paths.insert(0, generated)

    audits = [p for p in audit_paths if read(p).get('model_sha256') == sha(model)
              and read(p).get('frame_manifest_sha256') == sha(frame_path)
              and read(p).get('status') == 'STRUCTURAL-PASS' and not read(p).get('problems')]
    require(audits, 'Exact saved-state material audit missing; run a read-only material audit first')
    audit_path = audits[0]
    audit = read(audit_path)
    for name, digest in audit.get('artifact_sha256', {}).items():
        require(sha(audit_path.parent/name) == digest, 'Saved material audit image changed')
    require(set(audit.get('render_object_names', [])) == set(frames['object_names']), 'Saved material audit visibility differs')
    output = Path(output).resolve()
    require(not output.exists(), 'Normalized output already exists')
    output.mkdir(parents=True)
    provenance = {'version': 1, 'asset_id': asset_id, 'selected_state': state,
                  'source_approval_file': str(approvals), 'source_approval': approval,
                  'source_collector_evidence': str(evidence_path), 'source_collector_sha256': sha(evidence_path),
                  'authorization': 'Existing exact geometry approval; user requested generation and projection of missing textures.'}
    provenance_path = output/'approval-provenance.json'
    provenance_path.write_text(json.dumps(provenance, indent=2)+'\n')
    paths = {'approval_provenance': provenance_path, 'collector': evidence_path,
             'solid': solid, 'textured': packet/'textured.png', 'frames': frame_path,
             'preparation_model': model, 'material_audit': audit_path,
             'lighting_review': Path(lighting['path']), 'lighting_config': profile}
    if state_binding:
        paths['state_reconstruction'] = Path(state_binding).resolve()
    paths.update({f'solid_view_{i}': p for i, p in enumerate(solid_views)})
    paths.update({f'packet_{i}': p for i,p in enumerate(sorted(packet.rglob('*'))) if p.is_file()})
    paths.update({f'material_artifact_{i}': audit_path.parent/n for i,n in enumerate(audit.get('artifact_sha256', {}))})
    for name in ('workspace.json', 'source-masks.json', 'projection-layers.json', 'projection-state-layers.json',
                 'material-states.json', 'inspection/state-models/manifest.json', 'inspection/endpoints-v6/states.json'):
        if (workspace/name).exists(): paths['workspace_'+name] = workspace/name
    parent_identity = {key:approval.get(key) for key in
                       ('asset_id','model_sha256','modified_views_sha256','state_bundle_sha256','lighting_review_sha256')}
    parent_revision = hashlib.sha256(json.dumps(parent_identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    selection = {'preparation_model':str(model), 'preparation_state':state,
                 'solid_view_paths':[str(p) for p in solid_views], 'derive_unknown_lighting':True,
                 'parent_geometry_revision':parent_revision,
                 'preparation_lighting':{'config':str(profile), 'lighting':read(profile)['lighting']}}
    selection_path = output/'preparation-selection.json'
    selection_path.write_text(json.dumps(selection,indent=2)+'\n')
    paths['preparation_selection'] = selection_path
    revision_evidence = {key: {'path':str(p.resolve()), 'sha256':sha(p)} for key,p in paths.items()}
    identity = {'asset_id':asset_id, 'model_sha256':sha(workspace/'model.blend'),
                'evidence':{key:entry['sha256'] for key,entry in revision_evidence.items()}}
    revision = dict(identity, evidence=revision_evidence,
        sha256=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    normalized = {'id':asset_id, 'workspace':str(workspace), 'status':'ready-for-user',
                  'stored_material_validation':'PASS', 'solid':str(solid), 'textured':str(packet/'textured.png'),
                  'preparation_model':str(model), 'preparation_state':state,
                  'solid_view_paths':[str(p) for p in solid_views], 'derive_unknown_lighting':True,
                  'preparation_lighting':{'config':str(profile), 'lighting':read(profile)['lighting']},
                  'approval_provenance':provenance, 'preparation_selection':str(selection_path),
                  'parent_geometry_revision':parent_revision, 'revision':revision}
    decision = {'asset_id':asset_id, 'scope':'geometry', 'decision':'approved',
                'exact_user_text':approval['exact_text'], 'revision_sha256':revision['sha256'],
                'approval_provenance':provenance}
    (output/'manifest.json').write_text(json.dumps({'version':1,'items':[normalized]},indent=2)+'\n')
    (output/'decisions.json').write_text(json.dumps({'version':1,'decisions':[decision]},indent=2)+'\n')
    return {'manifest':str(output/'manifest.json'), 'asset_id':asset_id, 'state':state,
            'model':str(model), 'revision':revision['sha256']}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_id');parser.add_argument('output',type=Path)
    parser.add_argument('--state',default='covered')
    parser.add_argument('--material-audit',type=Path)
    parser.add_argument('--generation-lighting',type=Path)
    parser.add_argument('--state-binding',type=Path)
    args=parser.parse_args()
    print(json.dumps(normalize(args.asset_id,args.output,state=args.state,material_audit=args.material_audit,
                               generation_lighting=args.generation_lighting,state_binding=args.state_binding)))
