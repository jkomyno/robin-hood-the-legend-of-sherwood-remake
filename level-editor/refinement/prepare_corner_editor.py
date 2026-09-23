"""Prepare a source corner editor from one or more refinement review packets.

python3 .../prepare_corner_editor.py --output work/corners/project.json PACKET ...
Loads packet/modified/views.json; copies no art and never edits model inputs.
"""
import argparse
import json
from pathlib import Path


def prepare(packets, output):
    assets = []
    for packet in packets:
        packet = Path(packet).resolve()
        views = json.loads((packet / 'modified/views.json').read_text())
        crop = views['context_crop']
        asset = dict(id=views['asset_id'], name=views['asset_id'].removeprefix('derby-').replace('-', ' ').title(),
                     image_path=views['source_image'], crop=[crop[k] for k in ('left', 'top', 'right', 'bottom')],
                     model_path=str(packet / 'model.blend'), source_camera_elevation=views['elevation_degrees'], paths=[])
        targets = packet / 'source-opening-targets.json'
        if targets.exists():
            records = json.loads(targets.read_text())
            for run, edge in [('lower', 'front'), ('upper', 'rear')]:
                points = [p for r in records if r['id'].startswith(run) for p in r['source_corners']]
                if points:
                    asset['paths'].append(dict(id=run, name=f'{run.title()} {edge} edge — previous estimate', edge=edge, points=points))
        overlay = packet / 'modified/mesh-on-artwork.png'
        if overlay.exists():
            asset.update(overlay_path=str(overlay), overlay_crop=asset['crop'])
        segments = []
        for file in sorted(packet.glob('building-*-actual-segments.json')):
            segments.extend(json.loads(file.read_text()))
        if segments:
            asset['mesh_segments'] = segments
        assets.append(asset)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite project: {output}')
    output.write_text(json.dumps(dict(version=1, assets=assets), separators=(',', ':')) + '\n')
    print(output.resolve())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('packets', nargs='+')
    args = parser.parse_args()
    prepare(args.packets, args.output)
