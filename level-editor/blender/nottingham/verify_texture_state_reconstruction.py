"""Bind historical display-state packets to immutable approved scene models.

Reproduce the complete geometry/source ownership packet and separately render
the actual saved face materials. No state scene copy or material rewrite is
needed when the display selection reproduces the approved packet exactly.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'level-editor/refinement/blender'))
sys.path.insert(0, str(Path(__file__).parent))
import bpy
import numpy as np
from audit_stored_materials import run as audit_materials
from refinement_review import render_review
from render_slots import acquire


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pixels(path):
    image = bpy.data.images.load(str(path), check_existing=False)
    values = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(values)
    result = (tuple(image.size), values)
    bpy.data.images.remove(image)
    return result


def verify(row, output):
    workspace = Path(row['workspace'])
    model = workspace / 'model.blend'
    frame = Path(row['frame_manifest'])
    frozen = json.loads(frame.read_text())
    before = {str(p): digest(p) for p in (model, frame)}
    assert before[str(model)] == row['approval_model_sha256']
    assert before[str(frame)] == row['frame_manifest_sha256']
    names = frozen['render_object_names']
    assert sorted(names) == sorted(frozen['object_names'])
    bpy.ops.wm.open_mainfile(filepath=str(model))
    bpy.context.view_layer.update()
    render_review(output / 'reproduced',
                  scene_name=frozen['scene_name'], collection_name=frozen['collection_name'],
                  asset_id=frozen['asset_id'], source_path=frozen['source_image'],
                  frame_manifest=frame, projection_layers=frozen['projection_layers'],
                  source_mask_manifest=frozen.get('source_mask_manifest'),
                  render_object_names=names, lighting=frozen['lighting'],
                  framing_padding=frozen.get('framing_padding', 1.04))
    comparisons = []
    for relative in ['solid.png', 'textured.png'] + [
            f'views/view-{i}-{kind}.png' for i in range(8)
            for kind in ('solid', 'textured', 'known')]:
        old, new = frame.parent / relative, output / 'reproduced' / relative
        old_size, old_values = pixels(old)
        new_size, new_values = pixels(new)
        equal = old_size == new_size and np.array_equal(old_values, new_values)
        comparisons.append({'relative': relative, 'approved_sha256': digest(old),
                            'reproduced_sha256': digest(new), 'pixels_equal': equal})
    material_output = output / 'actual-materials'
    material = audit_materials(workspace, material_output, render=True,
                              render_object_names=names, frame_manifest=frame)
    unchanged = all(digest(p) == value for p, value in before.items())
    passed = unchanged and all(c['pixels_equal'] for c in comparisons) and material['status'] == 'STRUCTURAL-PASS'
    report = {'version': 1, 'status': 'PASS' if passed else 'FAIL',
              'asset_id': frozen['asset_id'], 'workspace': str(workspace),
              'frame_manifest': str(frame), 'frame_manifest_sha256': digest(frame),
              'source_blend': str(model), 'source_blend_sha256': digest(model),
              'render_object_names': names, 'approved_inputs_unchanged': unchanged,
              'source_rgb_preserved': all(c['pixels_equal'] for c in comparisons if 'textured' in c['relative']),
              'solid_pixels_preserved': all(c['pixels_equal'] for c in comparisons if 'solid' in c['relative']),
              'ownership_buffers_reproduced': all(c['pixels_equal'] for c in comparisons if 'known' in c['relative']),
              'comparisons': comparisons,
              'actual_material_check': {'path': str(material_output / 'audit.json'),
                                        'sha256': digest(material_output / 'audit.json'),
                                        'status': material['status']},
              'limitations': ['Actual material structural validation is separate from visual inspection; this report proves exact approved display-state reconstruction, not newly generated texture quality.']}
    (output / 'state-binding.json').write_text(json.dumps(report, indent=2) + '\n')
    print('STATE PROOF', frame, report['status'], flush=True)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--asset', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.output = args.output.resolve()
    inventory = ROOT / 'level-editor/work/nottingham-refinement/texture-generation/lighting-audit/audit.json'
    rows = [r for r in json.loads(inventory.read_text())['packets']
            if r['asset_id'] == args.asset and not r.get('saved_state_model')]
    assert rows, args.asset
    args.output.mkdir(parents=True, exist_ok=False)
    acquire()
    states = []
    for index, row in enumerate(rows):
        destination = args.output / f'state-{index}'
        destination.mkdir()
        states.append(verify(row, destination))
        status = 'FAIL' if any(s['status'] != 'PASS' for s in states) else (
            'PASS' if len(states) == len(rows) else 'INCOMPLETE')
        report = {'version': 1, 'asset_id': args.asset, 'states': states, 'status': status}
        (args.output / 'state-bindings.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['status'] != 'PASS':
        raise RuntimeError('State packet reconstruction differs from approved evidence')


if __name__ == '__main__':
    main()
