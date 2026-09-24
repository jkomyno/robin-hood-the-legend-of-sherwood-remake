"""Assign the transferred terrace parapet its measured hall artwork."""
import json
from pathlib import Path

def apply(workspace):
 from PIL import Image,ImageDraw,ImageChops
 w=Path(workspace).resolve();p=w/'source-masks.json';m=json.loads(p.read_text());cfg=json.loads((w/'workspace.json').read_text());ip=Path(m['mask_inventory']);inv=json.loads(ip.read_text());meta={r['index']:r for r in inv['masks']};size=Image.open(cfg['source_path']).size;trace=w.parents[2]/'castle-audit/hall39-blocker-independent/parapet497-full-trace.json';data=json.loads(trace.read_text());mask=Image.new('L',size);draw=ImageDraw.Draw(mask)
 for polygon in data['polygons']:draw.polygon([tuple(p)for p in polygon],fill=255)
 r=meta[449];native=Image.new('L',size);native.paste(Image.open(ip.parent/r['png']).convert('L'),tuple(r['box_top_left']));mask=ImageChops.darker(mask,native);folder=w/'inspection/terrace-parapet-domain';folder.mkdir(parents=True,exist_ok=True);mask.save(folder/'001113.png')
 roofs=Image.new('L',size)
 for index in [435,438]:
  row=meta[index];layer=Image.new('L',size);layer.paste(Image.open(ip.parent/row['png']).convert('L'),tuple(row['box_top_left']));roofs=ImageChops.lighter(roofs,layer)
 ImageChops.subtract(roofs,mask).save(folder/'001114.png')
 for r in inv['masks']:r['png']=str((ip.parent/r['png']).resolve())
 inv['masks']=[r for r in inv['masks']if r['index']not in [1113,1114]];inv['masks'].append({'index':1113,'png':'001113.png','layer':0,'layer_index':-1,'mask_type':0,'box_top_left':[0,0],'box_size':list(size),'character_polyline':None,'projectile_polyline':None,'obstacle_indices':[]});inv['masks'].append({**inv['masks'][-1],'index':1114,'png':'001114.png'});inventory=folder/'inventory.json';inventory.write_text(json.dumps(inv,indent=2)+'\n');m['mask_inventory']=str(inventory.resolve())
 for label in ['exterior','interior-patch-008']:
  rows=[a for a in m['projections'][label]['assignments']if a.get('source_node')=='building-497'];assert len(rows)==1
  a=rows[0];a['mask_indices']=[1113];a['exclude_mask_indices']=[];a['constraint_kind']='reviewed-source-traced-parapet';a['native_ownership_reviewed']=True;a['review_note']='Transferred497 is the hall terrace parapet. Measured cap/face and uppermerlon polygons intersect native449; foreign491roof and terrace pavement excluded. Actual first-hit ownership remains mandatory.';a['review_evidence']=str(trace)
  constraints=m['projections'][label].setdefault('occluder_constraints',[]);constraints[:]=[r for r in constraints if r['source_node']not in ['building-491','building-492']]
  for node in ['building-491','building-492']:constraints.append({'source_node':node,'mask_indices':[1114],'receiver_nodes':['building-497'],'reviewed':True,'reason':'Independent source-ray census identifies392 own whiteparapet cap/face pixels blocked by broad roof491/492 proxies. Only for receiver497, use435union438 minus tracedown1113; retain real foreign roofs everywhere else.','review_evidence':str(trace.parent/'parapet497-firsthit-overlay.png')})
 p.write_text(json.dumps(m,indent=2)+'\n')
