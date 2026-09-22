"""Apply measured rural recipes and rebuild their immutable-camera review packets.

Run in background Blender with --threads 2 --python-exit-code 1. Arguments after
``--`` are workspace directories. This command never approves or publishes an
asset. The initial packet remains immutable; source projection is refreshed only
for the working model and modified packet.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_slots import acquire
from freeze_tooling import select_tooling


def main(workspaces):
    acquire()
    run = ROOT / 'level-editor/work/nottingham-refinement'
    select_tooling(run / 'tooling/315d227e98d52a78')
    import bpy
    from refinement_workspace import initialize_working_masks, modified
    from refine_village_secondary import refine, digest

    def snapshot(predicate=lambda obj: True):
        return {obj.name: {'matrix': [list(row) for row in obj.matrix_world],
                           'geometry': digest(obj), 'hidden': obj.hide_render}
                for obj in bpy.context.scene.objects
                if obj.type == 'MESH' and predicate(obj)}

    for supplied in workspaces:
        workspace = Path(supplied).resolve()
        config = json.loads((workspace / 'workspace.json').read_text())
        name = config['asset_id']
        if name == 'nottingham-village-stream-wall' and config.get('bridge_projection_policy'):
            import refinement_workspace
            from western_bridge_projection import install
            install(refinement_workspace)
        initialize_working_masks(workspace)
        bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
        before = snapshot(lambda obj: obj.get('asset_group') != name)
        report = refine(name)
        after = snapshot(lambda obj: obj.get('asset_group') != name)
        if before != after:
            raise ValueError(f'{name}: changed an outside object')
        first = snapshot()
        refine(name)
        second = snapshot()
        if first != second:
            raise ValueError(f'{name}: recipe is not idempotent')
        inspection = workspace / 'inspection'
        inspection.mkdir(exist_ok=True)
        (inspection / 'idempotence.json').write_text(json.dumps({
            'status': 'PASS', 'asset_id': name, 'scene_meshes': len(first),
            'outside_objects_preserved': len(before),
            'check': 'Second invocation preserves geometry, transforms, visibility and object names.'
        }, indent=2) + '\n')
        report['outside_objects_preserved'] = len(before)
        recipe = Path(__file__).with_name('refine_village_secondary.py')
        report['recipe_sha256'] = hashlib.sha256(recipe.read_bytes()).hexdigest()
        old_path = workspace / 'geometry-recipe.json'
        if report['status'] == 'existing' and old_path.exists():
            previous = json.loads(old_path.read_text())
            previous['idempotence'] = 'PASS'
            previous['current_recipe_sha256'] = report['recipe_sha256']
            report = previous
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
        old_path.write_text(json.dumps(report, indent=2) + '\n')
        print(modified(workspace), flush=True)


if __name__ == '__main__':
    arguments = sys.argv[sys.argv.index('--') + 1:]
    if not arguments:
        raise ValueError('Supply at least one prepared village workspace directory')
    main(arguments)
