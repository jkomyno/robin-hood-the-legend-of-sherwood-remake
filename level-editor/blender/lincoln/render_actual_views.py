"""Render an asset's stored textures in a worker with its frozen eight review cameras.

    blender --background --threads 2 --python-exit-code 1 <worker.blend> \
      --python level-editor/blender/lincoln/render_actual_views.py -- \
      <asset_id> <workspace views.json> <output dir> [patch,patch...]

Optional applied patches select a state: objects follow reveal_hide_when_applied /
reveal_show_when_applied exactly as the editor does. Writes renders/view-N-textured.png
and a 4x2 sheet textured.png, plus render.json binding worker and camera hashes.
"""
import hashlib
import json
from pathlib import Path
import sys

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'refinement/blender'))
import render_slots  # noqa: E402
from render_multiview_asset import render  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def shown(obj, applied):
    if set(obj.get('reveal_hide_when_applied', [])) & applied:
        return False
    show = obj.get('reveal_show_when_applied')
    return bool(set(show) & applied) if show is not None else True


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    asset, views_path, output = args[0], Path(args[1]), Path(args[2]).resolve()
    applied = set(args[3].split(',')) if len(args) > 3 and args[3] else set()
    render_slots.acquire()
    frozen = json.loads(views_path.read_text())
    if frozen['asset_id'] != asset:
        raise ValueError('Frozen views belong to another asset')
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.get('asset_group') and (
                'reveal_hide_when_applied' in obj or 'reveal_show_when_applied' in obj):
            obj.hide_render = not shown(obj, applied)
    width, height = frozen['tile_size']
    manifest = {'asset_id': asset, 'scene_name': frozen['scene_name'],
                'views': [{'index': v['index'], 'camera_matrix_world': v['camera_matrix_world'],
                           'ortho_scale': v['ortho_scale'], 'crop': {'width': width, 'height': height}}
                          for v in frozen['views']]}
    output.mkdir(parents=True, exist_ok=False)
    (output / 'views.json').write_text(json.dumps(manifest, indent=2) + '\n')
    render(output / 'views.json', output / 'renders', width=width)
    from PIL import Image
    tiles = [Image.open(output / 'renders' / f'view-{i}-textured.png').convert('RGB') for i in range(8)]
    sheet = Image.new('RGB', (width * 4, height * 2))
    for i, tile in enumerate(tiles):
        sheet.paste(tile.resize((width, height)), ((i % 4) * width, (i // 4) * height))
    sheet.save(output / 'textured.png')
    record = {'asset_id': asset, 'worker': bpy.data.filepath, 'worker_sha256': sha(bpy.data.filepath),
              'frozen_views': str(views_path), 'frozen_views_sha256': sha(views_path),
              'applied_patches': sorted(applied), 'sheet_sha256': sha(output / 'textured.png')}
    (output / 'render.json').write_text(json.dumps(record, indent=2) + '\n')
    print('ACTUAL-VIEWS', json.dumps(record))


if __name__ == '__main__':
    main()
