"""Bind an explicit paired geometry decision to validated source-material clones.

The specification lists initial/applied state model, source_model, packet, and
source_material_validation paths. Clones must prove unchanged geometry; this
does not turn a pending gallery entry into approval or approve generated textures.
"""
import argparse
import hashlib
import json
from pathlib import Path
from prepare_texture_packet import prepare
from review_evidence import sha

def build(gallery, asset_id, specification, output):
    gallery=Path(gallery).resolve();specification=Path(specification).resolve();output=Path(output).resolve()
    item=next(i for i in json.loads(gallery.read_text())['items'] if i['id']==asset_id)
    approval=item.get('user_approval','')
    if item.get('status')!='approved' or not approval.startswith('Approved: '):
        raise ValueError('An explicit recorded gallery geometry approval is required')
    states=json.loads(specification.read_text())['states']
    if {s['id'] for s in states}!={'initial','applied'} or len(states)!=2:
        raise ValueError('Exactly initial and applied states required')
    if output.exists():raise FileExistsError(output)
    evidence={}; endpoints=[]
    def bind(key,path):
        path=Path(path).resolve(strict=True)
        evidence[key]={'path':str(path),'sha256':sha(path)}
    bind('gallery_approval',gallery)
    for state in states:
        validation=json.loads(Path(state['source_material_validation']).read_text())
        if (validation.get('geometry_unchanged') is not True or validation.get('stored_material_validation')!='PASS'
            or validation['source_model_sha256']!=sha(Path(state['source_model']))
            or validation['derived_model_sha256']!=sha(Path(state['model']))):
            raise ValueError('Source-material clone lacks exact geometry-preserving validation')
        packet=Path(state['packet']).resolve(strict=True)
        endpoint={'id':state['id'],'status':'ready-for-user','model':str(Path(state['model']).resolve()),
            'model_sha256':sha(Path(state['model'])),'solid':str(packet/'solid.png'),
            'textured':str(packet/'textured.png'),'frames':str(packet/'views.json')}
        for field in ('model','solid','textured','frames'):bind('endpoint_'+state['id']+'_'+field,endpoint[field])
        bind('endpoint_'+state['id']+'_approved_original_model',state['source_model'])
        bind('endpoint_'+state['id']+'_source_material_validation',state['source_material_validation'])
        endpoints.append(endpoint)
    initial=next(s for s in states if s['id']=='initial')
    if sha(Path(initial['source_model']))!=item['approved_sha256']['model']:
        raise ValueError('Initial model differs from recorded gallery approval')
    first=next(e for e in endpoints if e['id']=='initial')
    paired={'id':asset_id,'name':item['name'],'status':'ready-for-user',
        'workspace':str(Path(first['model']).parent),'solid':first['solid'],'textured':first['textured'],
        'stored_material_validation':'PASS','endpoint_reviews':endpoints}
    identity={'asset_id':asset_id,'model_sha256':first['model_sha256'],
        'evidence':{k:v['sha256'] for k,v in evidence.items()}}
    revision=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    paired['revision']={'sha256':revision,'model_sha256':first['model_sha256'],'evidence':evidence}
    decision={'asset_id':asset_id,'scope':'geometry','decision':'approved',
        'revision_sha256':revision,'exact_user_text':approval.removeprefix('Approved: '),
        'approved_original_model_sha256':{s['id']:sha(Path(s['source_model'])) for s in states},
        'derivation':'Source material preparation only; exact original endpoint geometry unchanged.',
        'source_gallery':str(gallery),'source_gallery_sha256':sha(gallery)}
    output.mkdir(parents=True)
    manifest=output/'paired-review.json';manifest.write_text(json.dumps({'version':1,'items':[paired]},indent=2)+'\n')
    (output/'decisions.json').write_text(json.dumps({'version':1,'decisions':[decision]},indent=2)+'\n')
    return [prepare(manifest,asset_id,output/state,endpoint=state) for state in ('initial','applied')]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gallery');parser.add_argument('asset_id');parser.add_argument('specification');parser.add_argument('output')
    args=parser.parse_args();print(json.dumps(build(args.gallery,args.asset_id,args.specification,args.output),indent=2))
