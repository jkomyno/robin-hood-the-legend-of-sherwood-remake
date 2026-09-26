"""Pack independently reviewed endpoint exports and retain verifiable bindings."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


SCRIPT = Path(__file__).resolve().parents[1] / 'pipeline/src/bundle-library-states.ts'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_bundled_reference(report, reference):
    """An exact worker re-export and independently recomputed scene must agree."""
    if str(report['model']).endswith('.gltf') or report.get('canonical_model'):
        from canonical_assets import read_model
        from unify_map_assets import local_states
        if sha(report['model']) != report['model_sha256']:
            raise ValueError('Canonical endpoint model changed')
        source, source_binary, source_external = read_model(reference, Path(reference).parent)
        source = local_states(source)
        with tempfile.TemporaryDirectory(prefix='verify-local-endpoint-') as temporary:
            root = Path(temporary)
            for table in ('buffers', 'images'):
                for i, value in enumerate(source.get(table, [])):
                    if 'uri' in value or table == 'buffers':
                        data = source_external(value['uri']) if 'uri' in value else source_binary
                        name = f'{table}-{i}.bin'
                        (root/name).write_bytes(data); value['uri'] = name
            prepared = root/'reference.gltf'; prepared.write_text(json.dumps(source))
            script = SCRIPT.with_name('verify-canonical-scene.ts')
            try:
                return json.loads(subprocess.check_output(['node', str(script), str(report['model']),
                    report['model_scene'], str(prepared)], text=True, stderr=subprocess.PIPE))
            except subprocess.CalledProcessError as error:
                raise ValueError('Canonical endpoint differs from independently re-exported worker: '+error.stderr) from error
    if sha(reference) != report['original_model_sha256']:
        raise ValueError('Reviewed worker re-export differs from original endpoint bytes')
    receipt_path = Path(report['bundle_receipt'])
    if sha(receipt_path) != report['bundle_receipt_sha256']:
        raise ValueError('Endpoint bundle receipt changed')
    receipt = json.loads(receipt_path.read_text())
    matching = [state for state in receipt['states'] if state['scene'] == report['model_scene']]
    if (receipt['asset_id'] != report['asset_id'] or len(matching) != 1 or
            matching[0]['source_sha256'] != report['original_model_sha256'] or
            receipt['output']['sha256'] != report['model_sha256'] or
            sha(report['model']) != report['model_sha256']):
        raise ValueError('Endpoint bundle receipt does not bind the reviewed source and output scene')
    args = ['node', str(SCRIPT), '--verify-scene', str(report['model']), '--scene', report['model_scene'],
            '--reference', str(reference)]
    result = json.loads(subprocess.check_output(args, text=True))
    if (result['semantic_sha256'] != matching[0]['semantic_sha256'] or
            result['scene'] != report['model_scene'] or
            result['reference_sha256'] != report['original_model_sha256'] or
            result['bundle_sha256'] != report['model_sha256']):
        raise ValueError('Independent selected-scene verification differs from bundle receipt')
    return result


def bundle_exported_variants(output, reports):
    """Called after all ordinary exports; never bundles the full editor map."""
    output = Path(output)
    for asset_id in sorted({report['asset_id'] for report in reports}):
        asset = output / 'assets' / asset_id
        source_descriptor = json.loads((asset / 'asset.json').read_text())
        old_models = {source_descriptor['model']} | {
            value['model'] for value in (source_descriptor.get('state_variants') or
                                        source_descriptor.get('standalone_variants') or {}).values()}
        if any(Path(name).name != name or not name.endswith('.glb') for name in old_models):
            raise ValueError('Endpoint bundle requires local GLB model paths')
        staged = output / 'state-bundles' / asset_id
        subprocess.run(['node', str(SCRIPT), '--asset-dir', str(asset), '--stage', str(staged)], check=True, stdout=subprocess.DEVNULL)
        descriptor = json.loads((staged / 'asset.json').read_text())
        receipt = json.loads((staged / 'bundle.receipt.json').read_text())
        variants = descriptor.get('state_variants') or descriptor.get('standalone_variants')
        if (descriptor['id'] != asset_id or receipt['asset_id'] != asset_id or
                sha(staged / descriptor['model']) != receipt['output']['sha256']):
            raise ValueError('Packed endpoint output identity differs')
        for report in reports:
            if report['asset_id'] != asset_id:
                continue
            variant = variants[report['state']]
            bindings = [state for state in receipt['states'] if state['scene'] == variant['model_scene']]
            if len(bindings) != 1 or bindings[0]['source_sha256'] != report['model_sha256']:
                raise ValueError('Packed endpoint substituted source export')
            report.update(original_model_sha256=report['model_sha256'],
                          model=str(asset / descriptor['model']), model_sha256=receipt['output']['sha256'],
                          model_scene=variant['model_scene'], bundle_receipt=str(asset / 'bundle.receipt.json'),
                          bundle_receipt_sha256=sha(staged / 'bundle.receipt.json'))
        for name in ('model.glb', 'asset.json', 'bundle.receipt.json'):
            shutil.copy2(staged / name, asset / name)
        for old in old_models - {descriptor['model']}:
            (asset / old).unlink()
    return reports
