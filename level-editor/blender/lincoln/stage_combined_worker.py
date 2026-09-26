"""Stage a texture-combined worker on top of a globally reprojected Lincoln stage (plain Python).

    python3 level-editor/blender/lincoln/stage_combined_worker.py \
      --stage-in <publication-N/stage-vM> --worker <combine/worker.blend> \
      --report <combine report.json> --output <publication-N/stage-vK>

Copies the combined worker and the stage-in catalog and writes an `integration.json` bound to the
new worker with a `texture_combine` record (stage-in, combine worker and report hashes). The
stage-in `global_reprojection` record is carried over. `publish_export.py` then runs unchanged;
`verify_global_reprojection.py` proves the combine only wrote texels that were unknown.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-in', type=Path, required=True)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--worker-sha256', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    stage_in = args.stage_in.resolve(strict=True)
    integration = json.loads((stage_in / 'integration.json').read_text())
    if sha(stage_in / 'worker.blend') != integration['worker_sha256']:
        raise ValueError('Stage-in worker changed after integration')
    if sha(args.worker) != args.worker_sha256:
        raise ValueError('Combined worker does not match the announced hash')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.worker, output / 'worker.blend')
    shutil.copyfile(stage_in / 'catalog.json', output / 'catalog.json')
    if sha(output / 'worker.blend') != args.worker_sha256:
        raise RuntimeError('Copied worker hash mismatch')
    staged = dict(integration)
    staged['worker'] = str(output / 'worker.blend')
    staged['worker_sha256'] = args.worker_sha256
    staged['staged_catalog'] = str(output / 'catalog.json')
    if 'texture_combine' in integration:
        # Chained texel stages (e.g. a verified correction on top of a combine) keep every link.
        staged['texture_combine_chain'] = integration.get('texture_combine_chain', []) + [integration['texture_combine']]
    staged['texture_combine'] = {
        'stage_in': str(stage_in), 'stage_in_worker_sha256': integration['worker_sha256'],
        'combine_worker': str(args.worker.resolve()), 'combine_worker_sha256': args.worker_sha256,
        'report': str(args.report.resolve()), 'report_sha256': sha(args.report),
        'semantics': 'Generated fill written only into texels still unknown after global source reprojection.'}
    staged['scope'] = integration['scope'] + ' Generated texture fill combined.'
    (output / 'integration.json').write_text(json.dumps(staged, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'worker_sha256': args.worker_sha256}))


if __name__ == '__main__':
    main()
