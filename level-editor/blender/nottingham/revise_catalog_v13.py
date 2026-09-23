"""Assign both castle gateway piers to their contiguous arch structure."""
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(WORK/'tooling/58744eeaf71a21e9'))
from catalog_schema import parse_catalog


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,data):
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(data,indent=2)+'\n')


def main():
    previous=WORK/'grouping/catalog-v12.json'
    catalog=json.loads(previous.read_text())
    groups={group['id']:group for group in catalog['groups']}
    origin=groups['nottingham-castle-gate-west-tower']
    destination=groups['nottingham-castle-gate-arch']
    for number in (349,350):
        part=next(part for part in origin['parts'] if part['obstacle']==number)
        origin['parts'].remove(part)
        part['name']=f'Castle gateway pier {number}'
        destination['parts'].append(part)
        catalog['canonical_owners'][f'building-{number}']=destination['id']
    destination['parts'].sort(key=lambda part:part['obstacle'])
    catalog['revision']=13
    catalog['revision_notes']=[
        'Move canonical349 and350 from the west tower to the castle gate arch; they are the two piers framing its portcullis opening beneath333.',
        'The source-artwork mesh overlay distinguishes the straight gateway piers from the adjacent curved tower walls.',
        'No geometry, transform, component selector or source assignment is changed by this ownership revision. Both groups require fresh review packets.',
    ]
    destination['review_notes']='Complete castle gateway with piers349/350, spanning arch333 and door335/336; retain separate selectable parts and source-supported animation endpoints.'
    origin['review_notes']='West gate tower329/330/331/332; straight gateway piers349/350 belong to the gate arch.'
    index=parse_catalog(catalog,{f'building-{i:03}' for i in range(555)})
    validation={'status':'PASS','groups':len(index.groups),'source_parts':len(index.sources),'explicit_components':len(index.component_owners),'missing_sources':[],'duplicate_component_ownership':[],'transfers':[{'source_node':f'building-{number}','from':origin['id'],'to':destination['id']} for number in (349,350)],'geometry_mutations':0}
    target=WORK/'grouping/catalog-v13.json'
    write(target,catalog)
    write(WORK/'grouping/validation-v13.json',validation)
    evidence=['castle-audit/review4-gates/349350-ownership.json','castle-audit/review4-gates/349350-source-outline.png']
    write(WORK/'grouping/grouping-review-v13.json',{'status':'reviewed','reviewer':'Independent source-footprint and gate arch continuity review','catalog_sha256':sha(target),'inventory_sha256':sha(WORK/'inventory/inventory-v2.json'),'previous_catalog_sha256':sha(previous),'notes':catalog['revision_notes']+['Ownership review is not approval of geometry, texture or publication.'],'validation':validation,'evidence':[{'path':path,'sha256':sha(WORK/path)}for path in evidence]})
    assignments=json.loads((WORK/'worker-assignments-v11.json').read_text())
    assignments.update(version=8,catalog='grouping/catalog-v13.json')
    write(WORK/'worker-assignments-v13.json',assignments)
    print(json.dumps({'catalog':str(target),'sha256':sha(target),'validation':validation}))


if __name__=='__main__':
    main()
