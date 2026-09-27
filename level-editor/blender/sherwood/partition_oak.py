"""Give the legacy merged oak's upper collision part its own existing triangles."""
import copy
import json
from pathlib import Path
import struct
import sys
import numpy as np

EDITOR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EDITOR/'refinement/blender'))
from lossy_assets import read_glb, accessor_array, mesh_instances


def partition(path, descriptor):
    if not any(p['node']=='building-048' for p in descriptor['parts']):
        return
    doc, buffers, _ = read_glb(path)
    upper = next(n for n in doc['nodes'] if n.get('name')=='building-048')
    if upper.get('children'):
        return
    lower = next(n for n in doc['nodes'] if n.get('name')=='building-032')
    node = next(doc['nodes'][i] for i in lower['children'] if doc['nodes'][i]['name'].startswith('Tree 032 - tapered trunk'))
    mesh = doc['meshes'][node['mesh']]
    matrix = mesh_instances(doc)[node['mesh']]
    blob = bytearray(buffers[0][:doc['buffers'][0]['byteLength']])
    low, high = [], []
    def indices(values):
        values = np.asarray(values, dtype='<u4').ravel()
        blob.extend(b'\0'*(-len(blob)%4))
        view = len(doc['bufferViews'])
        doc['bufferViews'].append({'buffer':0,'byteOffset':len(blob),'byteLength':values.nbytes,'target':34963})
        blob.extend(values.tobytes())
        accessor = len(doc['accessors'])
        doc['accessors'].append({'bufferView':view,'componentType':5125,'count':len(values),'type':'SCALAR',
                                 'min':[int(values.min())],'max':[int(values.max())]})
        return accessor
    for primitive in mesh['primitives']:
        points = accessor_array(doc,buffers,primitive['attributes']['POSITION'],True)
        points = points@matrix[:3,:3].T+matrix[:3,3]+descriptor.get('source_origin_scene',[0,0,0])
        triangles = accessor_array(doc,buffers,primitive['indices']).reshape(-1,3)
        # Native lower-trunk obstacle ends at z=221.001. Assign whole existing
        # triangles by centroid: no cuts, added faces, changed vertices or UVs.
        mask = points[triangles,2].mean(1)>221.001
        for target, selected in ((low,~mask),(high,mask)):
            if selected.any():
                target.append({**primitive,'indices':indices(triangles[selected])})
    if not low or not high:
        raise ValueError('Upper/lower trunk partition is empty')
    mesh['primitives']=low
    clone=copy.deepcopy(node)
    clone['name']='Central oak upper trunk surface'
    clone['mesh']=len(doc['meshes'])
    clone['extras'].update(source_node='building-048',editor_part_node='building-048')
    doc['meshes'].append({'name':'Central oak upper trunk','primitives':high})
    upper['children']=[len(doc['nodes'])]
    doc['nodes'].append(clone)
    upper['extras']['partition']='Existing trunk triangles with centroid above native lower obstacle z=221.001'
    doc['buffers'][0]['byteLength']=len(blob)
    encoded=json.dumps(doc,separators=(',',':')).encode()
    encoded+=b' '*(-len(encoded)%4)
    blob.extend(b'\0'*(-len(blob)%4))
    Path(path).write_bytes(struct.pack('<4sII',b'glTF',2,28+len(encoded)+len(blob))+
                          struct.pack('<II',len(encoded),0x4E4F534A)+encoded+
                          struct.pack('<II',len(blob),0x004E4942)+blob)
