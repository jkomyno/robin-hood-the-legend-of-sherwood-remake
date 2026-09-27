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


def review_revision(preparation):
    binding = dict(images={'solid': preparation['files']['solid.png'],
                           'textured': preparation['files']['input.png']},
                   reports={'validation': preparation['files']['views.json']})
    return hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()


def source_first_sheets(folder, output, asset):
    """Reorder gallery copies; synthesis packets and their generated results stay bound."""
    manifest = json.loads((folder/'views.json').read_text())
    views = manifest['views']
    source = next(v for v in views if (v['azimuth_degrees'], v['elevation_degrees']) == (0, 35))
    if views[0] == source and source['crop']['left'] == source['crop']['top'] == 0:
        return folder
    destination = output/'source-first'/asset
    destination.mkdir(parents=True, exist_ok=True)
    order = [source] + [v for v in views if v != source]
    reordered = []
    for name in ('solid.png', 'input.png'):
        with Image.open(folder/name) as original:
            sheet = Image.new(original.mode, original.size)
            for index, view in enumerate(order):
                crop = view['crop']
                left, top, width, height = (crop[k] for k in ('left', 'top', 'width', 'height'))
                target = views[index]['crop']
                sheet.paste(original.crop((left, top, left+width, top+height)),
                            (target['left'], target['top']))
            sheet.save(destination/name)
    for index, view in enumerate(order):
        reordered.append({**view, 'source_packet_index': view['index'],
                          'index': index, 'crop': views[index]['crop']})
    manifest.update(views=reordered, source_packet_views_sha256=hashlib.sha256((folder/'views.json').read_bytes()).hexdigest(),
                    gallery_change='Source-camera tile moved first; original tile pixels unchanged.')
    (destination/'views.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return destination


def main(packets, output):
    packets, output = Path(packets).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = json.loads((packets/'targets.json').read_text())['targets']
    inspections_path = output/'inspections.json'
    inspections = json.loads(inspections_path.read_text()) if inspections_path.exists() else {}
    decisions_path = Path(__file__).with_name('model-decisions.json')
    decisions = {d['id']: d for d in json.loads(decisions_path.read_text())['decisions']}
    grouping_root = output.parent/'grouping-review'
    regrouped = {}
    if (grouping_root/'stage.json').exists():
        plan = json.loads((grouping_root/'plan.json').read_text())
        stage = json.loads((grouping_root/'stage.json').read_text())
        if stage['catalog_sha256'] != hashlib.sha256((grouping_root/'catalog.json').read_bytes()).hexdigest():
            raise ValueError('Changed grouping candidate catalog')
        for group in plan['groups']:
            if group['changed']:
                for previous in group['previous_assets']:
                    regrouped.setdefault(previous, []).append(group['id'])
    artwork_path = packets.parent/'original-static-art.png'
    artwork = Image.open(artwork_path).convert('RGBA')
    artwork_hash = hashlib.sha256(artwork_path.read_bytes()).hexdigest()
    references = output/'original-art'
    references.mkdir(exist_ok=True)
    items, missing, reviewed = [], [], []
    for target in targets:
        asset = target['id']
        name = asset.removeprefix('sherwood-').replace('-', ' ').title()
        folder = packets/asset
        if not (folder/'preparation.json').exists():
            if asset in regrouped:
                continue
            missing.append(dict(id=asset, name=name, status='Rendering', reason='Eight-view model sheets are being prepared.'))
            continue
        preparation = json.loads((folder/'preparation.json').read_text())
        for key in ('input.png', 'solid.png', 'views.json'):
            if hashlib.sha256((folder/key).read_bytes()).hexdigest() != preparation['files'][key]:
                raise ValueError('Changed model review evidence: '+asset+'/'+key)
        decision = decisions.get(asset)
        if decision and decision['review_revision'] == review_revision(preparation):
            reviewed.append(dict(name=name, **decision))
            continue
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
        display_folder = source_first_sheets(folder, output, asset)
        display_revision = review_revision({'files': {key: hashlib.sha256((display_folder/key).read_bytes()).hexdigest()
            for key in ('solid.png', 'input.png', 'views.json')}})
        if decision and decision['review_revision'] == display_revision:
            reviewed.append(dict(name=name, **decision))
            continue
        if asset in regrouped:
            continue
        items.append(dict(id=asset, name=name, status='ready-for-user' if inspected else 'in-progress',
            user_approval='pending', solid=str(display_folder/'solid.png'), textured=str(display_folder/'input.png'),
            textured_label='Original-art projection; shaded gray marks unknown textures',
            validation=str(display_folder/'views.json'),
            artwork_references=[dict(id='original', label='Original artwork — source view with surrounding context',
                path=str(reference_path), sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),
                source=str(artwork_path), source_sha256=artwork_hash,
                crop=dict(zip(('left','top','right','bottom'), crop)))],
            notes=['Model review only: existing Sherwood reconstruction, with the published geometry unchanged.',
                   'No newly synthesized textures are shown.',
                   'Upper-left tile: original artwork camera (azimuth 0°, elevation 35°).',
                   'Inherited coarse background props and inferred hidden geometry remain visible for review.',
                   'Eight-view visual check complete.' if inspected else 'Visual preflight pending; feedback is available now.']))
    manifest=output/'models.json'
    manifest.write_text(json.dumps(dict(map='Sherwood models',items=items,without_packets=missing,reviewed=reviewed,
        superseded_by_grouping=regrouped,
        status_counts={'ready for review':sum(i['status']=='ready-for-user' for i in items),
                       'visual check pending':sum(i['status']!='ready-for-user' for i in items),
                       'approved':sum(i['decision']=='approved' for i in reviewed),
                       'awaiting refinement':sum(i['decision']=='needs refinement' for i in reviewed),
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
    reviewed_summary = '<details><summary>Recorded reviews</summary><ul>'+''.join(
        '<li>'+html.escape(i['name']+': '+i['decision']+(' — '+i['note'] if i['note'] else ''))+'</li>'
        for i in reviewed)+'</ul></details>'
    if regrouped:
        reviewed_summary += '<p><strong>Grouping has been revised.</strong> <a href="grouping/index.html">Review the regrouped assets here</a>.</p>'
    page.write_text(page.read_text().replace('<nav>', '<p><a href="scene/index.html">Full-scene model views and original artwork</a></p>'
        +reviewed_summary+'<nav>',1))
    print(json.dumps({'gallery':str(page),'available':len(items),'rendering':len(missing)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--packets',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();main(args.packets,args.output)
