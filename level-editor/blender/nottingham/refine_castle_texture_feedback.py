"""Restore source-owned castle artwork after native-mask review.

Each revision is prepared from the displayed model in a fresh immutable worker;
vertices, faces, transforms and foreign properties remain unchanged.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from correct_source_projection import geometry

def main():
 a=argparse.ArgumentParser();a.add_argument('asset');a.add_argument('--round',type=int,default=24);args=a.parse_args(sys.argv[sys.argv.index('--')+1:]);name=args.asset
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 from refinement_workspace import prepare,modified
 spec={'castle-east-courtyard-wall':(1,[],[]),'castle-gate-west-tower':(1,[284,285,286],[65,67]),'castle-east-round-tower':(5,[293],[])}
 rd,inc,exc=spec[name];old=WORK/f'round-{rd}/assets/nottingham-{name}';out=WORK/f'round-{args.round}/assets/nottingham-{name}';c=json.loads((old/'workspace.json').read_text());m=json.loads((old/'source-masks.json').read_text())
 for e in ([] if name=='castle-east-courtyard-wall' else m['projections']['exterior']['assignments']):
  if e['source_node'] not in c['part_ids']:continue
  node=e['source_node'];e.clear();e.update(source_node=node,reviewed=True,mask_indices=inc,constraint_kind='reviewed-native-silhouette',review_evidence=str(WORK/'castle-audit/review4-texture'),review_note='Reviewed full native silhouette; first-hit receiver gating retained. Tower99 exclusion removed because it contains the tower roof/drum itself.' if name.endswith('round-tower') else 'Native284/285 include the complete crown and lower shaft. Foreground cottage65/chimney67 are explicitly excluded; scene visibility rejects surrounding walls.')
  if exc:e.update(exclude_mask_indices=exc,exclusions_reviewed=True,exclusion_reason='Native65 is the foreground cottage and67 its chimney, not the tower shaft.')
 mask=WORK/f'castle-audit/review4-texture/{name}-masks.json'
 if name=='castle-east-courtyard-wall':
  mask=WORK/'castle-audit/review4-texture/castle-east-courtyard-wall-final-masks.json';m=json.loads(mask.read_text());inc=next(e['mask_indices']for e in m['projections']['exterior']['assignments']if e['source_node']=='building-325')
 if name=='castle-east-courtyard-wall':
  mask=WORK/f'castle-audit/review4-texture/{name}-round{args.round}-masks.json';m['projections']['exterior']['occluder_constraints']=[dict(reviewed=True,source_node=f'building-{n:03}',receiver_nodes=c['part_ids'],mask_indices=([289,375]if n in [337,339]else[51,52,54]),reason='Dense source-ray witnesses lie on visible wall masonry outside the actual foreground gate/greenhouse silhouettes. Scope only these reviewed foreign proxies; own and all unlisted geometry still block.',review_evidence=str(WORK/'round-24/assets/nottingham-castle-east-courtyard-wall/inspection/final-source-ray-coverage.json'))for n in [337,339,81,83,84,89]]
 if name=='castle-east-round-tower':
  wall=json.loads((WORK/'castle-audit/review4-texture/castle-east-courtyard-wall-final-masks.json').read_text());m['mask_inventory']=wall['mask_inventory'];wallindex=next(e['mask_indices']for e in wall['projections']['exterior']['assignments']if e['source_node']=='building-325');m['projections']['exterior']['occluder_constraints']=[dict(reviewed=True,source_node=f'building-{n:03}',receiver_nodes=c['part_ids'],mask_indices=wallindex if n==326 else [61],reason='Independent source/depth audit identifies proxy occluder triangles over visible tower293 artwork. Foreign wall uses reviewed positive masonry domain excluding293; red foreground roof uses native61. All own and unlisted hits continue blocking.',review_evidence=str(WORK/'castle-audit/review4-texture/east-tower-blocker-depth-proof.json'))for n in [326,93,95,96]]
 mask.write_text(json.dumps(m,indent=2)+'\n');bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));before=geometry()
 prepare(out,asset_id=c['asset_id'],scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=mask,width=c['width'],height=c['height'],context_padding=c['context_padding'],framing_padding=c.get('framing_padding',1.04))
 modified(out);assert before==geometry(),'Geometry changed'
 report={'version':1,'status':'awaiting-independent-visual-review','previous_workspace':str(old),'previous_model_sha256':hashlib.sha256((old/'model.blend').read_bytes()).hexdigest(),'model_sha256':hashlib.sha256((out/'model.blend').read_bytes()).hexdigest(),'geometry_unchanged':True,'recipe':str(Path(__file__).resolve()),'mask_indices':inc,'exclude_mask_indices':exc,'source_proof':str(WORK/'castle-audit/review4-texture')}
 (out/'texture-feedback-correction.json').write_text(json.dumps(report,indent=2)+'\n')
 (out/'candidate.json').write_text(json.dumps({'version':1,'asset_id':c['asset_id'],'status':'refinement-in-progress','geometry_reviewed':False,'geometry_refined':False,'inspected_views':[]},indent=2)+'\n')
if __name__=='__main__':main()
