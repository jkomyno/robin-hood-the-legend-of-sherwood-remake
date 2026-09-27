"""Build Sherwood's geometry gallery from source-only multi-view packets."""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import sys
from PIL import Image

EDITOR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EDITOR/'refinement/blender'))
from build_review_gallery import build


def main(packets, output):
    packets, output = Path(packets).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = json.loads((packets/'targets.json').read_text())['targets']
    inspections_path = output/'inspections.json'
    inspections = json.loads(inspections_path.read_text()) if inspections_path.exists() else {}
    artwork_path = packets.parent/'original-static-art.png'
    artwork = Image.open(artwork_path).convert('RGBA')
    artwork_hash = hashlib.sha256(artwork_path.read_bytes()).hexdigest()
    references = output/'original-art'
    references.mkdir(exist_ok=True)
    items, missing = [], []
    for target in targets:
        asset = target['id']
        name = asset.removeprefix('sherwood-').replace('-', ' ').title()
        folder = packets/asset
        if not (folder/'preparation.json').exists():
            missing.append(dict(id=asset, name=name, status='Rendering', reason='Eight-view model sheets are being prepared.'))
            continue
        preparation = json.loads((folder/'preparation.json').read_text())
        for key in ('input.png', 'solid.png', 'views.json'):
            if hashlib.sha256((folder/key).read_bytes()).hexdigest() != preparation['files'][key]:
                raise ValueError('Changed model review evidence: '+asset+'/'+key)
        inspection = inspections.get(asset, {})
        views = json.loads((folder/'views.json').read_text())['views']
        source_view = next(v for v in views if v['azimuth_degrees'] == 0 and v['elevation_degrees'] == 35)
        matrix = source_view['camera_matrix_world']
        # The original orthographic artwork uses world x horizontally and
        # -(y*sin(35)+z*cos(35)) vertically. Camera distance cancels out.
        cx = matrix[0][3]
        cy = -(matrix[1][3]*math.sin(math.radians(35)) + matrix[2][3]*math.cos(math.radians(35)))
        radius = source_view['ortho_scale']/2 + 20
        crop = (max(0, math.floor(cx-radius)), max(0, math.floor(cy-radius)),
                min(artwork.width, math.ceil(cx+radius)), min(artwork.height, math.ceil(cy+radius)))
        if crop[0] >= crop[2] or crop[1] >= crop[3]:
            raise ValueError('Original artwork crop is outside the scene: '+asset)
        reference_path = references/(asset+'.png')
        artwork.crop(crop).save(reference_path)
        inspected = (inspection.get('views_sha256') == preparation['files']['views.json']
                     and inspection.get('all_eight_solid_and_source_views_inspected') is True)
        items.append(dict(id=asset, name=name, status='ready-for-user' if inspected else 'in-progress',
            user_approval='pending', solid=str(folder/'solid.png'), textured=str(folder/'input.png'),
            textured_label='Original-art projection; shaded gray marks unknown textures',
            validation=str(folder/'views.json'),
            artwork_references=[dict(id='original', label='Original artwork — source view with surrounding context',
                path=str(reference_path), sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),
                source=str(artwork_path), source_sha256=artwork_hash,
                crop=dict(zip(('left','top','right','bottom'), crop)))],
            notes=['Model review only: existing Sherwood reconstruction, with the published geometry unchanged.',
                   'No newly synthesized textures are shown.',
                   'Inherited coarse background props and inferred hidden geometry remain visible for review.',
                   'Eight-view visual check complete.' if inspected else 'Visual preflight pending; feedback is available now.']))
    manifest=output/'models.json'
    manifest.write_text(json.dumps(dict(map='Sherwood models',items=items,without_packets=missing,
        status_counts={'ready for review':sum(i['status']=='ready-for-user' for i in items),
                       'visual check pending':sum(i['status']!='ready-for-user' for i in items),
                       'rendering':len(missing)}),indent=2)+'\n')
    build(manifest,output/'gallery',map_name='Sherwood models',pending_only=False)
    scene=output/'gallery/scene';scene.mkdir(exist_ok=True)
    figures=[]
    for label, source in [('Original artwork',packets.parent/'original-static-art.png'),
                          *[(f'Source-only {v} view',packets.parent/'source-review'/(v+'.png')) for v in ('source','east','west')]]:
        target=label.lower().replace(' ','-')+'.png';shutil.copy2(source,scene/target)
        figures.append(f'<figure><figcaption>{html.escape(label)}</figcaption><a href="{target}"><img src="{target}"></a></figure>')
    (scene/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Sherwood model context</title>'
        '<style>body{background:#171a20;color:#eee;font:16px system-ui;margin:24px}a{color:#afd3ff}'
        'main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}figure{margin:0}img{width:100%}</style>'
        '<h1>Sherwood model context</h1><p><a href="../index.html">Back to model review</a></p>'
        '<p>Original-art projection on published geometry. Gray marks unknown surfaces; no new AI textures are shown.</p><main>'+''.join(figures)+'</main>')
    page=output/'gallery/index.html'
    page.write_text(page.read_text().replace('<nav>', '<p><a href="scene/index.html">Full-scene model views and original artwork</a></p><nav>',1))
    print(json.dumps({'gallery':str(page),'available':len(items),'rendering':len(missing)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--packets',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();main(args.packets,args.output)
