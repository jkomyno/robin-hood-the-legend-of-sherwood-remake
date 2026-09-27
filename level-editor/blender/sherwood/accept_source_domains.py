"""Freeze explicitly inspected authored-domain evidence into the source recipe."""
import argparse
import json
import shutil
from pathlib import Path
from author_source_domains import ROOT, SPEC
from build_mask_review import digest, INVENTORY, SOURCE, EDITOR, RECIPE

def main(ids):
    manifest=json.loads((ROOT/'manifest.json').read_text())
    if manifest['spec_sha256']!=digest(SPEC) or manifest['source_sha256']!=digest(SOURCE) or manifest['inventory_sha256']!=digest(INVENTORY):
        raise ValueError('Authored-domain inputs changed')
    domains={r['id']:r for r in manifest['domains']}
    if set(ids)-domains.keys():raise ValueError('Unknown authored domains')
    native={r['index']:r for r in json.loads(INVENTORY.read_text())['masks']}
    recipe=json.loads(RECIPE.read_text())
    for id in ids:
        domain=domains[id]
        for key in ('mask','card'):
            if digest(Path(domain[key]))!=domain[key+'_sha256']:raise ValueError('Domain evidence changed')
        frozen=ROOT.parent/'history'/('authored-'+domain['card_sha256'][:16]);frozen.mkdir(exist_ok=True)
        for key in ('mask','card'):
            target=frozen/Path(domain[key]).name;shutil.copy2(domain[key],target);domain[key]=str(target.resolve())
        for node in domain['source_nodes']:
            components=domain.get('projection_components',[None])
            for component in components:
                target=recipe.setdefault('component_assignments',[]) if component else recipe['assignments']
                rule=next((r for r in target if r['source_node']==node and r.get('projection_component')==component),None)
                if rule is None:
                    rule=dict(source_node=node,mask_indices=domain['native_masks']);target.append(rule)
                    if component:rule['projection_component']=component
                rule.update(reviewed=True,authored_mask=dict(path=domain['mask'],sha256=domain['mask_sha256'],card=domain['card'],card_sha256=domain['card_sha256'],visually_inspected=True,
                    reason=('Hand-traced original-art silhouette beyond native mask coverage.' if domain.get('clip_native') is False else 'Hand-traced painted domain within native silhouettes.')+' Ambiguous boundary pixels remain unknown.'))
                rule['inspection']=dict(card=str(Path(domain['card']).relative_to(EDITOR)),card_sha256=domain['card_sha256'],source_sha256=digest(SOURCE),inventory_sha256=digest(INVENTORY),
                    mask_sha256={str(i):digest(INVENTORY.parent/native[i]['png']) for i in rule['mask_indices']+rule.get('exclude_mask_indices',[])},
                    result='Original art and authored cutout visually inspected; neighbouring painted surfaces excluded.')
                if not component:recipe['unresolved'].pop(node,None)
    recipe['inspection_summary']['accepted_source_nodes']=sum(r.get('reviewed') is True and r['source_node'] not in recipe['unresolved'] for r in recipe['assignments'])
    RECIPE.write_text(json.dumps(recipe,indent=2)+'\n');print('Accepted total:',recipe['inspection_summary']['accepted_source_nodes'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('ids',nargs='+');main(p.parse_args().ids)
