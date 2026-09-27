"""Extract Robin's original animations into transparent looping AVIF header assets."""
import json
from pathlib import Path
import subprocess
import tempfile
from PIL import Image

EDITOR = Path(__file__).resolve().parents[1]
SOURCE = EDITOR.parent / 'datadirs/fullgame_gog_hackable'
OUTPUT = EDITOR / 'app/src/assets'

def main():
    sequences = []
    for name, directory, actions, direction in (
        ('robin-bored', 'Data/Characters/RobinHood.rhs.d', ['WaitingUprightBored'], 6),
        ('robin-bored-random', 'Data/Characters/RobinHood.rhs.d', ['WaitingUprightBoredRandom'], 6),
        ('robin-to-dance', 'Data/Characters/RobinHood.rhs.d', ['TransitionWaitingUprightBoredWaitingUpright'], 6),
        ('robin-from-dance', 'Data/Characters/RobinHood.rhs.d', ['TransitionWaitingUprightWaitingUprightBored'], 6),
        ('robin-dancing', 'Data/Animations/Day/Z_Robin.rhs.d', ['Target210', 'Target211', 'Target212'], 0),
    ):
        root = SOURCE / directory
        manifest = json.loads((root / 'manifest.json').read_text())
        frames = []
        for action in actions:
            row = next(row for row in manifest['profiles'][0]['rows']
                       if row['action'] == action and row['direction'] == direction)
            for frame in row['frames']:
                image = Image.open(root / row['path'] / frame['file']).convert('RGBA')
                pixels = []
                for red, green, blue, alpha in image.get_flattened_data():
                    packed = ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)
                    if packed == 0x07c0:
                        pixels.append((0, 0, 0, 0))
                    elif packed == 0x001f or (name == 'robin-dancing' and (red, green, blue) == (0, 0, 0)):
                        # RGB565 blue is the character shadow; the camp sequence bakes it as black.
                        pixels.append((0, 0, 0, round(alpha * 0.4)))
                    else:
                        pixels.append((red, green, blue, alpha))
                image.putdata(pixels)
                frames.append((image, int(frame['offset_x'] - row['hotspot_x']), int(frame['offset_y'] - row['hotspot_y']), max(1, frame['delay'] + 1)))
        sequences.append((name, frames))
    # Frames are placed relative to their row hotspot, not cropped-content bounds.
    # One union canvas and one exported anchor work for any characters/sequences.
    left = min(x for _, frames in sequences for _, x, _, _ in frames) - 2
    top = min(y for _, frames in sequences for _, _, y, _ in frames) - 2
    right = max(x + image.width for _, frames in sequences for image, x, _, _ in frames) + 2
    bottom = max(y + image.height for _, frames in sequences for image, _, y, _ in frames) + 2
    OUTPUT.mkdir(exist_ok=True)
    metadata = {name: sum(frame[3] for frame in frames) * 40 for name, frames in sequences}
    metadata['canvas'] = {'width': right-left, 'height': bottom-top, 'anchorX': -left, 'anchorY': -top}
    (OUTPUT / 'robin-animation.json').write_text(json.dumps(metadata, indent=2) + '\n')
    with tempfile.TemporaryDirectory(prefix='robin-mascot-') as temporary:
        for name, frames in sequences:
            command = ['avifenc', '-q', '60', '--qalpha', '100', '--speed', '6', '--jobs', '4', '--fps', '25', '--repetition-count', '0' if name in ('robin-bored-random', 'robin-to-dance', 'robin-from-dance') else 'infinite']
            for index, (image, x, y, delay) in enumerate(frames):
                canvas = Image.new('RGBA', (right - left, bottom - top))
                canvas.paste(image, (x - left, y - top))
                path = Path(temporary) / f'{name}-{index:03}.png'
                canvas.save(path)
                if name == 'robin-bored' and index == 0:
                    canvas.save(OUTPUT / 'robin-still.png')
                command.extend(['--duration', str(delay), str(path)])
            command.extend(['-o', str(OUTPUT / f'{name}.avif')])
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
            print(f'{name}: {len(frames)} frames, {right-left}×{bottom-top}, {(OUTPUT / (name+".avif")).stat().st_size} bytes')

if __name__ == '__main__':
    main()
