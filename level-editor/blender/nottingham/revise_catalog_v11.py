"""Assign the western gate arch pier to its contiguous arch structure."""
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
    previous=WORK/'grouping/catalog-v10.json'
    catalog=json.loads(previous.read_text())
    groups={group['id']:group for group in catalog['groups']}
    origin=groups['nottingham-south-gate-east-tower']
    destination=groups['nottingham-south-gate-arch']
    part=next(part for part in origin['parts'] if part['obstacle']==212)
    origin['parts'].remove(part)
    part['name']='Western gate arch pier'
    destination['parts'].append(part)
    destination['parts'].sort(key=lambda part:part['obstacle'])
    catalog['canonical_owners']['building-212']=destination['id']
    catalog['revision']=11
    catalog['revision_notes']=['Move canonical212 from the east gate tower to the contiguous south gate arch. Its footprint abuts213 and lies beneath214, separated from turret206.','No geometry, transform, component selector or source assignment is changed by this ownership revision.','Both changed groups require fresh review packets. Existing approved and frozen revisions remain immutable.']
    destination['review_notes']='Complete gate arch with western pier212, front structure213, upper walk214 and rear parapet205; retain corrected numbered battlements during fresh workspace preparation.'
    origin['review_notes']='Eastern gate tower and adjoining retained western platform201 component; arch pier212 belongs to the gate arch and the eastern box201 belongs to south curtain section2.'
    index=parse_catalog(catalog,{f'building-{i:03}' for i in range(555)})
    validation={'status':'PASS','groups':len(index.groups),'source_parts':len(index.sources),'explicit_components':len(index.component_owners),'missing_sources':[],'duplicate_component_ownership':[],'transfers':[{'source_node':'building-212','from':origin['id'],'to':destination['id']}],'geometry_mutations':0}
    target=WORK/'grouping/catalog-v11.json'
    write(target,catalog)
    write(WORK/'grouping/validation-v11.json',validation)
    evidence=['round-13/assets/nottingham-south-gate-east-tower/inspection/source212-ownership.json','round-13/assets/nottingham-south-gate-east-tower/inspection/source212-arch-pier-ownership.png']
    write(WORK/'grouping/grouping-review-v11.json',{'status':'reviewed','reviewer':'Independent source-footprint and gate arch continuity review','catalog_sha256':sha(target),'inventory_sha256':sha(WORK/'inventory/inventory-v2.json'),'previous_catalog_sha256':sha(previous),'notes':catalog['revision_notes']+['Ownership review is not approval of geometry, texture or publication.'],'validation':validation,'evidence':[{'path':path,'sha256':sha(WORK/path)}for path in evidence]})
    assignments=json.loads((WORK/'worker-assignments-v10.json').read_text())
    assignments.update(version=7,catalog='grouping/catalog-v11.json')
    write(WORK/'worker-assignments-v11.json',assignments)
    print(json.dumps({'catalog':str(target),'sha256':sha(target),'validation':validation}))


if __name__=='__main__':
    main()
