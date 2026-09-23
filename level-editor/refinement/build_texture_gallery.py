"""Collect visually checked texture bakes into the shared, stable-ID gallery."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'blender'))
from build_review_gallery import build
from review_evidence import sha


def validate_reconciliation_reference(validation):
    reference = validation.get('reconciliation_reference')
    digest = validation.get('reconciliation_reference_sha256')
    if bool(reference) != bool(digest):
        raise ValueError('Incomplete reconciliation reference evidence')
    if reference:
        path = Path(reference)
        if not path.is_file() or sha(path) != digest:
            raise ValueError('Reconciliation reference changed or is missing')
        guarded = {str(Path(key).resolve()): value for key, value in validation.get('evidence_sha256', {}).items()}
        if guarded.get(str(path.resolve())) != digest:
            raise ValueError('Reconciliation reference absent from guarded bake evidence')


def collect(experiments, output, map_name, additional_experiments=()):
    experiments, output = Path(experiments).resolve(), Path(output).resolve()
    items = []
    roots = {experiments, *(Path(path).resolve() for path in additional_experiments)}
    for experiment in sorted({path.resolve() for root in roots for path in root.iterdir() if path.is_dir()}):
        review_path = experiment / 'texture-review.json'
        if not review_path.is_file():
            continue
        review = json.loads(review_path.read_text())
        if review.get('status') in {'held', 'fix-needed', 'rejected'}:
            continue
        approval = json.loads((experiment / 'approval.json').read_text())
        bake = (experiment / review['bake']).resolve()
        generation = (experiment / review['generation']).resolve()
        validation = json.loads((bake / 'validation.json').read_text())
        report = json.loads((generation / 'generation.json').read_text())
        validate_reconciliation_reference(validation)
        if (review.get('all_eight_actual_views_inspected') is not True
                or review.get('status') != 'ready-for-user'
                or validation.get('geometry_verified') is not True
                or report.get('changedProtected') != 0):
            raise ValueError(f'Incomplete texture review: {experiment.name}')
        actual = bake / 'actual/textured.png'
        if (sha(actual) != review['actual_sheet_sha256']
                or sha(bake / 'worker.blend') != review['baked_model_sha256']
                or sha(generation / 'generated-preserved.png') != validation['generated_sha256']
                or sha(experiment / 'input.png') != approval['input_sha256']):
            raise ValueError(f'Texture review evidence changed: {experiment.name}')
        asset_id = approval['asset_id']
        items.append({
            'id': asset_id, 'name': asset_id.removeprefix(map_name.lower() + '-').replace('-', ' ').title(),
            'status': 'ready-for-user', 'user_approval': 'pending',
            'notes': ['Texture approval pending; geometry was previously approved.', *review.get('notes', [])],
            'solid': str(experiment / 'solid.png'),
            'textured': str(actual), 'textured_label': 'Generated texture baked onto the actual mesh — approval candidate',
            'source_comparison': str(experiment / 'input.png'),
            'source_comparison_label': 'Approved source textures before generation',
            'source_comparison_secondary': str(generation / 'generated-preserved.png'),
            'source_comparison_secondary_label': 'Generated sheet with original pixels restored',
            'source_trace': str(generation / 'generated-raw.png'),
            'source_trace_label': ('Raw Sunburst output — inferred-color calibration only' if validation.get('reconciliation_reference') else 'Raw Sunburst output — reference only, not used for this bake'),
            'validation': str(bake / 'validation.json'), 'review': str(review_path),
        })
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / 'texture-candidates.json'
    manifest.write_text(json.dumps({'map': map_name + ' texture', 'items': items}, indent=2) + '\n')
    build(manifest, output / 'gallery', map_name=map_name + ' texture')
    return {'gallery': str(output / 'gallery/index.html'), 'candidates': len(items)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiments', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--map-name', required=True)
    parser.add_argument('--additional-experiments', type=Path, action='append', default=[],
                        help='Include another immutable experiment root without relocating its evidence')
    args = parser.parse_args()
    print(json.dumps(collect(args.experiments, args.output, args.map_name, args.additional_experiments)))
