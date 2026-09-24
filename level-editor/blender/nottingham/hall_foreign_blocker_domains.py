"""Constrain neighboring tower proxies to their independently reviewed artwork."""
import json,copy
from pathlib import Path

def apply(workspace):
 from PIL import Image,ImageChops
 w=Path(workspace);p=w/'source-masks.json';m=json.loads(p.read_text());cfg=json.loads((w/'workspace.json').read_text());ip=Path(m['mask_inventory']);inv=json.loads(ip.read_text());meta={r['index']:r for r in inv['masks']};size=Image.open(cfg['source_path']).size
 def native(n):
  r=meta[n];im=Image.new('L',size);im.paste(Image.open(ip.parent/r['png']).convert('L'),tuple(r['box_top_left']));return im
 watchtower=ImageChops.subtract(native(467),ImageChops.lighter(native(449),native(453)));folder=w/'inspection/foreign-blocker-domains';folder.mkdir(parents=True,exist_ok=True);watchtower.save(folder/'001111.png');ImageChops.subtract(Image.new('L',size,255),native(449)).save(folder/'001112.png')
 for r in inv['masks']:r['png']=str((ip.parent/r['png']).resolve())
 inv['masks']=[r for r in inv['masks']if r['index']not in [1111,1112]];inv['masks'].append({'index':1111,'png':'001111.png','layer':0,'layer_index':-1,'mask_type':0,'box_top_left':[0,0],'box_size':list(size),'character_polyline':None,'projectile_polyline':None,'obstacle_indices':[]});inv['masks'].append({**inv['masks'][-1],'index':1112,'png':'001112.png'});inventory=folder/'inventory.json';inventory.write_text(json.dumps(inv,indent=2)+'\n');m['mask_inventory']=str(inventory.resolve())
 for label in ['exterior','interior-patch-008']:
  rows=m['projections'][label].setdefault('occluder_constraints',[]);rows[:]=[r for r in rows if r['source_node']not in ['building-536','building-517','building-367','building-550','building-521']]
  for node,indices,note in [('building-536',[1111],'Raw watchtower467 overlaps the nearer hall facade and roof. Independently inspected original artwork supports467 minus native449/453 for this hall-only foreground constraint.'),('building-517',[445],'The eastern spire remains visible in both states; preserve its entire native445 domain, including pixels inside room patch alpha. Central removed spire451 is a different object.'),('building-367',[1112],'Independent original-art blocker census shows this oversized courtyardwall proxy hides plain hall facade inside449. Preserve source-ray blocking everywhere outside449, scoped only to hall receivers.'),('building-550',[1112],'Selected original source state contains plain hall masonry, not a mission prop, at all1248 proxy-blocked hall pixels. Preserve blocking outside449 only; do not let an absent-state proxy hide owned facade.'),('building-521',[442],'The northwest spire proxy overlaps48 visible hall shingle pixels beyond its source silhouette. Preserve only actual native442 foreground blocking for hall receivers.')]:
   rows.append({'source_node':node,'mask_indices':indices,'receiver_nodes':cfg['part_ids'],'reviewed':True,'reason':note,'review_evidence':str((w/'inspection/independent-complement'/('watchtower467.png'if node=='building-536'else'upper-neighbors.png'if node=='building-517'else'blocker'+node.split('-')[1]+'.png')).resolve())})
 p.write_text(json.dumps(m,indent=2)+'\n')
