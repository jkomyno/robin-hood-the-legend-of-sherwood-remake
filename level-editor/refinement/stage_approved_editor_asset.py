"""Export one current approved revision into a fresh private editor library.

Blender --background --python this_file -- MANIFEST ASSET_ID OUTPUT --map-name
MAP --level SOURCE_LEVEL [--decisions PATH] [--revision-sha256 HASH].
OUTPUT/3d-assets/index.json is a standalone palette root, never a live library.
No candidate blend, review evidence, decision or source artwork is rewritten.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent/'blender'))
from review_evidence import sha, load_decisions, bind_decision


def validate(manifest, asset_id, decisions=None, expected_revision=None):
    manifest = Path(manifest).resolve(strict=True)
    data = json.loads(manifest.read_text())
    matches = [item for item in data['items'] if item['id']==asset_id]
    if len(matches)!=1:
        raise ValueError('Expected exactly one stable asset ID')
    item = matches[0]
    records = load_decisions(Path(decisions) if decisions else manifest.parent/'decisions.json',
                             {entry['id'] for entry in data['items']})
    bind_decision(item, records)
    if item['decision_state']!='current' or item['user_approval']!='approved':
        raise ValueError('Private staging requires current explicit geometry approval')
    revision=item['revision']
    if expected_revision and expected_revision!=revision['sha256']:
        raise ValueError('Requested revision differs from reviewed revision')
    identity={'asset_id':asset_id,'model_sha256':revision['model_sha256'],
              'evidence':{key:value['sha256'] for key,value in revision['evidence'].items()}}
    if hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=revision['sha256']:
        raise ValueError('Revision identity does not match evidence')
    workspace=Path(item['workspace'])
    if not workspace.is_absolute():workspace=manifest.parent/workspace
    model=workspace/'model.blend'
    protected={model:revision['model_sha256']}
    for entry in revision['evidence'].values():
        path=Path(entry['path'])
        if not path.is_absolute():path=manifest.parent/path
        protected[path]=entry['sha256']
    for path,digest in protected.items():
        if sha(path)!=digest:raise ValueError('Approved evidence changed: '+str(path))
    return item,workspace,protected


def stage(manifest, asset_id, output, *, map_name, level, decisions=None, expected_revision=None):
    import bpy
    from export_editor import export_asset_library
    item,workspace,protected=validate(manifest,asset_id,decisions,expected_revision)
    output=Path(output).resolve()
    if output.exists():raise FileExistsError('Private stage must be fresh: '+str(output))
    config=json.loads((workspace/'workspace.json').read_text())
    source=Path(config['source_path'])
    level=Path(level).resolve(strict=True)
    source_hash=sha(source)
    if source_hash != config['reference_files']['source.png']:
        raise ValueError('Source artwork differs from frozen worker input')
    protected[source]=source_hash;protected[level]=sha(level)
    bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'))
    if config['collection_name']!=map_name+' Working':raise ValueError('Map/working collection mismatch')
    objects=[o for o in bpy.data.collections[config['collection_name']].objects
             if o.type=='MESH' and not o.hide_render and o.get('asset_group')==asset_id]
    if not objects:raise ValueError('Approved asset has no visible meshes')
    if any(o.get('source_node') not in config['part_ids'] for o in objects):
        raise ValueError('Export receiver outside approved ownership')
    points=[o.matrix_world @ v.co for o in objects for v in o.data.vertices]
    low=[min(p[i] for p in points) for i in range(3)]
    high=[max(p[i] for p in points) for i in range(3)]
    pivot=[(low[0]+high[0])/2,(low[1]+high[1])/2,low[2]]
    output.mkdir(parents=True)
    result=export_asset_library(map_name,output/'3d-assets',level,
                               asset_ids=[asset_id],standalone_pivots={asset_id:pivot})
    index=json.loads((output/'3d-assets/index.json').read_text())
    if [entry['id'] for entry in index['assets']]!=[asset_id]:
        raise ValueError('Private library included unapproved asset')
    descriptor=json.loads((output/'3d-assets'/asset_id/'asset.json').read_text())
    if sorted(part['node'] for part in descriptor['parts'])!=sorted(config['part_ids']):
        raise ValueError('Export omitted approved canonical part')
    for path,digest in protected.items():
        if sha(path)!=digest:raise RuntimeError('Protected candidate or source changed: '+str(path))
    report={'status':'PASS','scope':'private editor staging only','asset_id':asset_id,
        'revision_sha256':item['revision']['sha256'],'model_sha256':item['revision']['model_sha256'],
        'source_level_sha256':protected[level],'source_artwork_sha256':protected[source],
        'source_origin_scene':pivot,'default_state':'visible approved component set',
        'assets':result['assets'],'protected_files':{str(p):h for p,h in protected.items()},
        'artifacts':{str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file()},
        'limitations':['Geometry and existing approved source atlases only; no texture generation.',
                        'Collision descriptors retain source obstacle volumes; refined visual mesh does not invent collision.']}
    (output/'stage-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest');parser.add_argument('asset_id');parser.add_argument('output')
    parser.add_argument('--map-name',required=True);parser.add_argument('--level',required=True)
    parser.add_argument('--decisions');parser.add_argument('--revision-sha256')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    report=stage(args.manifest,args.asset_id,args.output,map_name=args.map_name,level=args.level,
                 decisions=args.decisions,expected_revision=args.revision_sha256)
    print(json.dumps({key:report[key] for key in ('status','asset_id','revision_sha256')}))
