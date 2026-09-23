"""Prepare a hash-guarded promotion manifest; apply only with explicit --apply.

Preparing never edits the live library. Applying backs up every existing target
before writing and restores copied targets if any replacement raises an error.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def prepare(stage, library, main_blend, map_name):
    for name in ('asset-verification.json', 'handoff-verification.json', 'browser-result.json'):
        if json.loads((stage/name).read_text())['status'] != 'PASS':
            raise ValueError('Missing successful verification: ' + name)
    index_path=library/'3d-assets/index.json'
    current=json.loads(index_path.read_text())
    staged=json.loads((stage/'assets/index.json').read_text())
    selected={a['id'] for a in staged['assets']}
    current['assets']=[a for a in current['assets'] if a['id'] not in selected]+staged['assets']
    current['assets'].sort(key=lambda a:a['id'])
    merged=stage/'promotion-library-index.json'
    merged.write_text(json.dumps(current,indent=2)+'\n')
    pairs=[(stage/'worker.blend',main_blend),(stage/f'{map_name}.scene.glb',library/f'scenes/{map_name}-volumes.scene.glb'),
           (stage/f'{map_name}.level3d.json',library/f'scenes/{map_name}.level3d.json'),
           (merged,index_path)]
    for asset in staged['assets']:
        for key in ('descriptor','model'):
            relative=Path(asset[key])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe asset-relative path')
            pairs.append((stage/'assets'/relative,library/'3d-assets'/relative))
    records=[]
    for index,(source,target) in enumerate(pairs):
        source=source.resolve(strict=True);target=target.resolve()
        records.append({'source':str(source),'target':str(target),'source_sha256':sha(source),
                        'previous_sha256':sha(target),'backup':str(stage/'promotion-backup'/f'{index:03d}-{target.name}')})
    protected=[]
    for suffix in ('-volumes.scene.json',):
        path=library/f'scenes/{map_name}{suffix}'
        protected.append({'path':str(path),'sha256':sha(path)})
    manifest={'status':'PREPARED_NOT_APPLIED','stage':str(stage),'files':records,'protected_files':protected}
    path=stage/'promotion.json'
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(path)


def apply(path):
    manifest=json.loads(path.read_text())
    if manifest['status']!='PREPARED_NOT_APPLIED':
        raise ValueError('Promotion manifest already applied')
    for record in manifest['protected_files']:
        if sha(Path(record['path']))!=record['sha256']:
            raise ValueError('Protected editor document changed')
    for item in manifest['files']:
        if sha(Path(item['source']))!=item['source_sha256'] or sha(Path(item['target']))!=item['previous_sha256']:
            raise ValueError('Promotion input/target changed: '+item['target'])
        if Path(item['backup']).exists():
            raise FileExistsError(item['backup'])
    for item in manifest['files']:
        target,backup=Path(item['target']),Path(item['backup'])
        backup.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():shutil.copy2(target,backup)
    written=[]
    try:
        for item in manifest['files']:
            target=Path(item['target']);target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_name(target.name+'.publication-tmp')
            if temporary.exists():raise FileExistsError(temporary)
            shutil.copy2(item['source'],temporary)
            temporary.replace(target);written.append(item)
            if sha(target)!=item['source_sha256']:raise ValueError('Copied hash mismatch')
    except Exception:
        for item in reversed(written):
            if item['previous_sha256'] is None:Path(item['target']).unlink()
            else:shutil.copy2(item['backup'],item['target'])
        raise
    manifest['status']='APPLIED'
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    print('Applied '+str(len(written))+' files; backups retained')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',type=Path)
    parser.add_argument('--library',type=Path,default=Path('level-editor/library'))
    parser.add_argument('--main-blend',type=Path)
    parser.add_argument('--map',default='derby')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();stage=args.stage.resolve(strict=True)
    if args.apply:apply(stage/'promotion.json')
    else:
        if args.main_blend is None:parser.error('--main-blend is required to prepare')
        prepare(stage,args.library.resolve(strict=True),args.main_blend.resolve(strict=True),args.map)
