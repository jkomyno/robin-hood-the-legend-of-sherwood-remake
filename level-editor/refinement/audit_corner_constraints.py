"""Freeze and independently verify user corner constraints before a Blender rebuild."""
import argparse
import hashlib
import json
from pathlib import Path


def derive(rails):
    a, b = rails['upper']
    if a[0] == b[0] or rails['depth'] <= 0:
        raise ValueError('Incomplete or degenerate boundary')
    direction = 1 if b[0] > a[0] else -1
    stations = sorted(set(rails['transitions']), reverse=direction < 0)
    if any(not min(a[0], b[0]) < x < max(a[0], b[0]) for x in stations):
        raise ValueError('Transition outside boundary endpoints')
    lower = not rails['startsUpper']
    def point(x):
        y = a[1] + (x-a[0]) * (b[1]-a[1]) / (b[0]-a[0])
        return [x, y + (rails['depth'] if lower else 0)]
    points = [point(a[0])]
    for x in stations:
        points.append(point(x))
        lower = not lower
        points.append(point(x))
    points.append(point(b[0]))
    return points, stations


def audit(source, output):
    from PIL import Image, ImageDraw
    source, output = Path(source), Path(output)
    raw = source.read_bytes()
    data = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    frozen = output / 'user-corners.json'
    if frozen.exists() and frozen.read_bytes() != raw:
        raise FileExistsError('Use a new output directory for different user constraints')
    frozen.write_bytes(raw)
    report = dict(source=str(source.resolve()), sha256=digest, assets=[])
    for asset in data['assets']:
        paths = [p for p in asset['paths'] if p.get('rails')]
        if not paths:
            continue
        image_path = Path(asset['image_path'])
        if hashlib.sha256(image_path.read_bytes()).hexdigest() != asset['source_sha256']:
            raise ValueError(f"Artwork changed: {asset['id']}")
        art = Image.open(image_path).convert('RGB')
        crop = asset['crop']
        original = art.crop(crop).resize(((crop[2]-crop[0])*3, (crop[3]-crop[1])*3), Image.Resampling.NEAREST)
        marked = original.copy()
        draw = ImageDraw.Draw(marked)
        results = []
        for i, path in enumerate(paths):
            points, stations = derive(path['rails'])
            if len(points) != len(path['points']):
                raise ValueError('Saved corners disagree with rail constraints')
            error = max(abs(a-b) for p, q in zip(points, path['points']) for a, b in zip(p, q))
            if error > 1e-8:
                raise ValueError(f'Saved corner drift: {error}')
            color = ['#63ffd4', '#ffda66'][i % 2]
            projected = [((x-crop[0])*3, (y-crop[1])*3) for x, y in points]
            draw.line(projected, fill=color, width=2)
            for j, (x, y) in enumerate(projected):
                draw.ellipse((x-2,y-2,x+2,y+2), fill=color)
                draw.text((x+4,y-10), str(j+1), fill=color, stroke_width=1, stroke_fill='black')
            results.append(dict(id=path['id'], edge=path['edge'], rails=path['rails'],
                                sorted_transition_x=stations, derived_points=points,
                                saved_corner_max_error_pixels=error,
                                ends_on_upper=path['rails']['startsUpper'] == (len(stations) % 2 == 0)))
        name = asset['id']
        original.save(output / f'{name}-original.png')
        marked.save(output / f'{name}-user-corners.png')
        report['assets'].append(dict(id=name, source_sha256=asset['source_sha256'], paths=results))
    (output / 'audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(sha256=digest, assets=[a['id'] for a in report['assets']])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('output')
    args = parser.parse_args()
    audit(args.source, args.output)
