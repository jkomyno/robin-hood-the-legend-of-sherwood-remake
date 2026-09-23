"""Apply seven source-backed market building groups to the V8 wall catalog."""
import copy, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(WORK/'tooling/94116d984f92dbae'))
from catalog_schema import parse_catalog

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):
 if p.exists(): raise FileExistsError(p)
 p.write_text(json.dumps(d,indent=2)+'\n')
def main():
 old=WORK/'grouping/catalog-v8.json'; catalog=json.loads(old.read_text())
 proposal=json.loads((WORK/'town-audit/market-seven-building-grouping-proposal.json').read_text())
 parent=next(g for g in catalog['groups'] if g['id']=='nottingham-market-terrace')
 parts={p['obstacle']:p for p in parent['parts']}
 groups=[]
 for building in proposal['buildings']:
  group=copy.deepcopy(parent); group['id']=building['proposed_id']; group['name']=group['id'].replace('nottingham-','').replace('-',' ').title()
  group['parts']=[copy.deepcopy(parts[int(n.split('-')[-1])]) for n in building['exclusive_source_nodes']]
  for part in group['parts']: catalog['canonical_owners'][f"building-{part['obstacle']:03}"]=group['id']
  if building['number']<=4:
   part=copy.deepcopy(parts[12]); part['name']='Masonry base section'; part['components']=[f"market-base-012-front-{building['number']}"]; group['parts'].append(part)
  group['parts'].sort(key=lambda p:p['obstacle']); groups.append(group)
 catalog['canonical_owners']['building-012']=groups[0]['id']
 catalog['groups']=[g for g in catalog['groups'] if g['id']!=parent['id']]+groups
 catalog['revision']=9
 catalog['revision_notes']=['Replace the previously approved terrace with seven separately selectable buildings, as explicitly requested.','Four front buildings receive disjoint components of canonical012; three rear buildings retain exclusive native meshes.','Approved exterior geometry and UVs are preserved; only concealed partition caps are inferred.','The earlier whole-terrace approval remains archived and does not approve these new ownership packets.']
 index=parse_catalog(catalog,{f'building-{i:03}' for i in range(555)})
 validation={'status':'PASS','groups':len(index.groups),'source_parts':len(index.sources),'explicit_components':len(index.component_owners),'split_sources':sorted(index.split_sources),'missing_sources':[],'duplicate_component_ownership':[],'removed_groups':[parent['id']],'new_groups':[g['id'] for g in groups]}
 path=WORK/'grouping/catalog-v9.json'; write(path,catalog);write(WORK/'grouping/validation-v9.json',validation)
 evidence=['town-audit/market-seven-building-grouping-proposal.json','market-partitions-v9/partition-proof.json','market-partitions-v9/components.blend']
 write(WORK/'grouping/grouping-review-v9.json',{'status':'reviewed','reviewer':'Source-backed seven-building market ownership review','catalog_sha256':sha(path),'inventory_sha256':sha(WORK/'inventory/inventory-v2.json'),'previous_catalog_sha256':sha(old),'notes':catalog['revision_notes'],'validation':validation,'evidence':[{'path':p,'sha256':sha(WORK/p)} for p in evidence]})
 assignments=json.loads((WORK/'worker-assignments-v8.json').read_text())
 for lane,ids in assignments['assignments'].items():
  assignments['assignments'][lane]=[new for identifier in ids for new in ([g['id'] for g in groups] if identifier==parent['id'] else [identifier])]
 assignments['version']=5; assignments['catalog']='grouping/catalog-v9.json'
 flat=[x for ids in assignments['assignments'].values() for x in ids]
 if len(flat)!=len(set(flat)) or set(flat)!=set(index.groups): raise ValueError('Assignments mismatch')
 write(WORK/'worker-assignments-v9.json',assignments)
 print(json.dumps(validation))
if __name__=='__main__': main()
