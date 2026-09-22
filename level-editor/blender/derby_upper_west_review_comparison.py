"""Create a source-coordinate inspection panel from the fixed source camera."""
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('review', type=Path)
    args = parser.parse_args()
    root = args.review
    frame = json.loads((root / 'views.json').read_text())
    camera = frame['views'][0]
    assert camera['azimuth_degrees'] == 0
    width, height = frame['tile_size']
    x, y, z = camera['camera_location']
    elevation = math.radians(frame['elevation_degrees'])
    center_y = -y * math.sin(elevation) - z * math.cos(elevation)
    step = camera['ortho_scale'] / height
    bounds = frame['context_crop']
    left, top, right, bottom = [bounds[k] for k in ('left', 'top', 'right', 'bottom')]
    size = right-left, bottom-top
    source = Image.open(frame['source_image']).convert('RGB').crop((left, top, right, bottom))
    panels = [source]
    for mode in ('solid', 'textured'):
        render = Image.open(root / 'views' / f'view-0-{mode}.png').convert('RGB')
        panels.append(render.transform(size, Image.Transform.AFFINE,
            (1/step, 0, (left-x)/step + width/2,
             0, 1/step, (top-center_y)/step + height/2),
            resample=Image.Resampling.BILINEAR))
    sheet = Image.new('RGB', (size[0]*3, size[1]+28), '#202020')
    draw = ImageDraw.Draw(sheet)
    for i, (panel, title) in enumerate(zip(panels, ('Original artwork, unmodified', 'Actual model, 48 degree sun', 'Source-only projection'))):
        sheet.paste(panel, (i*size[0], 28))
        draw.text((i*size[0]+8,8), title, fill='white')
    sheet.save(root / 'source-solid-textured.png')
    (root / 'comparison-coordinates.json').write_text(json.dumps(dict(
        source_crop=bounds, camera_center_source=[x,center_y],
        source_pixels_per_render_pixel=step, source_artwork_modified=False), indent=2))


if __name__ == '__main__':
    main()
