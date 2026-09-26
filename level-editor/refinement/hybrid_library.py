"""Pack asset-local GLBs, retaining only payloads with worthwhile cross-asset sharing."""
import argparse
import copy
import json
from pathlib import Path
import struct
from collections import defaultdict
from canonical_assets import digest, encoded, read_model
from scene_manifest import _splitter

DEFAULT_MIN_SAVINGS = 256 * 1024


def pack(model, binary, external, shared, blob_prefix='../blobs/'):
    """Repack bytes without changing any accessor, texture encoding, or scene."""
    result = copy.deepcopy(model)
    data = bytearray()
    embedded = {}
    buffers = [{'byteLength': 0}]
    pins = {}
    def embed(raw):
        key = digest(raw)
        if key not in embedded:
            data.extend(b'\0' * (-len(data) % 4))
            embedded[key] = len(data); data.extend(raw)
        return embedded[key]
    def resource(raw, suffix):
        key = digest(raw)
        if key not in shared: return None
        relative = '3d-assets/blobs/'+key+suffix
        pins[relative] = key
        return blob_prefix+key+suffix
    mapping = {}
    for i, buffer in enumerate(model.get('buffers', [])):
        raw = external(buffer['uri']) if 'uri' in buffer else binary[:buffer['byteLength']]
        uri = resource(raw, '.bin')
        if uri:
            mapping[i] = (len(buffers), 0)
            buffers.append({**buffer, 'uri':uri})
        else: mapping[i] = (0, embed(raw))
    for view in result.get('bufferViews', []):
        index, offset = mapping[view.get('buffer', 0)]
        view['buffer'] = index; view['byteOffset'] = view.get('byteOffset', 0)+offset
    for image in result.get('images', []):
        if 'uri' not in image: continue
        raw = external(image.pop('uri'))
        suffix = {'image/png':'.png', 'image/jpeg':'.jpg'}[image['mimeType']]
        uri = resource(raw, suffix)
        if uri: image['uri'] = uri
        else:
            image['bufferView'] = len(result.setdefault('bufferViews', []))
            result['bufferViews'].append({'buffer':0, 'byteOffset':embed(raw), 'byteLength':len(raw)})
    buffers[0]['byteLength'] = len(data)
    result['buffers'] = buffers
    if not data:
        result['buffers'] = buffers[1:]
        for view in result.get('bufferViews', []): view['buffer'] -= 1
    data.extend(b'\0' * (-len(data) % 4))
    chunk = encoded(result); chunk += b' ' * (-len(chunk) % 4)
    output = struct.pack('<III', 0x46546c67, 2, 20+len(chunk)+(8+len(data) if data else 0))
    output += struct.pack('<II', len(chunk), 0x4e4f534a)+chunk
    if data: output += struct.pack('<II', len(data), 0x004e4942)+data
    return output, result, bytes(data), [{'path':p, 'sha256':h} for p,h in sorted(pins.items())]


def stage_hybrid(library, output, min_savings=DEFAULT_MIN_SAVINGS):
    if min_savings < 1: raise ValueError('Minimum sharing savings must be positive')
    library, output = Path(library).resolve(), Path(output).resolve()
    if output.exists(): raise FileExistsError('Use a fresh hybrid staging directory: '+str(output))
    sources = {}
    def read(relative):
        raw = (library/relative).read_bytes(); sources[relative] = digest(raw); return raw
    index = json.loads(read('3d-assets/index.json'))
    records, owners, payloads = [], defaultdict(set), {}
    for entry in index['assets']:
        relative = '3d-assets/'+entry['descriptor']; descriptor = json.loads(read(relative))
        model_path = '3d-assets/'+entry['model']; read(model_path)
        model, binary, external = read_model(library/model_path, library)
        # Expand embedded models through the same canonical byte extractor first.
        # This also discovers sharing between previously self-contained assets.
        from canonical_assets import AssetBundle
        bundle = AssetBundle(output)
        for scene in model['scenes']:
            bundle.add(scene['name'], model, binary, external, scene['name'])
        ref = bundle.write(entry['id'])
        for resource in descriptor.get('resources', []):
            if digest(read(resource['path'])) != resource['sha256']: raise ValueError('Resource changed: '+resource['path'])
        for resource in ref['resources']:
            key = resource['sha256']; owners[key].add(entry['id']); payloads[key] = output/resource['path']
        records.append((entry, relative, descriptor, ref))
    shared = {key for key, ids in owners.items() if len(ids)>1 and payloads[key].stat().st_size*(len(ids)-1)>=min_savings}
    references, proofs, external_paths = {}, {}, set()
    for entry, relative, descriptor, temporary in records:
        model, binary, external = read_model(output/temporary['model'], output)
        source_map = entry.get('source_map', descriptor.get('source_map'))
        if not isinstance(source_map, str) or not source_map or any(c in source_map for c in '/\\.'):
            raise ValueError('Asset requires a source map: '+entry['id'])
        target = Path('3d-assets')/source_map.lower()/entry['id']
        model_path = str(target/'model.glb')
        (output/target).mkdir(parents=True, exist_ok=True)
        raw, packed, packed_binary, resources = pack(model, binary, external, shared, '../../blobs/')
        packed_external = lambda uri: (output/target/uri).read_bytes()
        for scene in model['scenes']:
            before = _splitter.canonical(model, binary, scene['nodes'], external)
            after = _splitter.canonical(packed, packed_binary, scene['nodes'], packed_external)
            if before != after: raise ValueError('Hybrid packing changed scene: '+entry['id']+'/'+scene['name'])
        (output/model_path).write_bytes(raw)
        (output/temporary['model']).unlink()
        descriptor.update(model='model.glb', resources=resources)
        for field in ('state_variants', 'standalone_variants'):
            for variant in descriptor.get(field, {}).values(): variant['model'] = 'model.glb'
        if descriptor.get('preview_model'):
            preview = descriptor['preview_model']
            (output/target/preview).write_bytes(read(str(Path(relative).parent/preview)))
        if entry.get('preview_model'):
            preview = Path(entry['preview_model'])
            destination_preview = target/preview.name
            (output/destination_preview).write_bytes(read(str(Path('3d-assets')/preview)))
            receipt = Path('3d-assets')/Path(str(preview)+'.receipt.json')
            if (library/receipt).is_file():
                (output/Path(str(destination_preview)+'.receipt.json')).write_bytes(read(str(receipt)))
            entry['preview_model'] = str(destination_preview.relative_to('3d-assets'))
        destination = str(target/'asset.json')
        (output/destination).write_bytes(encoded(descriptor))
        entry['descriptor'] = str((target/'asset.json').relative_to('3d-assets'))
        entry['model'] = str((target/'model.glb').relative_to('3d-assets'))
        references[relative] = {'descriptor':destination, 'model':model_path, 'model_sha256':digest(raw),
            'descriptor_sha256':digest(encoded(descriptor)), 'resources':resources}
        external_paths.update(resource['path'] for resource in resources)
        proofs[entry['id']] = {'scenes':len(model['scenes']), 'model_sha256':digest(raw)}
    (output/'3d-assets/index.json').write_bytes(encoded(index))
    (output/'scenes').mkdir()
    for path in sorted((library/'scenes').glob('*.rhlos-map.json')):
        relative = str(path.relative_to(library)); document = json.loads(read(relative))
        for ref in document['sceneAssets']+document.get('assetSources', []):
            if ref.get('descriptor') not in references: raise ValueError('Map reference is not in catalog')
            ref.update(references[ref['descriptor']])
        (output/relative).write_bytes(encoded(document))
    for path in (output/'3d-assets/blobs').iterdir():
        if str(path.relative_to(output)) not in external_paths: path.unlink()
    report = {'assets':len(records), 'self_contained':sum(not ref['resources'] for ref in references.values()),
        'shared_payloads':len(external_paths), 'min_savings_bytes':min_savings,
        'sharing_saves_bytes':sum(payloads[key].stat().st_size*(len(owners[key])-1) for key in shared),
        'verified_scenes':sum(proof['scenes'] for proof in proofs.values())}
    plan = {'library':str(library), 'output':str(output), 'sources':sources, 'proofs':proofs, 'hybrid':report}
    (output.parent/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('library', type=Path); parser.add_argument('output', type=Path)
    parser.add_argument('--min-savings', type=int, default=DEFAULT_MIN_SAVINGS)
    args = parser.parse_args(); print(json.dumps(stage_hybrid(args.library, args.output, args.min_savings), indent=2))
