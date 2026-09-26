"""One lossless model per catalog asset, shared by map and palette scenes."""
import copy
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote
from scene_manifest import _splitter


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'))+'\n').encode()


def read_model(path, library):
    path = Path(path)
    if path.suffix == '.glb':
        model, binary, _ = _splitter.read_glb(path, allow_external=True)
    else:
        model, binary = json.loads(path.read_text()), b''
    if model.get('skins') or model.get('animations') or set(model.get('extensionsUsed', [])) - {'KHR_materials_unlit'}:
        raise ValueError('Unsupported model features: '+str(path))
    def external(uri):
        root = Path(library).resolve()
        target = ((root if uri.startswith('3d-assets/') else path.parent) / unquote(uri)).resolve()
        if not target.is_relative_to(root):
            raise ValueError('Resource escapes library: '+uri)
        return target.read_bytes()
    return model, binary, external


class AssetBundle:
    def __init__(self, output):
        self.output = Path(output)
        self.model = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': []}
        self.seen = {}
        self.resources = {}
        self.proofs = []

    def payload(self, data, suffix):
        name = '3d-assets/blobs/'+digest(data)+suffix
        path = self.output / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        elif digest(path.read_bytes()) != digest(data):
            raise ValueError('Immutable resource changed: '+name)
        self.resources[name] = digest(data)
        return name

    def add(self, name, model, binary, external, selected=None):
        if any(scene.get('name') == name for scene in self.model['scenes']):
            raise ValueError('Duplicate canonical scene: '+name)
        candidates = [s for s in model['scenes'] if s.get('name') == selected] if selected is not None else [model['scenes'][model.get('scene', 0)]]
        if len(candidates) != 1:
            raise ValueError('Missing or ambiguous source scene: '+str(selected))
        scene = candidates[0]
        mappings = {}
        def view_bytes(index):
            view = model['bufferViews'][index]
            buffer = model['buffers'][view.get('buffer', 0)]
            source = external(buffer['uri']) if 'uri' in buffer else binary
            start = view.get('byteOffset', 0)
            data = source[start:start+view['byteLength']]
            if len(data) != view['byteLength'] or view.get('extensions'):
                raise ValueError('Unsupported buffer view')
            return data
        def intern(table, value):
            key = json.dumps(value, sort_keys=True, separators=(',', ':'))
            cache = self.seen.setdefault(table, {})
            if key not in cache:
                cache[key] = len(self.model.setdefault(table, []))
                self.model[table].append(value)
            return cache[key]
        def ref(table, index):
            cache = mappings.setdefault(table, {})
            if index in cache:
                return cache[index]
            value = copy.deepcopy(model[table][index])
            if table == 'nodes':
                if 'mesh' in value: value['mesh'] = ref('meshes', value['mesh'])
                if 'children' in value: value['children'] = [ref('nodes', child) for child in value['children']]
            elif table == 'meshes':
                for primitive in value['primitives']:
                    primitive['attributes'] = {k: ref('accessors', v) for k,v in primitive['attributes'].items()}
                    if 'indices' in primitive: primitive['indices'] = ref('accessors', primitive['indices'])
                    if 'material' in primitive: primitive['material'] = ref('materials', primitive['material'])
                    for target in primitive.get('targets', []):
                        for key in target: target[key] = ref('accessors', target[key])
            elif table == 'accessors':
                if 'bufferView' in value: value['bufferView'] = ref('bufferViews', value['bufferView'])
                for sparse in value.get('sparse', {}).values():
                    if isinstance(sparse,dict) and 'bufferView' in sparse: sparse['bufferView'] = ref('bufferViews', sparse['bufferView'])
            elif table == 'bufferViews':
                data = view_bytes(index)
                uri = self.payload(data, '.bin')
                value['buffer'] = intern('buffers', {'byteLength':len(data), 'uri':uri})
                value.pop('byteOffset', None)
            elif table == 'materials':
                for parent in [value, value.get('pbrMetallicRoughness', {})]:
                    for key, texture in parent.items():
                        if key.endswith('Texture') and isinstance(texture,dict) and 'index' in texture: texture['index'] = ref('textures',texture['index'])
            elif table == 'textures':
                if 'source' in value: value['source'] = ref('images',value['source'])
                if 'sampler' in value: value['sampler'] = ref('samplers',value['sampler'])
            elif table == 'images':
                data = external(value.pop('uri')) if 'uri' in value else view_bytes(value.pop('bufferView'))
                suffix = {'image/png':'.png','image/jpeg':'.jpg'}.get(value.get('mimeType'))
                if not suffix: raise ValueError('Unsupported image encoding')
                value['uri'] = self.payload(data,suffix)
            if table == 'nodes':
                result = len(self.model.setdefault(table, [])); self.model[table].append(value)
            else:
                result = intern(table,value)
            cache[index] = result
            return result
        roots = [ref('nodes',i) for i in scene.get('nodes',[])]
        self.model['scenes'].append({**copy.deepcopy(scene), 'name':name, 'nodes':roots})
        for key in ['extensionsUsed','extensionsRequired']:
            if model.get(key): self.model[key] = sorted(set(self.model.get(key,[])) | set(model[key]))
        before = _splitter.canonical(model,binary,scene.get('nodes',[]),external)
        after = _splitter.canonical(self.model,b'',roots,lambda uri:(self.output/uri).read_bytes())
        if before != after: raise ValueError('Canonical asset differs from source scene: '+name)
        self.proofs.append({'scene':name,'sha256':digest(encoded(before))})

    def write(self, asset_id):
        relative = '3d-assets/'+asset_id+'/model.gltf'
        path = self.output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        published = copy.deepcopy(self.model)
        for table in ('buffers', 'images'):
            for value in published.get(table, []):
                if 'uri' in value:
                    value['uri'] = '../blobs/' + Path(value['uri']).name
        raw = encoded(published); path.write_bytes(raw)
        return {'model':relative,'model_sha256':digest(raw),
                'resources':[{'path':p,'sha256':h}for p,h in sorted(self.resources.items())]}


def localize_positions(model, binary, external, origin):
    """Translate baked float32 positions into the asset-local frame."""
    import struct
    model = copy.deepcopy(model)
    payloads, translated = {}, set()
    for mesh in model.get('meshes', []):
        for primitive in mesh['primitives']:
            index = primitive['attributes']['POSITION']
            if index in translated:
                continue
            accessor = model['accessors'][index]
            if accessor['componentType'] != 5126 or accessor['type'] != 'VEC3' or 'sparse' in accessor:
                raise ValueError('Expected float32 baked positions')
            view = model['bufferViews'][accessor['bufferView']]
            buffer = model['buffers'][view.get('buffer', 0)]
            raw = external(buffer['uri']) if 'uri' in buffer else binary
            start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
            original = [struct.unpack_from('<3f', raw, start+j*view.get('byteStride', 12)) for j in range(accessor['count'])]
            values = [tuple(p[k]-origin[k] for k in range(3)) for p in original]
            high_raw = b''.join(struct.pack('<3f', *p) for p in values)
            high = list(struct.iter_unpack('<3f', high_raw))
            def new_view(data, label):
                uri = 'localized-'+str(index)+'-'+label+'.bin'; payloads[uri] = data
                result = len(model['bufferViews'])
                model['bufferViews'].append({'buffer':len(model['buffers']), 'byteLength':len(data)})
                model['buffers'].append({'uri':uri,'byteLength':len(data)})
                return result
            accessor.update(bufferView=new_view(high_raw, 'high'), byteOffset=0,
                            min=[min(p[k] for p in high) for k in range(3)], max=[max(p[k] for p in high) for k in range(3)])
            translated.add(index)
    return model, lambda uri: payloads[uri] if uri in payloads else external(uri)
