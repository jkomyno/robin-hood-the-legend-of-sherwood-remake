"""Prepare, generate and bake Lincoln texture experiments from explicit geometry approvals.

Lincoln records decisions in the collector's `approvals.json` (bound to model and
`modified/views.json` hashes) instead of Derby's review-manifest/decisions.json.
This adapter re-runs the frozen collector checks for one asset, verifies that
the single current approval binds the exact model and packet, and writes a
normalized one-item review manifest plus decision record. The shared
`prepare_texture_packet.py` then copies the approved packet unchanged into a new
immutable experiment (input.png = approved source-textured sheet with shaded
gray unknown surfaces, solid.png = calibrated pure-gray sheet, local mask,
views.json with cameras/crops, approval.json).

Commands (from the repository root):

  python3 level-editor/blender/lincoln/texture_packets.py survey
  /usr/bin/blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/texture_packets.py -- audit ID...
  python3 level-editor/blender/lincoln/texture_packets.py prepare ID...
  python3 level-editor/blender/lincoln/texture_packets.py generate EXPERIMENT... [--prompt-suffix TEXT] [--provider openrouter|openai]
  /usr/bin/blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/texture_packets.py -- bake EXPERIMENT BAKE_NAME [--provider ...]
  python3 level-editor/blender/lincoln/texture_packets.py retry ID SUFFIX_NAME

`audit` records the read-only structural stored-material audit that preparation
requires. `retry` clones a prepared experiment (same approved inputs) into a
separate retry directory so a material-specific prompt never overwrites the
original raw output. Nothing here records texture approval or publishes assets.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
EDITOR = ROOT / 'level-editor'
WORK = EDITOR / 'work/lincoln-refinement'
TEXTURES = WORK / 'textures'
CATALOG = WORK / 'grouping/catalog-v4.json'
ASSETS = WORK / 'round-4/assets'
WORKSPACE_MAP = WORK / 'workspace-overrides-v4.json'
APPROVALS = WORK / 'approvals.json'
COLLECTOR_EVIDENCE = WORK / 'round-4/gallery-packet-evidence'
TOOLING = WORK / 'tooling/e6b57cb851c7142b'
AUTHORIZATION = ('User approved running texture generation for all geometry-approved Lincoln assets '
                 '(relayed by the coordinator, 2026-09-25). '
                 'Texture approval is a separate, pending decision.')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def catalog_groups():
    return {group['id']: group for group in read(CATALOG)['groups']}


def workspace_for(asset_id):
    overrides = read(WORKSPACE_MAP)['assets']
    return Path(overrides[asset_id]).resolve() if asset_id in overrides else (ASSETS / asset_id).resolve()


def approval_for(asset_id):
    records = [a for a in read(APPROVALS)['approvals'] if a['asset_id'] == asset_id]
    require(len(records) == 1, 'Expected exactly one current approval record: ' + asset_id)
    return records[0]


def audit_directory(asset_id, model_sha256):
    return TEXTURES / 'material-audits' / asset_id / model_sha256[:16]


def editable_pixels(packet):
    from PIL import Image
    import numpy as np
    total = 0
    for index in range(8):
        known = np.asarray(Image.open(packet / f'views/view-{index}-known.png').convert('RGBA'))[:, :, 0] > 127
        solid = np.asarray(Image.open(packet / f'views/view-{index}-solid.png').convert('RGBA'))[:, :, 3] > 0
        total += int((solid & ~known).sum())
    return total


def verify_current(asset_id):
    """Fresh frozen-collector checks plus an approval bound to the exact current revision."""
    import build_gallery as collector
    group = catalog_groups()[asset_id]
    workspace = workspace_for(asset_id)
    status, _, fresh, _ = collector.inspect(workspace, group)
    require(status == 'ready-for-user', f'Collector technical status is {status}')
    approval = approval_for(asset_id)
    require(approval.get('decision') == 'approved' and approval.get('scope') == 'geometry',
            'Explicit geometry approval missing')
    require(approval.get('exact_text', '').strip(), 'Exact approval text missing')
    require(approval['model_sha256'] == fresh['model_sha256'], 'Geometry approval model is stale')
    require(approval['modified_views_sha256'] == fresh['packet_hashes']['modified']['views.json'],
            'Geometry approval camera packet is stale')
    require(approval.get('state_bundle_sha256') is None and approval.get('lighting_review_sha256') is None,
            'Stateful or relit approvals need a separate state lane')
    evidence_path = COLLECTOR_EVIDENCE / (asset_id + '.json')
    evidence = read(evidence_path)
    require(evidence.get('status') == 'approved' and evidence.get('user_decision_matches_revision') is True,
            'Round-4 collector evidence does not show this revision as approved')
    require(evidence['packet_hashes'] == fresh['packet_hashes'] and evidence['model_sha256'] == fresh['model_sha256'],
            'Collector evidence packets differ from the current workspace')
    require(not evidence.get('state_packets'), 'State packets require a separate state lane')
    return workspace, approval, fresh, evidence_path


def normalize(asset_id, output):
    """Write the one-item manifest/decision pair the shared preparation driver validates."""
    workspace, approval, fresh, evidence_path = verify_current(asset_id)
    packet = workspace / 'modified'
    model = workspace / 'model.blend'
    audits = sorted(audit_directory(asset_id, fresh['model_sha256']).glob('*/audit.json'))
    audits = [p for p in audits if read(p).get('model_sha256') == fresh['model_sha256']
              and read(p).get('status') == 'STRUCTURAL-PASS' and not read(p).get('problems')]
    require(audits, 'Exact stored-material audit missing; run the audit command in Blender first')
    audit_path = audits[-1]
    output = Path(output).resolve()
    require(not output.exists(), 'Normalized output already exists: ' + str(output))
    output.mkdir(parents=True)
    provenance = {'version': 1, 'asset_id': asset_id, 'selected_state': 'covered',
                  'source_approval_file': str(APPROVALS), 'source_approval': approval,
                  'source_collector_evidence': str(evidence_path), 'source_collector_sha256': sha(evidence_path),
                  'workspace': str(workspace), 'authorization': AUTHORIZATION}
    provenance_path = output / 'approval-provenance.json'
    write(provenance_path, provenance)
    parent_identity = {key: approval.get(key) for key in
                       ('asset_id', 'model_sha256', 'modified_views_sha256', 'state_bundle_sha256', 'lighting_review_sha256')}
    parent_revision = hashlib.sha256(json.dumps(parent_identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    selection = {'preparation_model': str(model), 'parent_geometry_revision': parent_revision}
    selection_path = output / 'preparation-selection.json'
    write(selection_path, selection)
    paths = {'approval_provenance': provenance_path, 'collector': evidence_path, 'model': model,
             'solid': packet / 'solid.png', 'textured': packet / 'textured.png', 'context': packet / 'context.png',
             'frames': packet / 'views.json', 'material_audit': audit_path, 'preparation_selection': selection_path,
             'lighting_config': WORK / 'lighting-calibration/map-lighting.json'}
    paths.update({f'packet_{i}': p for i, p in enumerate(sorted(packet.rglob('*'))) if p.is_file()})
    for name in ('workspace.json', 'source-masks.json', 'candidate.json', 'review.md',
                 'source-coverage-audit.json', 'validation.json'):
        if (workspace / name).exists():
            paths['workspace_' + name] = workspace / name
    revision_evidence = {key: {'path': str(p.resolve()), 'sha256': sha(p)} for key, p in paths.items()}
    identity = {'asset_id': asset_id, 'model_sha256': fresh['model_sha256'],
                'evidence': {key: entry['sha256'] for key, entry in revision_evidence.items()}}
    revision = dict(identity, evidence=revision_evidence,
                    sha256=hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest())
    item = {'id': asset_id, 'workspace': str(workspace), 'status': 'ready-for-user',
            'stored_material_validation': 'PASS', 'stored_material_audit': str(audit_path),
            'solid': str(packet / 'solid.png'), 'textured': str(packet / 'textured.png'),
            'approval_provenance': provenance, 'preparation_selection': str(selection_path),
            'revision': revision, **selection}
    decision = {'asset_id': asset_id, 'scope': 'geometry', 'decision': 'approved',
                'exact_user_text': approval['exact_text'], 'revision_sha256': revision['sha256'],
                'approval_provenance': provenance}
    write(output / 'manifest.json', {'version': 1, 'items': [item]})
    write(output / 'decisions.json', {'version': 1, 'decisions': [decision]})
    return output / 'manifest.json'


def shared_preparation():
    spec = importlib.util.spec_from_file_location('shared_texture_preparation',
                                                  EDITOR / 'refinement/prepare_texture_packet.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(asset_ids):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from freeze_tooling import select_tooling
    select_tooling(TOOLING)
    shared = shared_preparation()
    results = []
    for asset_id in asset_ids:
        experiment = TEXTURES / 'experiments' / asset_id
        row = {'asset_id': asset_id, 'experiment': str(experiment)}
        try:
            if experiment.exists():
                verify_prepared(experiment)
                row['status'] = 'already-prepared'
            else:
                editable = editable_pixels(workspace_for(asset_id) / 'modified')
                if editable == 0:
                    verify_current(asset_id)
                    row.update(status='skipped-fully-known', editable_pixels=0)
                else:
                    manifest = normalize(asset_id, TEXTURES / 'normalized' / asset_id)
                    report = shared.prepare(manifest, asset_id, experiment)
                    verify_prepared(experiment)
                    row.update(status='prepared', editable_pixels=report['editable_pixels'],
                               input_sha256=report['input_sha256'])
        except Exception as error:  # Recorded per asset; the batch continues.
            row.update(status='failed', reason=f'{type(error).__name__}: {error}')
        print(json.dumps(row), flush=True)
        results.append(row)
    return results


def verify_prepared(experiment):
    report = read(experiment / 'preparation.json')
    for name, digest in report['files'].items():
        require(sha(experiment / name) == digest, 'Prepared artifact changed: ' + name)
    approval = read(experiment / 'approval.json')
    require(sha(experiment / 'input.png') == approval['input_sha256'], 'Prepared input changed')
    return approval


def retry(asset_id, name):
    """Copy the exact prepared inputs into a separate retry experiment (no API cache)."""
    source = TEXTURES / 'experiments' / asset_id
    verify_prepared(source)
    target = TEXTURES / 'retries' / f'{asset_id}--{name}'
    require(not target.exists(), 'Retry experiment already exists: ' + str(target))
    target.mkdir(parents=True)
    for entry in read(source / 'preparation.json')['files']:
        (target / entry).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / entry, target / entry)
    shutil.copy2(source / 'preparation.json', target / 'preparation.json')
    write(target / 'retry-of.json', {'version': 1, 'asset_id': asset_id, 'original_experiment': str(source),
                                     'original_preparation_sha256': sha(source / 'preparation.json')})
    verify_prepared(target)
    return target


PROVIDER_AUTHORIZATION = {
    'openrouter': {'exact_user_text': 'use openrouter ith sunburst model',
                   'relayed_by': 'coordinator (team-lead), 2026-09-25',
                   'scope': 'OpenRouter transport of openai/gpt-image-2.5-sunburst for approved Lincoln assets'},
}


def generation_directory(experiment, provider='openrouter'):
    return Path(experiment) / ('generation-short-no-mask-with-lighting' + ('-openrouter' if provider == 'openrouter' else ''))


def generate(experiment, prompt_suffix=None, provider='openrouter'):
    experiment = Path(experiment).resolve()
    verify_prepared(experiment)
    output = generation_directory(experiment, provider)
    command = ['node', str(EDITOR / 'pipeline/src/refinement/generate-textures.ts'), str(experiment),
               '--generate', '--prompt-variant', 'short', '--no-mask',
               '--lighting-reference', str(experiment / 'solid.png'), '--provider', provider]
    if prompt_suffix:
        command += ['--prompt-suffix', prompt_suffix]
    provenance = {'version': 1, 'provider': provider, 'command': command[2:],
                  'prompt_suffix': prompt_suffix, 'geometry_authorization': AUTHORIZATION,
                  'provider_authorization': PROVIDER_AUTHORIZATION.get(provider)}
    require(provider == 'openai' or provenance['provider_authorization'], 'Provider lacks explicit authorization')
    # Node's fetch ignores HTTP(S)_PROXY unless asked; the sandbox routes egress through one.
    env = dict(os.environ, NODE_USE_ENV_PROXY='1')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=env)
    (experiment / f'generation-log-{provider}.txt').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[-2000:])
    report = read(output / 'generation.json')
    provenance['generation_sha256'] = sha(output / 'generation.json')
    write(output / 'generation-provenance.json', provenance)
    return report


def bake(experiment, bake_name, provider='openrouter'):
    """Run inside Blender: shared guarded bake of generated-preserved.png, raw as tone reference."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_slots import acquire
    experiment = Path(experiment).resolve()
    verify_prepared(experiment)
    generation = generation_directory(experiment, provider)
    report = read(generation / 'generation.json')
    require(report.get('changedProtected') == 0, 'Generated sheet changed protected pixels')
    output = experiment / bake_name
    require(not output.exists(), 'Bake directory already exists: ' + str(output))
    acquire()
    sys.path.insert(0, str(EDITOR / 'refinement/blender'))
    import bpy
    from bake_reviewed_asset import stage
    bpy.ops.wm.open_mainfile(filepath=str(experiment / 'approved-model.blend'))
    result = stage(experiment / 'views.json', generation / 'generated-preserved.png', output,
                   texels_per_unit=2, reconciliation_reference=generation / 'generated-raw.png')
    return {'asset': result['asset_id'], 'output': str(output), 'counts': result['counts'],
            'geometry_verified': result['geometry_verified'],
            'outside_objects_unchanged': result['outside_objects_unchanged']}


def audit(asset_ids):
    """Run inside Blender: read-only structural stored-material audit of each approved model."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_slots import acquire
    acquire()
    sys.path.insert(0, str(EDITOR / 'refinement/blender'))
    from audit_stored_materials import run
    rows = []
    for asset_id in asset_ids:
        workspace = workspace_for(asset_id)
        model_hash = sha(workspace / 'model.blend')
        directory = audit_directory(asset_id, model_hash)
        existing = [p for p in directory.glob('*/audit.json') if read(p).get('model_sha256') == model_hash]
        if existing:
            rows.append({'asset_id': asset_id, 'status': read(existing[-1])['status'], 'audit': str(existing[-1])})
            continue
        directory.mkdir(parents=True, exist_ok=True)
        output = directory / f'run-{len(list(directory.iterdir())) + 1}'
        try:
            report = run(workspace, output)
            rows.append({'asset_id': asset_id, 'status': report['status'], 'problems': report['problems'],
                         'audit': str(output / 'audit.json')})
        except Exception as error:
            rows.append({'asset_id': asset_id, 'status': 'error', 'reason': f'{type(error).__name__}: {error}'})
        print(json.dumps(rows[-1]), flush=True)
    return rows


def survey():
    rows = []
    for asset_id in catalog_groups():
        workspace = workspace_for(asset_id)
        approval = approval_for(asset_id)
        frames = read(workspace / 'modified/views.json')
        width, height = frames['tile_size']
        canvas = (4 * width, 2 * height)
        rows.append({'asset_id': asset_id, 'workspace': str(workspace), 'decision': approval['decision'],
                     'model_current': approval['model_sha256'] == sha(workspace / 'model.blend'),
                     'packet_current': approval['modified_views_sha256'] == sha(workspace / 'modified/views.json'),
                     'canvas': canvas,
                     'sunburst_size_ok': (canvas[0] % 16 == 0 and canvas[1] % 16 == 0 and max(canvas) <= 3840
                                          and max(canvas) / min(canvas) <= 3 and 655360 <= canvas[0] * canvas[1] <= 8294400),
                     'editable_pixels': editable_pixels(workspace / 'modified')})
    return rows


def main():
    in_blender = '--' in sys.argv
    argv = sys.argv[sys.argv.index('--') + 1:] if in_blender else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('survey')
    sub.add_parser('audit').add_argument('ids', nargs='+')
    sub.add_parser('prepare').add_argument('ids', nargs='+')
    command = sub.add_parser('generate')
    command.add_argument('experiments', nargs='+', type=Path)
    command.add_argument('--prompt-suffix')
    command.add_argument('--provider', default='openrouter', choices=['openai', 'openrouter'])
    command = sub.add_parser('bake')
    command.add_argument('experiment', type=Path)
    command.add_argument('bake_name')
    command.add_argument('--provider', default='openrouter', choices=['openai', 'openrouter'])
    command = sub.add_parser('retry')
    command.add_argument('id')
    command.add_argument('name')
    args = parser.parse_args(argv)
    if args.command in ('audit', 'bake') and not in_blender:
        raise SystemExit(args.command + ' must run inside Blender')
    if args.command == 'survey':
        result = survey()
    elif args.command == 'audit':
        result = audit(args.ids)
    elif args.command == 'prepare':
        result = prepare(args.ids)
    elif args.command == 'generate':
        result = []
        for experiment in args.experiments:
            try:
                report = generate(experiment, args.prompt_suffix, args.provider)
                result.append({'experiment': str(experiment), 'status': 'generated', 'filled': report['filled'],
                               'changedProtected': report['changedProtected'], 'cache': report['cache']})
            except Exception as error:
                result.append({'experiment': str(experiment), 'status': 'failed', 'reason': str(error)})
            print(json.dumps(result[-1]), flush=True)
    elif args.command == 'bake':
        result = bake(args.experiment, args.bake_name, args.provider)
    else:
        result = {'retry': str(retry(args.id, args.name))}
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
