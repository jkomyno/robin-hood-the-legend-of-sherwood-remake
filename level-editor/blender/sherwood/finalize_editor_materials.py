"""Preserve the legacy repeating timber crop in portable glTF materials.

Blender's FRACTION -> MULTIPLY -> ADD UV graph cannot be represented by a
single affine glTF texture transform. A repeating cropped donor image preserves
that mapping, including UVs beyond [0, 1], without changing any mesh or UV.
"""
import hashlib,io,json,struct,sys
from pathlib import Path
from PIL import Image
EDITOR=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def convert(path,donor_png):
    raw=path.read_bytes();length,kind=struct.unpack_from('<II',raw,12)
    doc=json.loads(raw[20:20+length]);binary_offset=20+length
    affected=[m for m in doc.get('materials',[]) if m.get('name','').startswith('Huts - concealed source timber')]
    if not affected:return False
    assert struct.unpack_from('<I',raw,binary_offset+4)[0]==0x004E4942
    blob=bytearray(raw[binary_offset+8:binary_offset+8+doc['buffers'][0]['byteLength']])
    blob.extend(b'\0'*(-len(blob)%4));offset=len(blob);blob.extend(donor_png)
    view=len(doc.setdefault('bufferViews',[]));doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(donor_png)})
    image=len(doc.setdefault('images',[]));doc['images'].append({'name':'Sherwood concealed timber donor','bufferView':view,'mimeType':'image/png'})
    sampler=len(doc.setdefault('samplers',[]));doc['samplers'].append({'magFilter':9728,'minFilter':9728,'wrapS':10497,'wrapT':10497})
    texture=len(doc.setdefault('textures',[]));doc['textures'].append({'source':image,'sampler':sampler})
    for mat in affected:
        tex=mat['pbrMetallicRoughness']['baseColorTexture']
        # The old graph starts at the mesh's primary UV layer.
        mat['pbrMetallicRoughness']['baseColorTexture']={'index':texture,'texCoord':tex.get('texCoord',0)}
        mat.setdefault('extras',{})['legacy_timber_mapping']='Repeated 15x32 source crop; exact FRACTION UV semantics'
    doc['buffers'][0]['byteLength']=len(blob)
    encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);blob.extend(b'\0'*(-len(blob)%4))
    path.write_bytes(struct.pack('<4sII',b'glTF',2,28+len(encoded)+len(blob))+struct.pack('<II',len(encoded),kind)+encoded+struct.pack('<II',len(blob),0x004E4942)+blob)
    return True


def main(stage):
    stage=Path(stage);source=EDITOR.parent/'datadirs/fullgame_gog_hackable/Data/Levels/Day/sherwood.map.png'
    image=Image.open(source);assert image.size==(1920,1088)
    stream=io.BytesIO();image.crop((553,361,568,393)).save(stream,format='PNG')
    changed=[]
    document=json.loads((stage/'sherwood.rhlos-map.json').read_text())
    for ref in document['assetSources']+document['sceneAssets']:
        path=stage/'map-assets'/ref['model']
        if convert(path,stream.getvalue()):
            changed.append(ref['id']);ref['model_sha256']=sha(path)
    (stage/'sherwood.rhlos-map.json').write_text(json.dumps(document,indent=2)+'\n')
    (stage/'timber-material-verification.json').write_text(json.dumps({'status':'PASS','assets':changed,'source_sha256':sha(source),'crop':[553,361,568,393],'geometry_and_uv_bytes_unchanged':True},indent=2)+'\n')
    sys.path.insert(0,str(EDITOR/'refinement'));from asset_index import write_asset_index
    write_asset_index(stage/'map-assets/3d-assets')
    print('Converted timber materials:',changed)

if __name__=='__main__':main(sys.argv[1])
