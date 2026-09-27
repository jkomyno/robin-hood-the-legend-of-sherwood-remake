"""Verify and install independent completed Sherwood textures with rollback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

EDITOR=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(EDITOR/'refinement'),str(EDITOR/'refinement/blender')]
from asset_index import write_asset_index,generate_asset_index
from scene_manifest import scene_metadata
from promote_staged_publication import library_lock
from lossy_assets import read_glb


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def verify(stage):
    stage=Path(stage).resolve();live=EDITOR/'library'
    receipt=json.loads((stage/'texture-handoff.json').read_text())
    assert receipt['status']=='PASS' and receipt['publication_authorization']=='Install completed textures in the level editor'
    for path,digest in receipt['before'].items():assert sha(live/path)==digest,('Live input changed',path)
    for path,digest in receipt['protected_files'].items():assert sha(path)==digest,('Candidate changed',path)
    old=json.loads((live/'scenes/sherwood.rhlos-map.json').read_text())
    new=json.loads((stage/'sherwood.rhlos-map.json').read_text())
    changed={r['asset'] for r in receipt['assets']}
    assert changed
    assert {k:v for k,v in old.items() if k not in ('assetSources','sceneAssets')}=={k:v for k,v in new.items() if k not in ('assetSources','sceneAssets')}
    old_refs={r['id']:r for r in old['assetSources']+old['sceneAssets']}
    refs={r['id']:r for r in new['assetSources']+new['sceneAssets']}
    assert old_refs.keys()==refs.keys() and changed <= refs.keys()
    artifacts={}
    for identity,ref in refs.items():
        prior=old_refs[identity]
        for key in ('model','descriptor'):
            path=stage/'map-assets'/ref[key]
            assert ref[key]==prior[key] and sha(path)==ref[key+'_sha256']
            if identity not in changed:assert sha(path)==sha(live/prior[key])
        if identity not in changed:continue
        previous=json.loads((live/prior['descriptor']).read_text())
        current=json.loads((stage/'map-assets'/ref['descriptor']).read_text())
        for key in ('id','name','parts','source_origin_scene'):assert current.get(key)==previous.get(key),(identity,key)
        gltf,_,_=read_glb(stage/'map-assets'/ref['model'])
        assert {p['node'] for p in current['parts']} <= {n.get('name') for n in gltf['nodes']},identity
        assert all('baseColorTexture' in m.get('pbrMetallicRoughness',{}) for m in gltf['materials']),identity
        assert not any('uri' in x for x in gltf.get('buffers',[])+gltf.get('images',[])),identity
        for path in (stage/'map-assets'/ref['descriptor']).parent.rglob('*'):
            if path.is_file():artifacts[str(path.relative_to(stage))]=sha(path)
    scene_metadata(stage/'map-assets',new)
    assert len(generate_asset_index(stage/'map-assets/3d-assets')['assets'])==len(refs)
    artifacts['sherwood.rhlos-map.json']=sha(stage/'sherwood.rhlos-map.json')
    result={'status':'PASS','updated_assets':sorted(changed),'unchanged_assets':len(refs)-len(changed),'artifacts':artifacts,
        'checks':['saved candidate source preservation','exported geometry handoff','unchanged placements and gameplay','unchanged other model bytes','embedded textured materials','runtime scene metadata']}
    write(stage/'partial-verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='artifacts'}),flush=True)
    return result


def install(stage):
    stage=Path(stage).resolve();live=EDITOR/'library'
    browser=json.loads((stage/'browser/result.json').read_text())
    assert browser['status']=='PASS','Browser audit has not passed'
    with library_lock(live):
        checked=verify(stage)
        handoff=json.loads((stage/'texture-handoff.json').read_text())
        workers=[Path(p) for p in handoff['protected_files'] if Path(p).name=='candidate.blend']
        assert len(workers)==1
        candidate=workers[0].parent
        inspected=json.loads((candidate/'actual-inspections.json').read_text())['items']
        for identity in checked['updated_assets']:
            targets=([f'sherwood-terrain-{x}-{y}' for x in (1,2) for y in (1,2,3)]
                     if identity=='sherwood-terrain' else [identity])
            for target in targets:
                evidence=inspected[target]
                actual=json.loads((candidate/'renders'/target/'review.json').read_text())
                assert evidence['all_eight_actual_views_inspected'] is True
                assert evidence['actual_sheet_sha256']==actual['actual_sheet_sha256']==sha(candidate/'renders'/target/'textured.png')
                assert actual['worker_sha256']==handoff['candidate_worker_sha256']
                assert actual['residual_unknown_pixels']==0,target
        for path,digest in checked['artifacts'].items():assert sha(stage/path)==digest
        # Browser inputs must be the exact staged bytes verified for installation.
        config=json.loads((stage/'browser/config.json').read_text())
        pinned={item['path']:item['sha256'] for item in config['files']}
        staged_document=json.loads((stage/'sherwood.rhlos-map.json').read_text())
        for ref in staged_document['assetSources']+staged_document['sceneAssets']:
            assert pinned[ref['model']]==ref['model_sha256'],ref['id']
        for item in config['files']:
            path=Path(item['url'].removeprefix('/@fs/'))
            assert sha(path)==item['sha256'],str(path)
        backup=stage/'installation-backup';backup.mkdir(exist_ok=False)
        document=live/'scenes/sherwood.rhlos-map.json';index=live/'3d-assets/index.json'
        shutil.copy2(document,backup/'sherwood.rhlos-map.json');shutil.copy2(index,backup/'index.json')
        installed=[]
        try:
            for identity in checked['updated_assets']:
                for other in (live/'scenes').glob('*.rhlos-map.json'):
                    if other==document:continue
                    assert not any(r['id']==identity for r in json.loads(other.read_text()).get('assetSources',[])),('Asset used by another scene',identity)
                target=live/'3d-assets/sherwood'/identity
                shutil.copytree(target,backup/identity)
                installed.append(identity)
                shutil.rmtree(target)
                shutil.copytree(stage/'map-assets/3d-assets/sherwood'/identity,target)
            temporary=document.with_suffix('.partial-textures.tmp')
            shutil.copy2(stage/'sherwood.rhlos-map.json',temporary);os.replace(temporary,document)
            write_asset_index(live/'3d-assets')
        except BaseException:
            for identity in installed:
                target=live/'3d-assets/sherwood'/identity
                if target.exists():shutil.rmtree(target)
                shutil.copytree(backup/identity,target)
            shutil.copy2(backup/'sherwood.rhlos-map.json',document);shutil.copy2(backup/'index.json',index)
            raise
        result={'status':'APPLIED','installed_assets':installed,'map_sha256':sha(document),'backup':str(backup),
            'texture_review':'pending','authorization':'Install completed textures in the level editor','browser_check':'PASS'}
        write(stage/'installation.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage');parser.add_argument('--install',action='store_true')
    args=parser.parse_args();(install if args.install else verify)(args.stage)
