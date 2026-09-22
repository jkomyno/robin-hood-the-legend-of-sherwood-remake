"""Retain the measured low grass bank and reject its mistaken roof masks."""
import hashlib,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).resolve().parent))
from freeze_tooling import select_tooling
select_tooling()
from render_slots import acquire
from refinement_workspace import modified
from refine_town_packets import mesh_hash

def main():
 acquire();asset='nottingham-northwest-roof-return';p=WORK/'round-1/assets'/asset
 bpy.ops.wm.open_mainfile(filepath=str(p/'model.blend'));before=mesh_hash(asset);path=p/'source-masks.json';masks=json.loads(path.read_text());rows=masks['projections']['exterior']['assignments'];matches=[i for i,row in enumerate(rows)if row['source_node']=='building-168']
 if len(matches)!=1:raise ValueError('Expected canonical bank assignment')
 rows[matches[0]]={'source_node':'building-168','mask_indices':[527],'reviewed':True,'native_ownership_reviewed':False,'constraint_kind':'unknown-no-approved-source','accepted_source_pixels':0,'review_evidence':'inspection/building-168-bank-diagnosis.json','review_note':'Low grass bank, native material3 and top0..40, adjoining annex141. Roof masks61/63 belong to intervening architecture. Self-visible grass samples have no positive native mask, so source pixels remain explicitly unknown.'};path.write_text(json.dumps(masks,indent=2)+'\n')
 result=modified(p);after=mesh_hash(asset)
 if before!=after:raise ValueError('Projection-only bank review changed geometry')
 (p/'bank-review-validation.json').write_text(json.dumps({'status':'PASS','geometry_before_sha256':before,'geometry_after_sha256':after,'workspace_validation':result,'geometry_mutation':False},indent=2)+'\n');print(result,flush=True)
if __name__=='__main__':main()
