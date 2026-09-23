"""Check the saved five source-fitted forest forms without mutating their packets."""
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_slots import acquire
from refine_forest_source_forms import refine

acquire()
root = Path(sys.argv[sys.argv.index('--') + 1]).resolve()


def geometry(obj):
    return ([list(v.co) for v in obj.data.vertices],
            [list(f.vertices) for f in obj.data.polygons],
            [list(row) for row in obj.matrix_world])


for suffix in ['bundled-tree', 'tall-trunk', 'east-stump', 'west-stump', 'wood-stack']:
    workspace = root / ('nottingham-forest-' + suffix)
    config = json.loads((workspace / 'workspace.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    objects = list(bpy.data.collections[config['collection_name']].all_objects)
    target, = [o for o in objects if o.type == 'MESH' and o.get('asset_group') == config['asset_id']]
    prior = geometry(target)
    refine(target)
    first = geometry(target)
    refine(target)
    assert first == geometry(target), 'Recipe not idempotent'
    assert first == prior, 'Saved geometry differs from current recipe'
    points = [target.matrix_world @ v.co for v in target.data.vertices]
    views = json.loads((workspace / 'modified/views.json').read_text())
    original = json.loads((workspace / 'input/views.json').read_text())
    width, height = views['tile_size']
    frames = []
    for before, view in zip(original['views'], views['views']):
        for key in ['camera_matrix_world', 'ortho_scale']:
            assert before[key] == view[key], 'Frozen camera changed'
        inverse = Matrix(view['camera_matrix_world']).inverted()
        projected = [inverse @ p for p in points]
        scale = view['ortho_scale']
        extent = max(max(abs(p.x) / (scale * width / height * .5), abs(p.y) / (scale * .5)) for p in projected)
        assert extent < 1, 'View clips geometry'
        frames.append({'view': view['index'], 'maximum_normalized_extent': extent})
    result = {'status': 'PASS', 'idempotence': 'PASS', 'saved_geometry_matches_recipe': True,
              'all_eight_cameras_unchanged': True, 'unclipped_views': frames,
              'model_sha256': hashlib.sha256((workspace / 'model.blend').read_bytes()).hexdigest()}
    (workspace / 'forest-geometry-validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(config['asset_id'], 'PASS', flush=True)
