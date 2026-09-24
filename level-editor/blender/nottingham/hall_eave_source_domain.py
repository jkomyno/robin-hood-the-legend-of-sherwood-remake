"""Restore original masonry on the visible vertical covered-state fascia."""
import json
from pathlib import Path

def apply(workspace):
 w=Path(workspace).resolve();p=w/'source-masks.json';m=json.loads(p.read_text());rows=[a for a in m['projections']['exterior']['assignments']if a.get('source_node')=='building-530'and a.get('projection_component')=='castle-hall-ceiling-cover']
 if not rows:
  a={'source_node':'building-530','projection_component':'castle-hall-ceiling-cover'};m['projections']['exterior']['assignments'].append(a);rows=[a]
 assert len(rows)==1
 rows[0].pop('accepted_source_pixels',None)
 rows[0].update(mask_indices=[449],exclude_mask_indices=[442,444,445,451],reviewed=True,native_ownership_reviewed=True,exclusions_reviewed=True,constraint_kind='reviewed-visible-eave-fascia',review_note='The two-unit vertical fascia below the front gable is visible original masonry. Faces2/8 are vertical and source-facing (dot0.703/0.619); assign covered native449 while retaining actual first-hit occlusion. This component is absent in the revealed state.',exclusion_reason='Separate spires retain source ownership.',review_evidence=str(w/'inspection/independent-ceiling-fringe.png'))
 p.write_text(json.dumps(m,indent=2)+'\n')
if __name__=='__main__':
 import sys
 apply(sys.argv[1])
