"""Write immutable, verified provenance for an already completed inferred transfer.

Blender CLI: -- transferred-bake fresh-proof-directory
Reads existing replay evidence only; never replays, edits or saves a model.
The resulting report.json can be passed to render_texture_coverage's
--provenance-report option. Original validation and masks remain untouched.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def updated_ownership(donor_rgba, target_rgba, final_rgba, donor_mask, target_mask):
    """Verify the exact transfer equation, then label only selected texels generated."""
    from transfer_shared_inferred import merge_inferred
    expected, count = merge_inferred(donor_rgba, target_rgba, donor_mask, target_mask)
    if final_rgba.shape != expected.shape or not np.array_equal(final_rgba, expected):
        raise ValueError('Final saved RGBA differs from exact inferred transfer')
    selected = (donor_mask == 2) & (target_mask != 1)
    result = target_mask.copy()
    result[selected] = 2
    if not np.array_equal(result[~selected], target_mask[~selected]):
        raise ValueError('Unselected ownership changed')
    return result, count


def run(bake, output):
    import bpy
    bake, output = Path(bake).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Supplemental provenance directory must be fresh')
    validation_path = bake / 'validation.json'
    validation = json.loads(validation_path.read_text())
    transfer = validation['shared_inferred_transfer']
    if transfer.get('allow_bounded_donors'):
        raise ValueError('This historical supplement supports donor class2 only; bounded-donor transfers require their own validated provenance report')
    for key in ('geometry_preserved', 'outside_appearance_preserved',
                'target_observed_rgba_preserved', 'all_target_alpha_preserved'):
        if transfer.get(key) is not True:
            raise ValueError('Transfer lacks required verification: ' + key)
    model = bake / 'worker.blend'
    if validation['model_sha256'] != sha(model):
        raise ValueError('Transferred model differs from validated model')
    bindings = dict(transfer['inputs_sha256'])
    bindings.update({str(validation_path): sha(validation_path), str(model): sha(model)})
    def check_inputs():
        for path, digest in bindings.items():
            if sha(path) != digest:
                raise ValueError('Immutable transfer input changed: ' + path)
    check_inputs()
    canonical, target = Path(transfer['canonical']), Path(transfer['target'])
    changed = {row['object']: row for row in transfer['changed']}
    if len(changed) != len(transfer['changed']) or not changed:
        raise ValueError('Invalid changed-object inventory')

    def provenance(experiment):
        path = experiment / 'bake-v1/validation.json'
        report = json.loads(path.read_text())
        entries = [e for layer in report['layers'] for e in layer['objects']]
        if not all(e.get('texel_provenance', {}).get('packed_image_sha256') for e in entries):
            path = experiment / 'provenance-replay-v2/report.json'
            replay = json.loads(path.read_text())
            if any(replay[key] != report[key] for key in ('generated_sha256', 'input_sha256')):
                raise ValueError('Replay inputs differ from original bake')
            report = replay
        if bindings.get(str(path)) != sha(path):
            raise ValueError('Provenance report was not bound by the completed transfer: ' + str(path))
        result = {}
        for layer_index, layer in enumerate(report['layers']):
            for entry in layer['objects']:
                name, proof = entry['object'], entry['texel_provenance']
                if name in result:
                    raise ValueError('Ambiguous duplicate provenance receiver: ' + name)
                path = Path(proof['path'])
                if sha(path) != proof['sha256'] or bindings.get(str(path)) != proof['sha256']:
                    raise ValueError('Original mask is not bound by transfer: ' + name)
                with np.load(path, allow_pickle=False) as data:
                    mask = data['ownership'].copy()
                if mask.ndim != 2 or not np.isin(mask, [0, 1, 2, 3]).all():
                    raise ValueError('Invalid original ownership classes: ' + name)
                result[name] = (proof, mask, layer_index)
        return report, result
    donor_report, donors = provenance(canonical)
    target_report, targets = provenance(target)
    if not changed.keys() <= donors.keys() or not changed.keys() <= targets.keys():
        raise ValueError('Changed receiver lacks donor or target provenance')

    def read(model_path, names, proofs=None, pixel_names=()):
        bpy.ops.wm.open_mainfile(filepath=str(model_path))
        result = {}
        for name in names:
            obj = bpy.data.objects.get(name)
            if obj is None or obj.type != 'MESH':
                raise ValueError('Missing atlas receiver: ' + name)
            slots = {p.material_index for p in obj.data.polygons}
            if len(slots) != 1:
                raise ValueError('Ambiguous atlas material: ' + name)
            material = obj.data.materials[next(iter(slots))]
            if material is None or not material.use_nodes:
                raise ValueError('Missing atlas material: ' + name)
            images = [n.image for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
            uvs = [n.uv_map for n in material.node_tree.nodes if n.type == 'UVMAP']
            if len(images) != 1 or len(uvs) != 1 or not images[0].packed_file:
                raise ValueError('Ambiguous packed atlas or UV node: ' + name)
            image = images[0]
            uv = [list(e.uv) for e in obj.data.uv_layers[uvs[0]].data]
            row = dict(packed_image_sha256=hashlib.sha256(image.packed_file.data).hexdigest(),
                       uv_sha256=hashlib.sha256(json.dumps(uv).encode()).hexdigest(),
                       shape=(image.size[1], image.size[0]))
            if proofs is not None:
                proof, mask, _ = proofs[name]
                if row['shape'] != mask.shape or any(row[k] != proof[k] for k in ('packed_image_sha256', 'uv_sha256')):
                    raise ValueError('Saved original atlas differs from replay proof: ' + name)
            if name in pixel_names:
                row['rgba'] = np.asarray(image.pixels[:], dtype=np.float32).reshape(*row['shape'], 4)
            result[name] = row
        return result

    donor_pixels = read(canonical/'bake-v1/worker.blend', changed, donors, changed)
    prior = read(target/'bake-v1/worker.blend', targets, targets, changed)
    final = read(model, targets, pixel_names=changed)
    masks, records, verified = {}, [], []
    for name, (proof, mask, layer_index) in targets.items():
        saved = final[name]
        if saved['uv_sha256'] != proof['uv_sha256'] or saved['shape'] != mask.shape:
            raise ValueError('Final UV layout or atlas dimensions changed: ' + name)
        if name in changed:
            if donor_pixels[name]['uv_sha256'] != saved['uv_sha256']:
                raise ValueError('Donor UV layout differs: ' + name)
            mask, count = updated_ownership(donor_pixels[name]['rgba'], prior[name]['rgba'],
                                            saved['rgba'], donors[name][1], mask)
            before_hash = hashlib.sha256(prior[name]['rgba'].tobytes()).hexdigest()
            after_hash = hashlib.sha256(saved['rgba'].tobytes()).hexdigest()
            row = changed[name]
            if count != row['inferred_texels'] or before_hash != row['before_rgba_sha256'] or after_hash != row['after_rgba_sha256']:
                raise ValueError('Transfer pixel/count receipt differs: ' + name)
            verified.append(dict(object=name, selected_texels=count, exact_final_rgba=True,
                                 source_and_unselected_rgba_preserved=True, all_alpha_preserved=True))
        elif saved['packed_image_sha256'] != proof['packed_image_sha256']:
            raise ValueError('Unchanged receiver atlas differs: ' + name)
        masks[name] = mask
        new_proof = dict(proof)
        # rgba8 from the original atlas no longer describes changed output.
        new_proof.pop('rgba8_sha256', None)
        new_proof.update(packed_image_sha256=saved['packed_image_sha256'], uv_sha256=saved['uv_sha256'])
        if name in changed:
            new_proof['rgba_float32_sha256'] = hashlib.sha256(saved['rgba'].tobytes()).hexdigest()
        records.append(dict(object=name, layer_index=layer_index, texel_provenance=new_proof,
                            class_counts={str(i): int((mask == i).sum()) for i in range(4)}))
    check_inputs()
    output.mkdir(parents=True)
    for entry in records:
        path = output / (hashlib.sha256(entry['object'].encode()).hexdigest()[:20] + '.npz')
        np.savez_compressed(path, ownership=masks[entry['object']])
        entry['texel_provenance'].update(path=str(path), sha256=sha(path))
    layers = [dict(objects=[e for e in records if e['layer_index'] == i]) for i in range(len(target_report['layers']))]
    report = dict(version=1, status='PASS', asset_id=validation['asset_id'], model_sha256=sha(model), transfer_validation_sha256=sha(validation_path),
                  transfer_bake=str(bake), inputs_sha256=bindings, objects=records, layers=layers,
                  verified_transfers=verified, original_evidence_unchanged=True,
                  selection_rule='donor ownership == 2 AND target ownership != 1; only selected provenance becomes 2')
    check_inputs()
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    report = run(*sys.argv[sys.argv.index('--')+1:])
    print(json.dumps(dict(status=report['status'], model_sha256=report['model_sha256'],
                         objects=len(report['objects']), transfers=len(report['verified_transfers']))))
