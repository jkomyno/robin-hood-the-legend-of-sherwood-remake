"""Losslessly extract scene nodes into content-addressed library assets.

This is an import/publication boundary, not an editor fallback. Binary payloads
are copied without decoding, quantization, or texture recompression.
"""
import argparse
import copy
import hashlib
import json
import struct
from pathlib import Path
from urllib.parse import unquote


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_glb(path, *, allow_external=False):
    raw = Path(path).read_bytes()
    magic, version, length = struct.unpack_from('<III', raw)
    if magic != 0x46546c67 or version != 2 or length != len(raw):
        raise ValueError('Invalid GLB header')
    size, kind = struct.unpack_from('<II', raw, 12)
    if kind != 0x4e4f534a:
        raise ValueError('Missing GLB JSON')
    model = json.loads(raw[20:20+size])
    pos = 20 + size
    binary = b''
    if pos < len(raw):
        size, kind = struct.unpack_from('<II', raw, pos)
        if kind != 0x004e4942:
            raise ValueError('Unexpected GLB chunk')
        binary = raw[pos+8:pos+8+size]
    if model.get('animations') or model.get('skins') or model.get('cameras'):
        raise ValueError('Animated, skinned, or camera-bearing imports require explicit support')
    if set(model.get('extensionsUsed', [])) - {'KHR_materials_unlit'}:
        raise ValueError('Unsupported GLB extension; refusing a lossy conversion')
    if not allow_external and any('uri' in buffer for buffer in model.get('buffers', [])):
        raise ValueError('Expected embedded GLB buffers')
    return model, binary, digest(raw)


class Extractor:
    def __init__(self, model, binary, output, external=None):
        self.model, self.binary, self.output = model, binary, Path(output)
        self.files = {}
        self.external = external

    def blob(self, data, suffix):
        name = f'3d-assets/blobs/{digest(data)}{suffix}'
        self.write(name, data)
        return name

    def write(self, name, data):
        path = self.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError('Content-addressed asset differs: ' + name)
        else:
            path.write_bytes(data)
        self.files[name] = digest(data)

    def view_bytes(self, index):
        view = self.model['bufferViews'][index]
        if view.get('buffer', 0) != 0 or view.get('extensions'):
            raise ValueError('Unsupported binary buffer layout')
        start = view.get('byteOffset', 0)
        data = self.binary[start:start+view['byteLength']]
        if len(data) != view['byteLength']:
            raise ValueError('Truncated buffer view')
        return data

    def extract(self, root_indices, label):
        result = {key: copy.deepcopy(value) for key, value in self.model.items()
                  if key not in {'nodes','meshes','accessors','materials','textures','images','samplers','bufferViews','buffers','scenes','scene'}}
        tables, mappings, resources = {}, {}, {}
        geometry = bytearray()

        def reference(table, index):
            mapping = mappings.setdefault(table, {})
            if index in mapping:
                return mapping[index]
            entries = tables.setdefault(table, [])
            new_index = len(entries)
            mapping[index] = new_index
            entries.append(None)
            value = copy.deepcopy(self.model[table][index])
            if table == 'nodes':
                if 'mesh' in value: value['mesh'] = reference('meshes', value['mesh'])
                if 'children' in value: value['children'] = [reference('nodes', child) for child in value['children']]
            elif table == 'meshes':
                for primitive in value['primitives']:
                    primitive['attributes'] = {key: reference('accessors', item) for key, item in primitive['attributes'].items()}
                    for key, target in [('indices','accessors'),('material','materials')]:
                        if key in primitive: primitive[key] = reference(target, primitive[key])
                    for target in primitive.get('targets', []):
                        for key in target: target[key] = reference('accessors', target[key])
            elif table == 'accessors':
                if 'bufferView' in value: value['bufferView'] = reference('bufferViews', value['bufferView'])
                for sparse in value.get('sparse', {}).values():
                    if isinstance(sparse, dict) and 'bufferView' in sparse:
                        sparse['bufferView'] = reference('bufferViews', sparse['bufferView'])
            elif table == 'bufferViews':
                data = self.view_bytes(index)
                while len(geometry) % 4: geometry.append(0)
                value['buffer'] = 0
                value['byteOffset'] = len(geometry)
                geometry.extend(data)
            elif table == 'materials':
                for parent in [value, value.get('pbrMetallicRoughness', {})]:
                    for key, texture in parent.items():
                        if key.endswith('Texture') and isinstance(texture, dict) and 'index' in texture:
                            texture['index'] = reference('textures', texture['index'])
            elif table == 'textures':
                for key, target in [('source','images'),('sampler','samplers')]:
                    if key in value: value[key] = reference(target, value[key])
            elif table == 'images':
                data = self.external(value.pop('uri')) if 'uri' in value else self.view_bytes(value.pop('bufferView'))
                suffix = {'image/png':'.png','image/jpeg':'.jpg'}.get(value.get('mimeType'))
                if not suffix: raise ValueError('Unsupported image MIME type')
                uri = self.blob(data, suffix)
                value['uri'] = uri
                resources[uri] = digest(data)
            entries[new_index] = value
            return new_index

        roots = [reference('nodes', index) for index in root_indices]
        result.update(tables)
        result['scene'] = 0
        result['scenes'] = [{'nodes': roots}]
        if geometry:
            uri = self.blob(bytes(geometry), '.bin')
            result['buffers'] = [{'byteLength': len(geometry), 'uri': uri}]
            resources[uri] = digest(geometry)
        raw = (json.dumps(result, separators=(',', ':'), ensure_ascii=False)+'\n').encode()
        model_path = f'3d-assets/models/{digest(raw)}.gltf'
        self.write(model_path, raw)
        return {'id': label, 'model': model_path, 'model_sha256': digest(raw),
                'resources': [{'path': name, 'sha256': value} for name, value in sorted(resources.items())]}, result, mappings


def canonical(model, binary, roots, external=None):
    """Resolve all table indices and payload locations before comparing subtrees."""
    def ref(table, index):
        value = copy.deepcopy(model[table][index])
        if table == 'nodes':
            if 'mesh' in value: value['mesh'] = ref('meshes', value['mesh'])
            if 'children' in value: value['children'] = [ref('nodes', i) for i in value['children']]
        elif table == 'meshes':
            for p in value['primitives']:
                p['attributes'] = {key:ref('accessors',i) for key,i in p['attributes'].items()}
                if 'indices' in p: p['indices'] = ref('accessors',p['indices'])
                if 'material' in p: p['material'] = ref('materials',p['material'])
                for target in p.get('targets',[]):
                    for key in target: target[key] = ref('accessors',target[key])
        elif table == 'accessors':
            if 'bufferView' in value: value['bufferView'] = ref('bufferViews',value['bufferView'])
            for sparse in value.get('sparse',{}).values():
                if isinstance(sparse,dict) and 'bufferView' in sparse: sparse['bufferView']=ref('bufferViews',sparse['bufferView'])
        elif table == 'bufferViews':
            buffer = model['buffers'][value.pop('buffer')]
            data = external(buffer['uri']) if 'uri' in buffer else binary
            start = value.pop('byteOffset',0)
            value['payload_sha256'] = digest(data[start:start+value['byteLength']])
        elif table == 'materials':
            for parent in [value,value.get('pbrMetallicRoughness',{})]:
                for key, texture in parent.items():
                    if key.endswith('Texture') and isinstance(texture,dict) and 'index' in texture: texture['index']=ref('textures',texture['index'])
        elif table == 'textures':
            if 'source' in value: value['source']=ref('images',value['source'])
            if 'sampler' in value: value['sampler']=ref('samplers',value['sampler'])
        elif table == 'images':
            if 'uri' in value:
                data=external(value.pop('uri'))
            else:
                view=model['bufferViews'][value.pop('bufferView')];start=view.get('byteOffset',0)
                data=binary[start:start+view['byteLength']]
            value['payload_sha256']=digest(data)
        return value
    return [ref('nodes',index) for index in roots]


def split_model(model, binary, output, source_hash, external=None):
    extractor=Extractor(model,binary,output,external)
    scene=model['scenes'][model.get('scene',0)]
    roots=scene.get('nodes',[])
    map_roots=[i for i in roots if model['nodes'][i].get('name')=='map']
    if len(map_roots)!=1 or len(roots)!=1: raise ValueError('Expected one map wrapper')
    root=model['nodes'][map_roots[0]]
    if 'mesh' in root: raise ValueError('Map wrapper cannot carry geometry')
    references=[]
    count=0
    if root.get('extras'):
        local=copy.deepcopy(model)
        local['nodes'][map_roots[0]]['children']=[]
        extractor.model=local
        reference,asset,_=extractor.extract(map_roots,'map-metadata')
        if canonical(local,binary,map_roots,external) != canonical(asset,b'',asset['scenes'][0]['nodes'],lambda name:(Path(output)/name).read_bytes()):
            raise ValueError('Map metadata differs after extraction')
        reference['role']='metadata'
        references.append(reference)
        count+=1
    for group_index in root.get('children',[]):
        group=model['nodes'][group_index]
        # Preserve reviewed groups. Large ungrouped volume sets become individual assets.
        children=group.get('children',[])
        partitions=[children] if group.get('extras',{}).get('asset_group') or group.get('name')=='ground' or not children else [[i] for i in children]
        for part_indices in partitions:
            local=copy.deepcopy(model)
            if group.get('name')!='ground' and children: local['nodes'][group_index]['children']=part_indices
            extractor.model=local
            label=group.get('extras',{}).get('asset_group') or (model['nodes'][part_indices[0]].get('name') if len(part_indices)==1 else group.get('name')) or f'asset-{count}'
            reference,asset,_=extractor.extract([group_index],f'{count:04d}-{label}')
            before=canonical(local,binary,[group_index],external)
            after=canonical(asset,b'',asset['scenes'][0]['nodes'],lambda name:(Path(output)/name).read_bytes())
            if before != after: raise ValueError('Asset differs from its source subtree: '+label)
            reference['role']='ground' if group.get('name')=='ground' else 'objects'
            references.append(reference)
            count+=1
    return {'source_sha256':source_hash,'sceneAssets':references,'files':extractor.files,'verified_assets':count}


def split(source, output):
    model, binary, source_hash = read_glb(source)
    return split_model(model, binary, output, source_hash)


def split_gltf(source, output):
    source = Path(source)
    model = json.loads(source.read_text())
    root = source.parent.resolve()
    def external(uri):
        path = (root / unquote(uri)).resolve()
        if not path.is_relative_to(root):
            raise ValueError('External resource escapes export directory')
        return path.read_bytes()
    if len(model.get('buffers', [])) > 1 or set(model.get('extensionsUsed', [])) - {'KHR_materials_unlit'}:
        raise ValueError('Unsupported separate export layout')
    for image in model.get('images', []):
        if 'mimeType' not in image:
            image['mimeType'] = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}.get(Path(image['uri']).suffix.lower())
    binary = external(model['buffers'][0]['uri']) if model.get('buffers') else b''
    return split_model(model, binary, output, digest(source.read_bytes()), external)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();report=split(args.source,args.output)
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'verified_assets':report['verified_assets'],'files':len(report['files']),'source_sha256':report['source_sha256']}))
