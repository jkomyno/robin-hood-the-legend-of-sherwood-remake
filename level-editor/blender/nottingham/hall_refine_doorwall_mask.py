"""Restore the revealed hall's source-visible outer doorway walls."""
import json,sys
from pathlib import Path

def apply(workspace):
 p=Path(workspace)/'source-masks.json';m=json.loads(p.read_text());matches=0
 for a in m['projections']['interior-patch-008']['assignments']:
  if a['source_node']=='building-504'and not a.get('projection_component'):
   a['mask_indices']=[449];a['exclude_mask_indices']=sorted((set(a.get('exclude_mask_indices',[]))-{456,465})|{1110});a['review_note']='Independent original-art comparison confirms retained504 supports left outer doorway and right doorway jamb, roof rim and interior walls. Full native449 in revealed state rejects coarse456/465 room envelopes over original doorway walls and retains furniture masks, first-hit ownership and foreign silhouettes only outside patchalpha.';a['review_evidence']=str((Path(workspace)/'inspection/independent-504-rejected.png').resolve());matches+=1
 assert matches==1,matches
 for a in m['projections']['interior-patch-008']['assignments']:
  if a['source_node']in ['building-505','building-506']and a.get('projection_component')=='castle-hall-retained-roof':
   a['mask_indices']=[449];a['exclude_mask_indices']=[1110];a['review_note']='Revealed retained roof receiver includes source-visible underroof rafters beyond native460. State-specific source prevents covered shingle bleed; native449 plus foreign-outside-patch and actual first-hit retain source ownership.';a['review_evidence']=str((Path(workspace)/'inspection/remaining-roof-rejects.png').resolve())
 p.write_text(json.dumps(m,indent=2)+'\n')
if __name__=='__main__':apply(sys.argv[1])
