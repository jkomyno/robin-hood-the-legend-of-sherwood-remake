"""Render a reconstructed hall state and bind its exact preservation evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(Path(__file__).parent), str(ROOT / 'level-editor/refinement/blender')]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment', type=Path)
    parser.add_argument('reconstructed', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    experiment, output = args.experiment.resolve(), args.reconstructed.resolve()
    proof_path = output / 'provenance.json'
    proof = read(proof_path)
    assert proof['status'] == 'PASS' and proof['geometry_uv_exact'] and proof['source_rgba_alpha_exact']
    assert proof['model_sha256'] == sha(output / 'model.blend')
    generation_review = read(experiment / 'generation-review.json')
    assert generation_review['status'] == 'ready-for-bake'
    generated = Path(generation_review['generated_preserved_path'])
    assert sha(generated) == generation_review['generated_preserved_sha256']
    donor = read(experiment / 'bake-donor-v1/validation.json')
    assert donor['generated_sha256'] == sha(generated) and donor['geometry_verified']
    assert not (output / 'worker.blend').exists() and not (output / 'actual').exists()
    shutil.copy2(output / 'model.blend', output / 'worker.blend')
    from render_slots import acquire
    acquire()
    import bpy
    from PIL import Image
    from render_multiview_asset import render
    from render_texture_coverage import inspect
    frames = read(experiment / 'views.json')
    bpy.ops.wm.open_mainfile(filepath=str(output / 'worker.blend'))
    render(experiment / 'views.json', output / 'actual', width=frames['tile_size'][0])
    width, height = frames['tile_size']
    sheet = Image.new('RGBA', (4 * width, 2 * height))
    for index in range(8):
        with Image.open(output / 'actual' / f'view-{index}-textured.png') as image:
            assert image.size == (width, height)
            sheet.paste(image, ((index % 4) * width, (index // 4) * height))
    sheet.save(output / 'actual/textured.png')
    assert sha(output / 'worker.blend') == proof['model_sha256']
    validation = dict(donor)
    validation.update(
        status='PASS', projection_kind='preserved-source-atlas-completion',
        model_sha256=proof['model_sha256'], geometry_verified=True,
        outside_objects_unchanged=proof['outside_objects_unchanged'],
        source_preservation='Every approved source RGBA texel, atlas alpha, geometry and UV preserved exactly after reopening; generated colors only fill unknown atlas texels.',
        preservation_report=str(proof_path), preservation_report_sha256=sha(proof_path),
        original_donor_validation=str(experiment / 'bake-donor-v1/validation.json'),
        original_donor_validation_sha256=sha(experiment / 'bake-donor-v1/validation.json'),
        actual_sheet_sha256=sha(output / 'actual/textured.png'),
        review_status='awaiting-independent-actual-and-coverage-review')
    # Keep original donor counters explicitly separate from final atlas counts.
    validation['donor_counts'] = validation.pop('counts')
    validation['counts'] = {
        'protected_texels_including_padding': sum(r['protected_source_texels'] for r in proof['objects']),
        'generated_texels_including_padding': sum(r['completion_texels'] for r in proof['objects'])}
    (output / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    inspect(experiment / 'views.json', output, output / 'coverage', provenance_reports=[proof_path])
    print(json.dumps({'model_sha256': proof['model_sha256'], 'output': str(output), 'status': 'awaiting-visual-review'}), flush=True)


if __name__ == '__main__':
    main()
