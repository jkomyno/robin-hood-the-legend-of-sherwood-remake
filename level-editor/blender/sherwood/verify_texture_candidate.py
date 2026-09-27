"""Independently reopen a texture candidate and compare it with its source worker."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import texture_packets as tp


def digest(values):
    return hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()


def verify(candidate):
    candidate = Path(candidate).resolve()
    fill = json.loads((candidate/'fill.json').read_text())
    source = Path(fill['source'])
    scene, provenance = tp.open_source(source)
    assert provenance['worker_sha256'] == fill['source_worker_sha256']
    geometry = tp.uf.geometry_record(scene)
    expected = {}
    for record in scene.meshes:
        obj = record['object']
        for slot in np.unique(record['slots']):
            binding, kind = tp.fillable(scene, obj, int(slot))
            atlas = tp.gr.read_image(binding['image'])
            known = kind.mask == 1
            expected[(obj.name, int(slot))] = {
                'source_rgb': digest(atlas[known, :3]),
                'alpha': digest(atlas[..., 3] if kind.physical else atlas[known, 3]),
                'physical_alpha': kind.physical,
                'source_texels': int(known.sum()),
            }
    original_masks = {name: mask.copy() for name, mask in tp.MASKS.items()}
    worker = candidate/'candidate.blend'
    assert tp.uf.sha(worker) == fill['worker_sha256']
    _, scene = tp.uf.open_worker(worker)
    assert tp.uf.geometry_record(scene) == geometry
    assert set(fill['ownership']) == set(original_masks)
    final_masks = {}
    for name, evidence in fill['ownership'].items():
        assert tp.uf.sha(evidence['path']) == evidence['sha256'], name
        with np.load(evidence['path']) as data:
            flags = data['ownership']
        original = original_masks[name]
        assert flags.shape == original.shape and set(np.unique(flags)) <= {0, 1, 2}, name
        assert np.array_equal(flags == 1, original == 1), name
        final_masks[name] = flags
    checked = set()
    for record in scene.meshes:
        obj = record['object']
        for slot in np.unique(record['slots']):
            key = (obj.name, int(slot))
            binding = scene.slot_binding(obj, int(slot))
            atlas = tp.gr.read_image(binding['image'])
            flags = final_masks[obj.name]
            assert digest(atlas[flags == 1, :3]) == expected[key]['source_rgb'], key
            # Non-foliage alpha stores source ownership in this legacy atlas
            # format; synthesis intentionally sets generated texels to zero.
            # Physical coverage and source texel alpha must remain exact.
            alpha = atlas[..., 3] if expected[key]['physical_alpha'] else atlas[flags == 1, 3]
            assert digest(alpha) == expected[key]['alpha'], key
            assert np.all(atlas[flags == 0, :3] == 128), key
            checked.add(key)
    assert checked == set(expected)
    result = {
        'status': 'PASS_SAVED_TEXTURE_CANDIDATE',
        'worker_sha256': fill['worker_sha256'],
        'source_worker_sha256': fill['source_worker_sha256'],
        'checked_meshes': len(scene.meshes),
        'protected_source_texels': sum(v['source_texels'] for v in expected.values()),
        'protected_rgb_changes': 0, 'physical_alpha_changes': 0,
        'protected_source_alpha_changes': 0,
        'geometry_and_uvs_unchanged': True,
        'unassigned_color_changes': 0,
        'texture_approval': 'pending',
    }
    tp.write(candidate/'saved-worker-verification.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    verify(args.candidate)
