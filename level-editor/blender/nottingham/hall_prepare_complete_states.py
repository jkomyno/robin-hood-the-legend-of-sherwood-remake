"""Prepare full hall state ownership, including architecture uncovered by patch008."""
import sys,json,copy,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from hall_complete_projection import write
OLD=WORK/'round-40/assets/nottingham-castle-main-hall';OUT=WORK/'round-41/assets/nottingham-castle-main-hall'
def main():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from PIL import Image,ImageChops
 from refinement_workspace import prepare
 bpy.ops.wm.open_mainfile(filepath=str(OLD/'model.blend'));cfg=json.loads((OLD/'workspace.json').read_text());m=json.loads((OLD/'source-masks.json').read_text());l=json.loads((OLD/'projection-layers.json').read_text());ip=Path(m['mask_inventory']);inv=json.loads(ip.read_text());meta={r['index']:r for r in inv['masks']};size=Image.open(l['sources']['interior']).size
 def native(n):
  e=meta[n];im=Image.new('L',size);im.paste(Image.open(ip.parent/e['png']).convert('L'),tuple(e['box_top_left']));return im
 patch=next(p for p in l['patches']if p['id']=='patch-008')['graphic'];alpha=Image.new('L',size);alpha.paste(Image.open(patch['alpha']).convert('L'),tuple(patch['bbox'][:2]));foreign=native(442)
 for n in [444,445,451]:foreign=ImageChops.lighter(foreign,native(n))
 foreign=ImageChops.subtract(foreign,alpha);folder=WORK/'hall-completeness/full-state-inventory';folder.mkdir(exist_ok=True);foreign.save(folder/'001110.png')
 for e in inv['masks']:e['png']=str((ip.parent/e['png']).resolve())
 inv['masks'].append({'index':1110,'png':'001110.png','layer':0,'layer_index':-1,'mask_type':0,'box_top_left':[0,0],'box_size':list(size),'character_polyline':None,'projectile_polyline':None,'obstacle_indices':[]});write(folder/'manifest.json',inv);m['mask_inventory']=str(folder/'manifest.json')
 key=lambda a:(a['source_node'],a.get('projection_component'))
 combined={key(a):copy.deepcopy(a)for a in m['projections']['exterior']['assignments']}
 for a in combined.values():
  if a['source_node']in cfg['part_ids']and a.get('exclude_mask_indices'):
   a['exclude_mask_indices']=[n for n in a['exclude_mask_indices']if n not in [442,444,445,451]]+[1110];a['review_note']=a.get('review_note','')+' In the revealed state exclude foreign silhouettes only outside patch008 alpha; removed spire pixels become hall floor/cut masonry.'
 receivers=set(l['projection_reviews']['patch-008']['receiver_nodes'])
 for a in m['projections']['interior-patch-008']['assignments']:
  if a['source_node']in receivers and a.get('mask_indices')!=[527]:combined[key(a)]=copy.deepcopy(a)
 for a in combined.values():
  if a['source_node']=='building-504'and not a.get('projection_component'):
   a['exclude_mask_indices']=[n for n in a.get('exclude_mask_indices',[])if n!=460];a['review_note']+=' Actual saved receiver504 supports the source-visible retained right roof rim; do not exclude its native460 shingle pixels.'
  if a['source_node']=='building-500':
   a['exclude_mask_indices']=[n for n in a.get('exclude_mask_indices',[])if n!=463];a['review_note']+=' Stair witness443754 is original stone inside coarse stool463 envelope; physical first-hit table534 remains authoritative.'
 m['projections']['interior-patch-008']['assignments']=list(combined.values());m['projections']['interior-patch-008']['occluder_constraints']=copy.deepcopy(m['projections']['exterior'].get('occluder_constraints',[]))+m['projections']['interior-patch-008'].get('occluder_constraints',[])
 mp=WORK/'hall-completeness/full-state-masks.json';write(mp,m)
 prepare(OUT,asset_id=cfg['asset_id'],scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],source_path=OLD/'reference/source.png',grouping_manifest=OLD/'reference/grouping.json',inventory_path=OLD/'reference/inventory.json',review_path=OLD/'reference/grouping-review.json',projection_manifest=OLD/'projection-layers.json',source_mask_manifest=mp,width=cfg['width'],height=cfg['height'],context_padding=cfg['context_padding'],framing_padding=cfg.get('framing_padding',1.04))
 write(OUT/'candidate.json',{'version':1,'asset_id':cfg['asset_id'],'status':'refinement-in-progress','geometry_reviewed':False,'inspected_views':[],'recipe':str(Path(__file__).resolve())});print('HALL41 PREPARED FOR HEARTH BOUNDARY CORRECTION',flush=True)
if __name__=='__main__':main()
