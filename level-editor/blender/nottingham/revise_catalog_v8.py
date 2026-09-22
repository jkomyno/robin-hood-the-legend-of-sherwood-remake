"""Freeze component-aware curtain-wall ownership without losing canonical provenance."""
import copy,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
from catalog_schema import parse_catalog

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):
 if path.exists():raise FileExistsError(path)
 path.write_text(json.dumps(data,indent=2)+'\n')
def main():
 previous=WORK/'grouping/catalog-v7.json';catalog=json.loads(previous.read_text());delta_path=WORK/'wall-partitions-v8/catalog-delta-proposal.json';delta=json.loads(delta_path.read_text());owners={f"building-{p['obstacle']:03}":g['id']for g in catalog['groups']for p in g['parts']};owners.update(delta['canonical_owners']);oldids={g['id']for g in catalog['groups']}
 catalog['groups']=[g for g in catalog['groups']if g['id']not in {'nottingham-south-curtain-wall','nottingham-southwest-curtain-wall'}];catalog['groups'].extend(copy.deepcopy(delta['new_groups']));byid={g['id']:g for g in catalog['groups']}
 for identifier,edits in delta['update_existing_groups'].items():
  group=byid[identifier]
  if 'replace201part'in edits:
   part=next(p for p in group['parts']if p['obstacle']==201);part.clear();part.update(copy.deepcopy(edits['replace201part']))
  if 'add_part'in edits:group['parts'].append(copy.deepcopy(edits['add_part']));group['parts'].sort(key=lambda p:p['obstacle'])
 for group in delta['new_groups']:
  target=byid[group['id']]
  for part in target['parts']:
   if part['obstacle']in (200,219):part['name']='Curtain parapet section'
   elif part['obstacle']in (202,220):part['name']='Curtain wall walk section'
   elif part['obstacle']==201:part['name']='Eastern gate platform and box'
 catalog.update(version=2,revision=8,canonical_owners=owners,revision_notes=['Four southern wall sections follow the explicit user revision: split where the curve ends, retain the next straight run, and merge the earlier far-east sections.','Two southwestern wall sections preserve parapet and walk together at the measured elbow.','Canonical201 western platform stays with the east gate tower; its eastern box component belongs to southern section2.','Transfer canonical205 rear parapet crown to the south gate arch.','Canonical source ownership remains unique; explicit component selectors distribute clipped surfaces. Hidden originals retain provenance and must not render.','Existing frozen packets and approvals remain immutable; new component-aware workspaces require review.'])
 index=parse_catalog(catalog,{f'building-{i:03}'for i in range(555)});newids=set(index.groups);evidence_names=['south-wall-partition-proposal.json','southwest-wall-partition-proposal.json','wall-partitions-v8/catalog-delta-proposal.json','wall-partitions-v8/baseline-partition-proof.json','wall-partitions-v8/partition-proof.json','wall-partitions-v8/baseline-components.blend','wall-partitions-v8/components.blend'];evidence=[{'path':p,'sha256':sha(WORK/p)}for p in evidence_names]
 validation={'status':'PASS','groups':len(index.groups),'source_parts':len(index.sources),'explicit_components':len(index.component_owners),'split_sources':sorted(index.split_sources),'missing_sources':[],'duplicate_component_ownership':[],'removed_groups':sorted(oldids-newids),'new_groups':sorted(newids-oldids),'part_references':sum(len(g['parts'])for g in catalog['groups']),'source_205_owner':owners['building-205'],'partition_geometry_validation':'wall-partitions-v8/baseline-partition-proof.json','refined_partition_validation':'wall-partitions-v8/partition-proof.json'}
 path=WORK/'grouping/catalog-v8.json';write(path,catalog);write(WORK/'grouping/validation-v8.json',validation);write(WORK/'grouping/grouping-review-v8.json',{'status':'reviewed','reviewer':'Nottingham explicit wall segmentation, source geometry and partition provenance review','catalog_sha256':sha(path),'inventory_sha256':sha(WORK/'inventory/inventory-v2.json'),'previous_catalog_sha256':sha(previous),'notes':catalog['revision_notes']+['This ownership review does not approve geometry, texture, source masks or publication.'],'validation':validation,'evidence':evidence})
 assignments=json.loads((WORK/'worker-assignments-v7.json').read_text());assigned=assignments['assignments']['fortifications_geometry'];result=[]
 for identifier in assigned:
  if identifier=='nottingham-south-curtain-wall':result.extend(g['id']for g in delta['new_groups']if g['id'].startswith('nottingham-south-curtain-wall-'))
  elif identifier=='nottingham-southwest-curtain-wall':result.extend(g['id']for g in delta['new_groups']if g['id'].startswith('nottingham-southwest-curtain-wall-'))
  else:result.append(identifier)
 assignments['assignments']['fortifications_geometry']=result;assignments['version']=4;assignments['catalog']='grouping/catalog-v8.json';flat=[v for values in assignments['assignments'].values()for v in values]
 if len(flat)!=len(set(flat))or set(flat)!=newids:raise ValueError('V8 worker assignments do not reconcile')
 write(WORK/'worker-assignments-v8.json',assignments);(WORK/'worker-assignments.json').write_text(json.dumps(assignments,indent=2)+'\n');print(json.dumps(validation))
if __name__=='__main__':main()
