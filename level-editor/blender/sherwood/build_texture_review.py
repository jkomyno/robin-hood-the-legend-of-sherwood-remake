"""Adapt verified Sherwood batch bakes to the normal interactive texture gallery."""
import argparse
import hashlib
import html
import json
import math
import os
from pathlib import Path
import shutil
import sys
from PIL import Image

EDITOR = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(EDITOR/'refinement'), str(EDITOR/'refinement/blender')]
from build_texture_gallery import candidate as checked_candidate
from build_review_gallery import build
from texture_decisions import bind


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2)+'\n')


def link(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha(source) != sha(destination):
            raise ValueError('Immutable review file differs: '+str(destination))
    else:
        os.link(source, destination)


def main(candidate, experiments, inspections, output):
    candidate, experiments, output = [Path(p).resolve() for p in (candidate, experiments, output)]
    fill = json.loads((candidate/'fill.json').read_text())
    worker = candidate/'candidate.blend'
    if sha(worker) != fill['worker_sha256'] or not fill['geometry_and_uvs_unchanged']:
        raise ValueError('Baked worker no longer matches its verification')
    inspected = json.loads(Path(inspections).read_text())['items']
    decisions_path = output/'decisions.json'
    decisions = json.loads(decisions_path.read_text())['decisions'] if decisions_path.exists() else []
    items = []
    by_asset = {}
    artwork_path = experiments.parent/'original-static-art.png'
    artwork = Image.open(artwork_path).convert('RGBA')
    for row in fill['assets']:
        asset = row['asset']
        experiment = experiments/asset
        actual = candidate/'renders'/asset/'textured.png'
        receipt = json.loads((candidate/'renders'/asset/'review.json').read_text())
        inspection = inspected[asset]
        if (receipt['worker_sha256'] != fill['worker_sha256']
                or sha(actual) != receipt['actual_sheet_sha256']
                or inspection['actual_sheet_sha256'] != sha(actual)
                or inspection['all_eight_actual_views_inspected'] is not True):
            raise ValueError('Missing visual inspection of the exact baked views: '+asset)
        generation = experiment/row['generation_directory']
        bake = candidate/'bakes'/asset
        link(worker, bake/'worker.blend')
        link(actual, bake/'actual/textured.png')
        write(bake/'validation.json', {
            'status': 'PASS', 'geometry_verified': True, 'uv_verified': True,
            'protected_changes': row['counts']['protected_changed'],
            'physical_alpha_changes': row['counts']['physical_alpha_changed'],
            'generated_sha256': sha(generation/'generated-preserved.png'),
            'baked_model_sha256': fill['worker_sha256'],
            'source_worker_sha256': fill['source_worker_sha256'],
            'fill_report_sha256': sha(candidate/'fill.json'), 'counts': row['counts'],
        })
        notes = [
            'Existing Sherwood reconstruction, fully reprojected from original artwork before synthesis.',
            f"Generated {row['counts']['generated']} of {row['counts']['unknown']} unknown interior texels; "
            f"{row['counts']['unseen']} remain outside the generated views.",
            f"Actual review views contain {receipt['residual_unknown_pixels']} unknown pixels.",
            *inspection.get('notes', []),
        ]
        write(experiment/'texture-review.json', {
            'status': 'ready-for-user', 'bake': str(bake), 'generation': str(generation),
            'all_eight_actual_views_inspected': True,
            'actual_sheet_sha256': sha(actual), 'baked_model_sha256': fill['worker_sha256'],
            'actual_sheet_path': 'actual/textured.png', 'notes': notes,
        })
        item, _, _ = checked_candidate(experiment, 'Sherwood')
        item['notes'] = ['Texture approval pending.', *notes]
        item['source_comparison_label'] = 'Original-art textures before synthesis'
        views = json.loads((experiment/'views.json').read_text())['views']
        view = views[0]
        if view['azimuth_degrees'] != 0 or view['elevation_degrees'] != 35:
            raise ValueError('Upper-left view is not the original camera: '+asset)
        matrix = view['camera_matrix_world']
        cx = matrix[0][3]
        cy = -(matrix[1][3]*math.sin(math.radians(35))+matrix[2][3]*math.cos(math.radians(35)))
        radius = view['ortho_scale']/2+20
        crop = (max(0, math.floor(cx-radius)), max(0, math.floor(cy-radius)),
                min(artwork.width, math.ceil(cx+radius)), min(artwork.height, math.ceil(cy+radius)))
        if crop[0] >= crop[2] or crop[1] >= crop[3]:
            raise ValueError('Original artwork crop is outside the scene: '+asset)
        reference = output/'original-art'/(asset+'.png')
        reference.parent.mkdir(parents=True, exist_ok=True)
        artwork.crop(crop).save(reference)
        item['artwork_references'] = [dict(id=asset, label='Original artwork with surrounding context',
            path=str(reference), sha256=sha(reference), source=str(artwork_path), source_sha256=sha(artwork_path),
            crop=dict(zip(('left','top','right','bottom'), crop)))]
        if item['id'] in by_asset:
            parent = by_asset[item['id']]
            parent.setdefault('artwork_references', []).extend(item['artwork_references'])
            state_id = 'region-' + asset.removeprefix(item['id']+'-')
            images = ['solid','textured','source_comparison','source_comparison_secondary','source_trace']
            reports = ['validation','review']
            for key in images + reports:
                parent['texture_state_'+state_id+'_'+key] = item[key]
            parent.setdefault('texture_states', []).append({
                'id': state_id, 'name': state_id.replace('-', ' ').title(),
                'image_fields': images, 'report_fields': reports,
                'image_labels': {key:item[key+'_label'] for key in images if key+'_label' in item},
                'model': str(bake/'worker.blend'),
            })
        else:
            if asset != item['id']:
                item['notes'].append('Terrain is split into six regions; review the main sheet and every additional region.')
            items.append(item)
            by_asset[item['id']] = item
    for item in items:
        bind(item, decisions)
    manifest = output/'texture-candidates.json'
    write(manifest, {'map': 'Sherwood texture', 'review_kind': 'texture', 'items': items})
    build(manifest, output/'gallery', map_name='Sherwood texture', pending_only=True)
    # Full-scene context supplements the per-asset decision evidence.
    scene = output/'gallery/scene'
    scene.mkdir(exist_ok=True)
    figures = []
    references = [('original', experiments.parent/'original-static-art.png')]
    source_root = Path(fill['source'])
    for state, directory in [('source-only', source_root/'scene-review'),
                             ('baked', candidate/'scene-review')]:
        references.extend((state+'-'+view, directory/(view+'.png')) for view in ('source','east','west'))
    for label, source in references:
        shutil.copy2(source, scene/(label+'.png'))
        figures.append(f'<figure><figcaption>{html.escape(label.replace("-", " ").title())}</figcaption>'
                       f'<a href="{label}.png"><img loading="lazy" src="{label}.png"></a></figure>')
    (scene/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Sherwood scene texture review</title>'
        '<style>body{background:#171a20;color:#eee;font:16px system-ui;margin:24px}a{color:#afd3ff}'
        'main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}figure{margin:0}'
        'img{width:100%;background:#30343a}figcaption{padding:10px 0}</style>'
        '<h1>Sherwood scene texture review</h1><p><a href="../index.html">Asset review and feedback</a></p>'
        '<main>'+''.join(figures)+'</main>')
    page = output/'gallery/index.html'
    page.write_text(page.read_text().replace('<nav>', '<p><a href="scene/index.html">Full-map and oblique comparisons</a></p><nav>', 1))
    print(json.dumps({'gallery': str(page), 'candidates': len(items)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--experiments', required=True)
    parser.add_argument('--inspections', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    main(args.candidate, args.experiments, args.inspections, args.output)
