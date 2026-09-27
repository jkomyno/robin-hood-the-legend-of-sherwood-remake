"""Bind submitted grouping decisions to exact sheets and semantic mesh ownership."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def group_signature(group,catalog,stage):
    parts=next(g['parts'] for g in catalog['groups'] if g['id']==group['id'])
    source=lambda p:p.get('node',f"building-{p.get('obstacle',0):03}")
    binding=dict(id=group['id'],name=group['name'],objects=sorted(group['objects']),parts=parts,
        canonical_owners={source(p):catalog['canonical_owners'][source(p)] for p in parts},
        geometry_uv_material_fingerprint=stage['geometry_uv_material_fingerprint'],
        source_worker_sha256=stage['source_worker_sha256'])
    return hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()


def record(gallery,root,feedback,decisions):
    gallery,root,feedback,decisions=map(Path,(gallery,root,feedback,decisions))
    catalog=json.loads((root/'catalog.json').read_text());stage=json.loads((root/'stage.json').read_text())
    assert sha(root/'catalog.json')==stage['catalog_sha256']
    plan={g['id']:g for g in json.loads((root/'plan.json').read_text())['groups']}
    current={i['id']:i for i in json.loads((gallery/'evidence.json').read_text())['items']}
    result=json.loads(decisions.read_text()) if decisions.exists() else dict(version=1,scope='grouping-only',decisions=[])
    known={(d['id'],d['review_revision'],d['decision'],d['note']) for d in result['decisions']}
    count=0
    for line in feedback.read_text().splitlines():
        match=re.fullmatch(r'(sherwood-[a-z0-9-]+): (approved|needs refinement)(?: — (.*?))? \[review ([a-f0-9]{16})\]',line.strip())
        if not match:
            if line.startswith('sherwood-'):raise ValueError('Unrecognized review line: '+line)
            continue
        identity,decision,note,prefix=match.groups();note=note or '';item=current[identity]
        if item['review_revision'][:16]!=prefix:raise ValueError('Stale review: '+identity)
        if decision=='approved' and (item['status']!='ready-for-user' or not item.get('technical_eligible',True)):
            raise ValueError('Review packet is not ready: '+identity)
        for kind in ('images','reports'):
            for entry in item[kind].values():
                if sha(gallery/entry['file'])!=entry['sha256']:raise ValueError('Changed review evidence: '+identity)
        packet=json.loads((gallery/item['reports']['ownership']['file']).read_text())
        assert packet['objects']==plan[identity]['objects'] and packet['worker_sha256']==stage['worker_sha256']
        key=(identity,item['review_revision'],decision,note)
        if key in known:continue
        result['decisions'].append(dict(id=identity,decision=decision,note=note,review_revision=item['review_revision'],
            exact_user_line=line,group_signature=group_signature(plan[identity],catalog,stage),
            binding={kind:{k:v['sha256'] for k,v in item[kind].items()} for kind in ('images','reports')}))
        known.add(key);count+=1
    if not count:raise ValueError('No new decisions found')
    decisions.write_text(json.dumps(result,indent=2)+'\n');print(f'Recorded {count} verified grouping decisions')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--gallery',required=True);p.add_argument('--root',required=True)
    p.add_argument('--feedback',required=True);p.add_argument('--decisions',required=True)
    a=p.parse_args();record(a.gallery,a.root,a.feedback,a.decisions)
