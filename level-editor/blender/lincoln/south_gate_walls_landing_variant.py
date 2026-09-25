"""Save a landing-split variant of the angled run (no packet, model.blend untouched).

  SOUTH_GATE_ROUND=round-3 SOUTH_GATE_LANDING_SPLIT=1 /usr/bin/blender --background --threads 2 \
    --python-exit-code 1 --python level-editor/blender/lincoln/south_gate_walls_landing_variant.py
Writes round-3/assets/lincoln-south-curtain-wall-angle/inspection/model-landing-split.blend.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
assert os.environ.get('SOUTH_GATE_LANDING_SPLIT') == '1'
import refine_south_gate as rsg  # noqa: E402
import south_gate_walls_assets as assets  # noqa: E402

ASSET = 'lincoln-south-curtain-wall-angle'


def main():
    import bpy
    ws = rsg.R / os.environ['SOUTH_GATE_ROUND'] / 'assets' / ASSET
    bpy.ops.wm.open_mainfile(filepath=str(ws / 'model.blend'))
    owned = [o for o in bpy.data.collections['lincoln Working'].all_objects
             if o.type == 'MESH' and o.get('asset_group') == ASSET]
    by_key = {(o['source_node'], o.get('projection_component')): o for o in owned}
    built = assets.build_catalog(ASSET, rsg.R)
    report = []
    for comp in ('south-angle-curtain-walk', 'south-wall-stair-top-landing'):
        obj = by_key.get(('building-085', comp))
        if obj is None:
            base = by_key[('building-085', 'south-angle-curtain-walk')]
            obj = base.copy()
            obj.data = base.data.copy()
            obj.name = base.name.split(' :: ')[0] + ' :: ' + comp
            for col in base.users_collection:
                col.objects.link(obj)
            obj['south_gate_component_copy'] = True
            obj['projection_component'] = comp
            obj['asset_group'] = ASSET
        report.append({**rsg.install(obj, built['pieces'][('building-085', comp)], {'role': comp}),
                       'projection_component': comp, 'asset_group': obj['asset_group']})
    out = ws / 'inspection/model-landing-split.blend'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(out), copy=True)
    (ws / 'inspection/model-landing-split.json').write_text(json.dumps(
        {'variant': str(out), 'base_model': str(ws / 'model.blend'), 'pieces': report,
         'untouched': ['building-085/south-angle-bastion-body (owned by lincoln-south-angle-bastion)']}, indent=1) + '\n')
    print('VARIANT', out, [(r['projection_component'], r['vertices'], r['faces'], r['nonmanifold_edges']) for r in report])


main()
