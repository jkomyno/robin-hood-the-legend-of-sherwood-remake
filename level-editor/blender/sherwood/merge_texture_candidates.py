"""Combine disjoint normal-bake batches without transferring any geometry."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import texture_packets as tp


def main(source, parts, output, targets):
    source, output = Path(source).resolve(), Path(output).resolve()
    expected = {row['id'] for row in json.loads(Path(targets).read_text())['targets']}
    reports = [(Path(p).resolve(), json.loads((Path(p)/'fill.json').read_text())) for p in parts]
    assets = [row for _, report in reports for row in report['assets']]
    assert len(assets) == len(expected) and {r['asset'] for r in assets} == expected
    scene, provenance = tp.open_source(source)
    geometry = tp.uf.geometry_record(scene)
    objects = {row['object'].name: row['object'] for row in scene.meshes}
    occupied = set()
    output.mkdir(parents=True, exist_ok=False)
    evidence = []
    for part, report in reports:
        assert report['source_worker_sha256'] == provenance['worker_sha256']
        assert tp.uf.sha(part/'candidate.blend') == report['worker_sha256']
        assert report['geometry_and_uvs_unchanged'] is True
        claimed = {update['object'] for update in report['atlas_updates']}
        assert not occupied.intersection(claimed), 'Bake batches share receiver objects'
        occupied.update(claimed)
        for update in report['atlas_updates']:
            obj = objects[update['object']]
            binding, kind = tp.fillable(scene, obj, update['slot'])
            assert binding['image'].name == update['image']
            assert kind.physical == update['physical_alpha']
            assert tp.uf.sha(update['path']) == update['sha256']
            ownership = report['ownership'][obj.name]
            assert tp.uf.sha(ownership['path']) == ownership['sha256']
            with np.load(ownership['path']) as data: flags = data['ownership']
            with np.load(update['path']) as data: atlas = data['rgba']
            original = tp.gr.read_image(binding['image'])
            assert flags.shape == kind.mask.shape and atlas.shape == original.shape
            assert set(np.unique(flags)) <= {0, 1, 2}
            assert np.array_equal(flags == 1, kind.mask == 1)
            assert np.array_equal(atlas[flags == 1], original[flags == 1]), obj.name
            assert np.array_equal(atlas[flags == 0, :3], original[flags == 0, :3]), obj.name
            if kind.physical:
                assert np.array_equal(atlas[..., 3], original[..., 3]), obj.name
            tp.gr.write_image(binding['image'], atlas)
            binding['image'].alpha_mode = update['alpha_mode']
            for key, value in update['material_properties'].items():
                binding['material'][key] = value
            tp.MASKS[obj.name] = flags
        evidence.append({'path': str(part), 'fill_sha256': tp.uf.sha(part/'fill.json'),
                         'worker_sha256': report['worker_sha256']})
    assert tp.uf.geometry_record(scene) == geometry
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'candidate.blend'))
    (output/'ownership').mkdir()
    masks = {}
    for name, flags in tp.MASKS.items():
        path = output/'ownership'/(hashlib.sha256(name.encode()).hexdigest()[:20]+'.npz')
        np.savez_compressed(path, ownership=flags)
        masks[name] = {'path': str(path), 'sha256': tp.uf.sha(path)}
    tp.write(output/'fill.json', {
        'status': 'CANDIDATE_REVIEW_PENDING', 'assets': sorted(assets, key=lambda r: r['asset']),
        'source': str(source), 'source_worker_sha256': provenance['worker_sha256'],
        'worker_sha256': tp.uf.sha(output/'candidate.blend'), 'geometry_and_uvs_unchanged': True,
        'ownership': masks, 'ownership_semantics': reports[0][1]['ownership_semantics'],
        'bake_batches': evidence,
    })
    print(json.dumps({'merged_assets': len(assets), 'output': str(output)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--part', action='append', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--targets', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    main(args.source, args.part, args.output, args.targets)
