"""Explicit eight-pixel eave/hearth boundary supplement; native masks unchanged."""
import json,hashlib,copy
from pathlib import Path
from PIL import Image
PIXELS=[(433,2837),(434,2837),(435,2837),(436,2837),(433,2838),(434,2838),(435,2838),(434,2839)]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def apply(workspace,masks):
 w=Path(workspace);old=Path(masks['mask_inventory']);inventory=copy.deepcopy(json.loads(old.read_text()));folder=w/'reviewed-eave-domain';folder.mkdir(exist_ok=True)
 for row in inventory['masks']:
  if row.get('png'):row['png']=str((old.parent/row['png']).resolve())
  if row.get('folder'):row['folder']=str((old.parent/row['folder']).resolve())
 index=max(row['index']for row in inventory['masks'])+1
 im=Image.new('L',(4,3))
 for x,y in PIXELS:im.putpixel((x-433,y-2837),255)
 path=folder/'eave-boundary-eight-pixels.png';im.save(path)
 inventory['masks'].append(dict(index=index,png=path.name,box_top_left=[433,2837],box_size=[4,3],synthetic_reviewed_domain=True,reason='Exact eight source pixels at the dark eave/hearth junction, accepted on the exposed roof282 skirt. One-pixel semantic boundary uncertainty; no broad native211 roof transfer.'))
 manifest=folder/'manifest.json';manifest.write_text(json.dumps(inventory,indent=2)+'\n');masks['mask_inventory']=str(manifest.resolve())
 for assignment in masks['projections']['exterior']['assignments']:
  if assignment.get('source_node')=='building-282':
   assert assignment['mask_indices']==[210]
   assignment['mask_indices']=[210,index];assignment['review_note']='Native210 roof plus exactly8 reviewed dark eave/hearth boundary pixels. Root source review accepted the narrow exposed skirt/underside with one-pixel semantic uncertainty; no full211 assignment.';assignment['review_evidence']=str((folder/'evidence.json').resolve())
 evidence=dict(version=1,status='TECHNICAL-SOURCE-REVIEW',source_sha256=sha(w/'reference/source.png'),native_inventory_sha256=sha(old),supplement_sha256=sha(path),pixels=[list(p)for p in PIXELS],receiver='building-282',receiver_face='Vertical outer eave skirt, triangle vertices2,5,1; unchanged V5 geometry.',semantic_uncertainty_pixels=1,geometry_approval='pending-user-review',rationale='The dark horizontal junction is compatible with exposed roof underside above the hearth. Transfer only these8 pixels; all native bitmaps and every other receiver domain remain unchanged.')
 (folder/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 return masks
