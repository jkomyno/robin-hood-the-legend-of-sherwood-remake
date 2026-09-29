"""Regenerate bundled terrain with Pillow and the texture-synthesis CLI on PATH.

Usage: python3 scripts/synthesize-terrain.py /path/to/Data/Levels/Day
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('maps', type=Path)
parser.add_argument('--threads', default=8, type=int)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = root / 'app/src/terrain-textures'
out.mkdir(parents=True, exist_ok=True)
work = root / 'work/terrain-textures'
work.mkdir(parents=True, exist_ok=True)
# Day-map pixel rectangles containing only the surface, avoiding props and shadows.
samples = {
    'grass': ('leicester', (1830, 1360, 2025, 1460), 71),
    'dirt': ('leicester', (890, 925, 950, 1005), 72),
    'water': ('leicester', (1710, 70, 1850, 180), 73),
    'paved': ('Nottingham', (610, 1100, 950, 1250), 74),
}
packed = {}
for kind, (name, bounds, seed) in samples.items():
    with Image.open(args.maps / f'{name}.map.png') as source:
        donor = source.crop(bounds).convert('RGB')
    # Undo vertical ground foreshortening before synthesizing a world-space tile.
    donor = donor.resize((donor.width, round(donor.height / 0.573576)), Image.Resampling.BICUBIC)
    donor_path = work / f'{kind}-donor.png'
    donor.save(donor_path)
    masks = []
    if kind == 'paved':
        mask = Image.new('L', (bounds[2] - bounds[0], bounds[3] - bounds[1]))
        # Keep only open flagstones inside the diagonal courtyard balustrade.
        points = [(715, 1140), (890, 1115), (930, 1150), (885, 1175), (785, 1175)]
        ImageDraw.Draw(mask).polygon([(x - bounds[0], y - bounds[1]) for x, y in points], fill=255)
        mask = mask.resize(donor.size, Image.Resampling.NEAREST)
        mask_path = work / 'paved-mask.png'
        mask.save(mask_path)
        masks = ['--sample-masks', str(mask_path)]
    subprocess.run(['texture-synthesis', '--no-progress', '--tiling', '--threads', str(args.threads),
                    *masks, '--seed', str(seed), '--out-size', '256x256', '--out', str(work / f'{kind}.png'),
                    'generate', str(donor_path)], check=True)
    tile = Image.open(work / f'{kind}.png').convert('RGB').quantize(colors=256)
    tile.save(out / f'{kind}.png', optimize=True)
    # Indexed pixels load synchronously in both the browser and offline tests, so
    # an immediate export cannot race image decoding. Each tile is only 64 KiB.
    packed[kind] = {'size': 256, 'palette': base64.b64encode(bytes(tile.getpalette())).decode(),
                    'pixels': base64.b64encode(tile.tobytes()).decode()}
    print(f'Generated {kind}', flush=True)
(out / 'tiles.json').write_text(json.dumps(packed, separators=(',', ':')) + '\n')
