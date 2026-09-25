"""Render a disposable paired roof/tower inspection without regrouping either asset."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'level-editor/refinement/blender'), str(Path(__file__).parent)]


def main():
    import bpy
    from render_slots import acquire
    from refinement_review import render_review
    from audit_stored_materials import run
    from correct_spire_metal_ridges import sha
    parent = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    source = parent / 'paired-source-audit'
    output = parent / 'paired-visual-review'
    output.mkdir(exist_ok=False)
    acquire(slots=2)
    bpy.ops.wm.open_mainfile(filepath=str(source / 'model.blend'))
    config = json.loads((source / 'workspace.json').read_text())
    original_groups = {}
    for obj in bpy.data.collections[config['collection_name']].all_objects:
        if obj.type == 'MESH' and obj.get('asset_group') in ['nottingham-castle-main-hall', 'nottingham-castle-northwest-spire']:
            original_groups[obj.name] = obj['asset_group']
            obj['asset_group'] = 'nottingham-paired-hall-northwest-contact'
    config['asset_id'] = 'nottingham-paired-hall-northwest-contact'
    config['source_mask_manifest'] = str(source / 'source-masks.json')
    (output / 'workspace.json').write_text(json.dumps(config, indent=2) + '\n')
    (output / 'original-groups.json').write_text(json.dumps(original_groups, indent=2) + '\n')
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'model.blend'))
    render_review(output / 'modified', scene_name=config['scene_name'], collection_name=config['collection_name'],
                  asset_id=config['asset_id'], source_path=config['source_path'], width=512, height=512,
                  context_padding=25, framing_padding=1.08, lighting=config['lighting'],
                  source_mask_manifest=config['source_mask_manifest'])
    audit = run(output, output / 'actual', render=True, export=False)
    assert not audit['problems'], audit['problems']
    (output / 'scope.json').write_text(json.dumps(dict(
        source_pair_sha256=sha(source / 'model.blend'), model_sha256=sha(output / 'model.blend'),
        purpose='Inspection-only display grouping; original canonical asset groups retained in original-groups.json.',
        geometry_and_materials_changed=False), indent=2) + '\n')


if __name__ == '__main__':
    main()
