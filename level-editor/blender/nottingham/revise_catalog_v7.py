"""Freeze reviewed Nottingham ownership transfers and wall-group splits.

Run with --decisions <reviewed wall/display decisions JSON>. All evidence paths
are relative to the Nottingham refinement work root and must exist unchanged.
"""
import argparse,copy,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):
 if path.exists():raise FileExistsError(path)
 path.write_text(json.dumps(data,indent=2)+'\n')
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--decisions',type=Path,required=True);args=parser.parse_args();decisions=json.loads(args.decisions.read_text())
 if decisions.get('status')!='reviewed':raise ValueError('Wall decisions require explicit reviewed status')
 source=WORK/'grouping/catalog-v6.json';catalog=json.loads(source.read_text());old=copy.deepcopy(catalog);by_id={g['id']:g for g in catalog['groups']}
 transfers=[(129,'nottingham-church-west-house','nottingham-church-north-house','Southern roof chimney'),(379,'nottingham-castle-southwest-stair','nottingham-castle-west-courtyard-wall','Western curtain coping'),(167,'nottingham-upper-west-yard-prop','nottingham-upper-red-house','Side entrance stair')]
 for number,origin,destination,name in transfers:
  parts=by_id[origin]['parts'];matches=[p for p in parts if p['obstacle']==number]
  if len(matches)!=1:raise ValueError(('Transfer source mismatch',number))
  part=matches[0];parts.remove(part);part['name']=name;by_id[destination]['parts'].append(part);by_id[destination]['parts'].sort(key=lambda p:p['obstacle'])
 catalog['groups']=[g for g in catalog['groups']if g['parts']]
 for split in decisions['splits']:
  origin=by_id[split['from']];expected={p['obstacle']for p in origin['parts']};newparts=[p['obstacle']for g in split['groups']for p in g['parts']]
  if len(newparts)!=len(set(newparts))or set(newparts)!=expected:raise ValueError(('Wall split canonical coverage',split['from']))
  if len(split['groups'])!=({'nottingham-south-curtain-wall':4,'nottingham-southwest-curtain-wall':2}[split['from']]):raise ValueError('Wrong segment count')
  index=next(i for i,g in enumerate(catalog['groups'])if g['id']==split['from']);catalog['groups'][index:index+1]=copy.deepcopy(split['groups'])
 names={'nottingham-northwest-roof-return':'Castle east annex grass bank','nottingham-southeast-road-props':'Pillory'}
 if decisions.get('courtyard_haypile_confirmed'):names['nottingham-village-courtyard-well']='Village courtyard hay pile'
 for group in catalog['groups']:
  if group['id']in names:group['name']=names[group['id']]
  if group['id']=='nottingham-northwest-roof-return':group['parts'][0]['name']='Low grass bank adjoining castle east annex'
  if group['id']=='nottingham-southeast-road-props':
   for part in group['parts']:part['name']='Pillory approach stair'if part['obstacle']==57 else'Pillory platform and timber frame'
  if group['id']=='nottingham-castle-southwest-stair':group['name']='Castle courtyard southwestern stair'
 catalog['revision']=7;catalog['revision_notes']=['Transfer chimney129 to the northern church-side house, stair167 to the upper red house, and coping379 to the western courtyard wall after source/footprint review.','Remove the empty upper-west yard-prop group; authored spatial wall partitions are deferred to component-aware revision8.','Correct the low grass bank and pillory display classifications; keep existing stable IDs for renamed groups.','Existing workspaces, source baselines and explicit approvals remain immutable; changed membership requires separately reviewed new packets.']
 if decisions.get('courtyard_haypile_confirmed'):catalog['revision_notes'].append('Source artwork confirms the village courtyard object is a hay pile; retain its stable ID.')
 ids=[g['id']for g in catalog['groups']];labels=[g['name'].casefold()for g in catalog['groups']];nodes=[p['obstacle']for g in catalog['groups']for p in g['parts']]
 if len(ids)!=len(set(ids))or len(labels)!=len(set(labels))or len(nodes)!=555 or set(nodes)!=set(range(555)):raise ValueError('Catalog reconciliation failed')
 if any(not g['parts']for g in catalog['groups']):raise ValueError('Empty asset group')
 evidence_paths=['town-audit/building-129-grouping-diagnosis.json','town-audit/stair167-grouping.json','town-audit/building-168-bank-diagnosis.json',*decisions['evidence']]
 evidence=[{'path':p,'sha256':sha(WORK/p)}for p in evidence_paths];oldparts={g['id']:[p['obstacle']for p in g['parts']]for g in old['groups']};newparts={g['id']:[p['obstacle']for p in g['parts']]for g in catalog['groups']};changed=[{'asset_id':i,'before':oldparts.get(i,[]),'after':newparts.get(i,[])}for i in sorted(set(oldparts)|set(newparts))if oldparts.get(i)!=newparts.get(i)]
 validation={'status':'PASS','groups':len(ids),'source_parts':555,'missing_parts':[],'duplicate_parts':[],'empty_groups':[],'changed_groups':changed,'display_names':names,'geometry_or_transform_edits':False,'geometry_preservation_validation':'grouped/nottingham-grouped-v7.validation.json'}
 out=WORK/'grouping/catalog-v7.json';write(out,catalog);write(WORK/'grouping/validation-v7.json',validation);review={'status':'reviewed','reviewer':'Nottingham V7 source, footprint and explicit user grouping review','catalog_sha256':sha(out),'inventory_sha256':sha(WORK/'inventory/inventory-v2.json'),'previous_catalog_sha256':sha(source),'decisions_sha256':sha(args.decisions),'notes':catalog['revision_notes']+['Grouping review is not geometry, source-pixel, texture or publication approval.'],'validation':validation,'evidence':evidence};write(WORK/'grouping/grouping-review-v7.json',review)
 assignment_path=WORK/'worker-assignments.json';assignment=json.loads(assignment_path.read_text());archive=WORK/'worker-assignments-v6.json'
 if not archive.exists():shutil.copy2(assignment_path,archive)
 for values in assignment['assignments'].values():
  if 'nottingham-upper-west-yard-prop'in values:values.remove('nottingham-upper-west-yard-prop')
  for split in decisions['splits']:
   if split['from']in values:
    index=values.index(split['from']);values[index:index+1]=[g['id']for g in split['groups']]
 assigned=[i for values in assignment['assignments'].values()for i in values]
 if len(assigned)!=len(set(assigned))or set(assigned)!=set(ids):raise ValueError('Worker assignments differ from catalog')
 assignment['version']=3;assignment['catalog']='grouping/catalog-v7.json';assignment_path.write_text(json.dumps(assignment,indent=2)+'\n');write(WORK/'worker-assignments-v7.json',assignment);print(json.dumps({'catalog':str(out),'groups':len(ids),'source_parts':555,'catalog_sha256':sha(out)}))
if __name__=='__main__':main()
