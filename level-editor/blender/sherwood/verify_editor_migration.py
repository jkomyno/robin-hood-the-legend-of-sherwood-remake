"""Check staged legacy geometry coverage and unchanged gameplay before installation."""
import hashlib,json,struct,sys
from pathlib import Path
EDITOR=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(EDITOR/'refinement'))
from scene_manifest import scene_metadata
from asset_index import generate_asset_index


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(stage):
    stage=Path(stage).resolve();migration=json.loads((stage/'migration.json').read_text())
    live=EDITOR/'library';assets=stage/'map-assets';document=json.loads((stage/'sherwood.rhlos-map.json').read_text())
    old=json.loads((live/'scenes/sherwood.rhlos-map.json').read_text())
    for path,digest in migration['before'].items():
        assert sha(live/path)==digest,('Live source changed',path)
    before={x['assets'][0]:x['transform'] for x in old['placements']}
    after={x['assets'][0]:x['transform'] for x in document['placements']}
    for identity,transform in before.items():assert after[migration['renames'][identity]]==transform,identity
    old_descriptors={r['id']:json.loads((live/r['descriptor']).read_text()) for r in old['assetSources']+old['sceneAssets']}
    new_descriptors={r['id']:json.loads((assets/r['descriptor']).read_text()) for r in document['assetSources']+document['sceneAssets']}
    for identity,previous in old_descriptors.items():
        current=new_descriptors[migration['renames'][identity]]
        def gameplay(d):return [{k:v for k,v in p.items() if k!='name'} for p in d['parts']]
        assert gameplay(previous)==gameplay(current),('Gameplay changed',identity)
        assert previous.get('source_origin_scene')==current.get('source_origin_scene'),identity
    expected={}
    for row in json.loads((stage/'ownership.json').read_text()):
        expected[row['asset_id']]=expected.get(row['asset_id'],0)+row['faces']
    reports=[]
    for reference in document['assetSources']+document['sceneAssets']:
        d=new_descriptors[reference['id']];path=assets/reference['model'];raw=path.read_bytes()
        assert sha(path)==reference['model_sha256']
        assert sha(assets/reference['descriptor'])==reference['descriptor_sha256']
        length=struct.unpack_from('<I',raw,12)[0];gltf=json.loads(raw[20:20+length])
        assert not any('uri' in x for x in gltf.get('buffers',[])+gltf.get('images',[])),reference['id']
        assert 'group-' not in d['id'] and not d['name'].startswith('group-'),d['id']
        assert {p['node'] for p in d['parts']}<={n.get('name') for n in gltf['nodes']},d['id']
        triangles=sum(gltf['accessors'][p['indices']]['count']//3 for m in gltf.get('meshes',[]) for p in m['primitives'])
        assert triangles>=expected[d['id']],(d['id'],triangles,expected[d['id']])
        untextured=[m.get('name') for m in gltf.get('materials',[]) if 'baseColorTexture' not in m.get('pbrMetallicRoughness',{})]
        assert not untextured,('Unexportable material',d['id'],untextured)
        reports.append({'id':d['id'],'triangles':triangles,'source_faces':expected[d['id']],'materials':len(gltf.get('materials',[]))})
    index=generate_asset_index(assets/'3d-assets')
    assert len(index['assets'])==len(new_descriptors)
    scene_metadata(assets,document)
    result={'status':'PASS','assets':reports,'checks':['all map model/descriptor hashes resolve',
        'all historical placements retain their transforms','all original collision payloads and pivots unchanged',
        'all visible native meshes accounted for','all exported materials have textures','no generic asset IDs or names',
        'every native selectable part retained, including the repartitioned upper trunk','runtime scene metadata loads']}
    (stage/'asset-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'PASS','assets':len(reports),'triangles':sum(x['triangles'] for x in reports)}))
    return result

if __name__=='__main__':verify(sys.argv[1])
