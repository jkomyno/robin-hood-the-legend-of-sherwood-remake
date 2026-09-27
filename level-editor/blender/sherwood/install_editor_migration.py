"""Install a verified legacy migration under the shared library lock, with rollback.

Only the local editor library is changed. No web deployment is performed.
"""
import hashlib,json,os,shutil,sys
from pathlib import Path
EDITOR=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(EDITOR/'refinement'),str(Path(__file__).parent)]
from asset_index import write_asset_index
from promote_staged_publication import library_lock
from verify_editor_migration import verify


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def install(stage):
    stage=Path(stage).resolve();library=EDITOR/'library'
    for filename in ('asset-verification.json','handoff-verification.json','browser-result.json'):
        if json.loads((stage/filename).read_text()).get('status')!='PASS':raise ValueError('Missing passing '+filename)
    with library_lock(library):
        verify(stage)
        migration=json.loads((stage/'migration.json').read_text())
        document=json.loads((stage/'sherwood.rhlos-map.json').read_text())
        backup=stage/'installation-backup';backup.mkdir(exist_ok=False)
        prior_map=library/'scenes/sherwood.rhlos-map.json';prior_index=library/'3d-assets/index.json'
        shutil.copy2(prior_map,backup/'sherwood.rhlos-map.json');shutil.copy2(prior_index,backup/'index.json')
        retired=[];installed=[]
        try:
            # Generic map entries are replaced, not retained as compatibility aliases.
            for old,new in migration['renames'].items():
                directory=library/'3d-assets/sherwood'/old
                shutil.move(str(directory),str(backup/old));retired.append(old)
            for source in sorted((stage/'map-assets/3d-assets/sherwood').iterdir()):
                target=library/'3d-assets/sherwood'/source.name
                if target.exists():
                    for map_path in (library/'scenes').glob('*.rhlos-map.json'):
                        if map_path==prior_map:continue
                        refs=json.loads(map_path.read_text()).get('assetSources',[])
                        if any(r['id']==source.name for r in refs):
                            raise ValueError('Semantic ID is used by another map: '+source.name)
                    shutil.move(str(target),str(backup/source.name));retired.append(source.name)
                shutil.copytree(source,target);installed.append(source.name)
            tmp=prior_map.with_suffix('.migration.tmp');shutil.copy2(stage/'sherwood.rhlos-map.json',tmp);os.replace(tmp,prior_map)
            write_asset_index(library/'3d-assets')
        except BaseException:
            for identity in installed:shutil.rmtree(library/'3d-assets/sherwood'/identity)
            for identity in retired:shutil.move(str(backup/identity),str(library/'3d-assets/sherwood'/identity))
            shutil.copy2(backup/'sherwood.rhlos-map.json',prior_map);shutil.copy2(backup/'index.json',prior_index)
            raise
        receipt={'status':'APPLIED','map_sha256':sha(prior_map),'retired_asset_ids':retired,
                 'installed_asset_ids':installed,'backup':str(backup),'browser_check':'PASS'}
        (stage/'installation.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt))

if __name__=='__main__':install(sys.argv[1])
