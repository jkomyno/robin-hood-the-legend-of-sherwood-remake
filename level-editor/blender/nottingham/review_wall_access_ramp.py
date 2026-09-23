"""Bind the hidden ramp's negative house ownership without inventing source RGB."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 from PIL import Image
 w=R/'round-13/assets/nottingham-south-curtain-wall-2'
 v=json.loads((w/'inspection/independent-building-203-visibility.json').read_text())
 mpath=w/'source-masks.json';m=json.loads(mpath.read_text());inv=Path(m['mask_inventory']);records=json.loads(inv.read_text())['masks'];record=next(x for x in records if x['index']==47)
 image=Image.open(inv.parent/record['png']).convert('L');left,top=record['box_top_left'];points=v['visible_source_pixels']
 accepted=sum(0<=x-left<image.width and 0<=y-top<image.height and image.getpixel((x-left,y-top))>0 for x,y in points)
 if accepted!=len(points):raise ValueError('House47 fails to own every exposed ramp pixel')
 for a in m['projections']['exterior']['assignments']:
  if a['source_node']=='building-203':
   a['exclude_mask_indices']=[47];a['exclusions_reviewed']=True;a['exclusion_reason']='Native47 owns all285 apparent source-camera ramp pixels; these are adjacent house053 plaster, not ramp artwork. Preserve unknown-only positive assignment527.'
   a['review_evidence']=str(w/'inspection/ramp-negative-ownership.json')
 report={'status':'PASS','source_node':'building-203','source_model_sha256':v['model_sha256'],'source_visible_test_pixels':len(points),'native47_house_owned_pixels':accepted,'native47_sha256':sha(inv.parent/record['png']),'positive_mask':527,'excluded_native_masks':[47],'geometry_policy':'Native ramp top160.001 meets platform201 at160.001; preserve this coherent concealed landing and inferred ramp. No visible ramp artwork constrains a replacement shape.','known_pixels_policy':'No source pixels are accepted for203. Single-image house47 occlusion is explicit; do not copy its plaster onto the ramp.','limitation':'The baseline house geometry does not itself cover285 ramp pixels that house47 owns in the artwork. The ramp therefore remains neutral in standalone views; mask authority records this source-layer occlusion.'}
 (w/'inspection/ramp-negative-ownership.json').write_text(json.dumps(report,indent=2)+'\n');mpath.write_text(json.dumps(m,indent=2)+'\n')
if __name__=='__main__':main()
