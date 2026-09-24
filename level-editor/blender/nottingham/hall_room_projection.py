"""Restore exposed hall room tiles, landings and retained masonry ownership."""
import sys,json,copy,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from correct_source_projection import geometry,geometry_sha
from hall_complete_projection import OUT,write

def main():
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 from PIL import Image,ImageChops,ImageDraw
 from refinement_workspace import prepare,modified,_absolute_manifest_images
 from asset_reference_views import render_states
 bpy.ops.wm.open_mainfile(filepath=str(OUT/'model.blend'));before=geometry();m=json.loads((OUT/'source-masks.json').read_text());l=json.loads((OUT/'projection-layers.json').read_text());ip=Path(json.loads((OUT/'mask-reference/assignments.json').read_text())['mask_inventory']);inv=json.loads(ip.read_text());meta={r['index']:r for r in inv['masks']};size=Image.open(l['sources']['interior']).size;folder=WORK/'hall-completeness/room-inventory';folder.mkdir(exist_ok=True)
 def native(n):
  e=meta[n];im=Image.new('L',size);im.paste(Image.open(ip.parent/e['png']).convert('L'),tuple(e['box_top_left']));return im
 for e in inv['masks']:e['png']=str((ip.parent/e['png']).resolve())
 proposal=json.loads((WORK/'castle-audit/v15-floor-independent/floor-domain-expansion-proposal.json').read_text());floor=Image.new('L',size);ImageDraw.Draw(floor).polygon([tuple(x)for x in proposal['polygon']],fill=255)
 patch=next(p for p in l['patches']if p['id']=='patch-008')['graphic'];alpha=Image.new('L',size);im=Image.open(patch['alpha']).convert('L');alpha.paste(im,tuple(patch['bbox'][:2]))
 wall=ImageChops.lighter(native(461),ImageChops.subtract(native(449),alpha))
 for n,im in [(1100,floor),(1101,wall)]:
  path=folder/f'{n:06}.png';im.save(path);inv['masks'].append({'index':n,'png':path.name,'layer':0,'layer_index':-1,'mask_type':0,'box_top_left':[0,0],'box_size':list(size),'character_polyline':None,'projectile_polyline':None,'obstacle_indices':[]})
 write(folder/'manifest.json',inv);m['mask_inventory']=str(folder/'manifest.json');review=str(WORK/'castle-audit/v15-floor-independent/floor-domain-expansion-proposal.png')
 for a in m['projections']['interior-patch-008']['assignments']:
  if a['source_node']=='building-501'and a.get('projection_component')=='castle-hall-floor':a.update(mask_indices=[1100],constraint_kind='reviewed-source-trace',review_evidence=review,review_note='Expanded floor boundary follows the original rear and right wall-to-tile contacts; keep measured furniture/stair exclusions and first-hit checks.')
  if a['source_node']=='building-504'and not a.get('projection_component'):a.update(mask_indices=[1101],review_evidence=str(WORK/'hall-completeness/exterior-native-domains.png'),review_note='Retained interior native461 plus source-visible exterior449 outside room-patch alpha; prevents deleting the unchanged outer masonry while preserving the room state.')
  if a['source_node']in ['building-499','building-503','building-508','building-526']:
   node=a['source_node'];a.clear();a.update(source_node=node,reviewed=True,mask_indices=[456]if node=='building-499'else[456,461,465],exclude_mask_indices=[462,463,464,466],exclusions_reviewed=True,exclusion_reason='Independent furniture and chandelier silhouettes remain owned by their explicit receivers.',constraint_kind='reviewed-native-silhouette',native_ownership_reviewed=True,review_evidence=str(OUT/'inspection/independent-blocked-interior.png'),review_note='Original revealed art shows landing499, low parapet503, upper masonry508 and stone cut edge526. Removed room covers must not block these interior receivers.')
 nodes=['building-499','building-503','building-508','building-526'];r=l['projection_reviews']['patch-008'];r['receiver_nodes']=sorted(set(r['receiver_nodes']+nodes))
 m['projections']['interior-patch-008']['occluder_constraints']=[x for x in m['projections']['interior-patch-008'].get('occluder_constraints',[])if x['source_node']!='building-504']
 m['projections']['interior-patch-008'].setdefault('occluder_constraints',[]).append({'reviewed':True,'source_node':'building-504','receiver_nodes':['building-501'],'mask_indices':[461],'reason':'Measured visible tile646779 is blocked by an oversized retained wall504 outside native461; restrict only floor receiver source-ray blocking to actual wall artwork.','review_evidence':str(WORK/'castle-audit/v15-floor-independent/source-witnesses.json')})
 cfg=json.loads((OUT/'workspace.json').read_text())
 m['projections']['exterior'].setdefault('occluder_constraints',[]).extend([{'reviewed':True,'source_node':f'building-{n}','receiver_nodes':cfg['part_ids'],'mask_indices':[428,435,438],'reason':'Independent original-source classification finds overreaching stair proxies reject exposed hall masonry outside the native stair/conical silhouette. Preserve all actual foreground blockers within these domains.','review_evidence':str(WORK/'castle-audit/hall39-blocker-independent/stair-domain-comparison.png')}for n in [486,487,498]])
 mp=WORK/'hall-completeness/room-complete-masks.json';lp=WORK/'hall-completeness/room-complete-layers.json';write(mp,m);write(lp,l)
 write(OUT/'source-masks.json',json.loads((OUT/'mask-reference/assignments.json').read_text()));write(OUT/'projection-layers.json',_absolute_manifest_images(json.loads((OUT/'reference/layers.json').read_text()),OUT/'reference'))
 dest=WORK/'round-40/assets/nottingham-castle-main-hall'
 prepare(dest,asset_id=cfg['asset_id'],scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],source_path=OUT/'reference/source.png',grouping_manifest=OUT/'reference/grouping.json',inventory_path=OUT/'reference/inventory.json',review_path=OUT/'reference/grouping-review.json',projection_manifest=lp,source_mask_manifest=mp,width=cfg['width'],height=cfg['height'],context_padding=cfg['context_padding'],framing_padding=cfg.get('framing_padding',1.04))
 modified(dest);assert geometry()==before
 render_states(dest,dest/'states-room');write(dest/'state-packet.json',{'version':1,'directory':str(dest/'states-room'),'revealed_input':'input'})
 write(dest/'candidate.json',{'version':1,'asset_id':cfg['asset_id'],'status':'refinement-in-progress','geometry_reviewed':False,'inspected_views':[],'recipe':str(Path(__file__).resolve())})
 write(dest/'room-projection-correction.json',{'geometry_unchanged':True,'geometry_sha256':geometry_sha(before),'new_interior_receivers':nodes,'floor_trace':proposal,'status':'awaiting-independent-full-coverage-review'})
if __name__=='__main__':main()
