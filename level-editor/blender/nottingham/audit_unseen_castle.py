"""Audit source-visible castle surfaces and rebuild reviewed native mask assignments."""
import argparse,collections,hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from correct_source_projection import geometry,geometry_sha

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['rays','rebuild','northeast']);p.add_argument('--round',type=int,default=27);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 from refinement_review import _tree
 from refinement_workspace import prepare,modified
 from PIL import Image,ImageChops
 inv=WORK/'mask-review/inventory-v11';meta=json.loads((inv/'manifest.json').read_text())['masks'];out=WORK/'castle-audit/unseen';out.mkdir(exist_ok=True)
 def mask(indices):
  result=Image.new('L',(2304,3520))
  for n in indices:
   e=meta[n];layer=Image.new('L',result.size);layer.paste(Image.open(inv/e['png']).convert('L'),tuple(e['box_top_left']));result=ImageChops.lighter(result,layer)
  return result
 s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s))
 specs=[('watchtower',1,[467,468,469,470],[449,445]),('southeast-spire',4,[445],[]),('northwest-spire',1,[442],[]),('northeast-spire',1,[444],[]),('southwest-stair',5,[278],[])]
 for name,rd,inc,exc in specs:
  old=WORK/f'round-{rd}/assets/nottingham-castle-{name}';cfg=json.loads((old/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));bpy.context.view_layer.update();bpy.context.window.scene=bpy.data.scenes[cfg['scene_name']];objects=[o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH' and not o.hide_render];targets=[o for o in objects if o.get('source_node') in cfg['part_ids']];allowed=ImageChops.subtract(mask(inc),mask(exc));allowed.save(out/f'{name}-owned-native.png')
  if a.mode=='rays':
   tree,owners,_=_tree(objects);own,ownowners,_=_tree(targets);box=allowed.getbbox();counts=collections.Counter();witnesses=collections.defaultdict(list)
   for y in range(box[1],box[3]):
    for x in range(box[0],box[2]):
     if not allowed.getpixel((x,y)):continue
     origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,normal,i,_=own.ray_cast(origin,-toward)
     if i is None:key='no_receiver'
     else:
      _,_,i2,_=tree.ray_cast(origin,-toward);o=ownowners[i];first=owners[i2] if i2 is not None else None;key=o.get('source_node')+(':visible' if first==o else ':blocked:'+str(first.get('source_node') if first else None))
      if first==o and normal.dot(toward)<float(o.get('projection_min_cosine',.05)):key+=':facing'
     counts[key]+=1
     if len(witnesses[key])<100:witnesses[key].append([x,y])
   report=dict(asset_id=cfg['asset_id'],model_sha256=hashlib.sha256((old/'model.blend').read_bytes()).hexdigest(),counts=dict(counts),witnesses=dict(witnesses),properties={o.get('source_node'):{k:str(v) for k,v in o.items() if 'projection' in k} for o in targets})
   (out/f'{name}-rays.json').write_text(json.dumps(report,indent=2)+'\n');print(name,dict(counts),flush=True)
  elif (a.mode=='rebuild' and name=='watchtower') or (a.mode=='northeast' and name=='northeast-spire'):
   before=geometry();m=json.loads((old/'source-masks.json').read_text())
   for e in m['projections']['exterior']['assignments']:
    if e['source_node'] not in cfg['part_ids']:continue
    n=e['source_node'];e.clear();e.update(source_node=n,reviewed=True,mask_indices=inc,exclude_mask_indices=exc,exclusions_reviewed=True,exclusion_reason='Native449 is the foreground hall and445 its separate southeast spire.',constraint_kind='reviewed-native-silhouette',native_ownership_reviewed=True,review_evidence=str(out/'watchtower-native.png'),review_note='Full shaft and walkway467 plus doorway469/470. Broad native467 is clipped by exact neighboring hall449 and spire445 silhouettes; first-hit source ray gating remains active.')
   
   if name=='watchtower':
    m['projections']['exterior']['occluder_constraints']=[dict(reviewed=True,source_node=f'building-{n:03}',receiver_nodes=cfg['part_ids'],mask_indices=[445],reason='Dense source-ray classification identifies foreground spire proxies extending beyond native445 into exposed watchtower masonry. Restrict only those foreign proxy blockers to their native silhouette; keep all own and unlisted blockers.',review_evidence=str(WORK/'round-27/assets/nottingham-castle-watchtower/inspection/source-coverage-domain.png')) for n in [516,517,518]]
   if name=='northeast-spire':
    from PIL import ImageDraw
    import shutil
    folder=out/'northeast-inventory';folder.mkdir(exist_ok=True);metadata=json.loads((inv/'manifest.json').read_text());ridge=[(450,372),(465,386),(475,395),(485,405),(495,414),(505,425),(515,434),(525,442),(535,449),(550,463)]
    roof=Image.new('L',(2304,3520));ImageDraw.Draw(roof).polygon(ridge+[(550,3520),(450,3520)],fill=255)
    ownmask=ImageChops.subtract(mask([444]),roof);ownmask.save(folder/'001000.png');occluder=ImageChops.subtract(mask([449,453]),ownmask);occluder.save(folder/'001001.png')
    for row in metadata['masks']:row['png']=str((inv/row['png']).resolve())
    for index in [1000,1001]:metadata['masks'].append(dict(index=index,png=f'{index:06}.png',layer=0,layer_index=-1,mask_type=0,box_top_left=[0,0],box_size=[2304,3520],character_polyline=None,projectile_polyline=None,obstacle_indices=[]))
    (folder/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n');m['mask_inventory']=str(folder/'manifest.json')
    for e in m['projections']['exterior']['assignments']:
     if e['source_node'] in cfg['part_ids']:
      node=e['source_node'];e.clear();e.update(source_node=node,reviewed=True,mask_indices=[1000],constraint_kind='reviewed-source-trace',native_ownership_reviewed=True,review_evidence=str(out/'ne-ridge-grid.png'),review_note='Native444 clipped at measured foreground roof ridge. Source-visible turret masonry above ridge remains owned; roof below is excluded.')
    m['projections']['exterior']['occluder_constraints']=[dict(reviewed=True,source_node=f'building-{n:03}',receiver_nodes=cfg['part_ids'],mask_indices=[1001],reason='Source-observed hall roof ridge excludes the exposed rear turret masonry. Scope the three demonstrated overreaching foreign roof proxies; keep own and all unlisted blockers.',review_evidence=str(out/'ne-blocker-close.png')) for n in [505,506,508]]
    (out/'northeast-ridge-trace.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256((old/'reference/source.png').read_bytes()).hexdigest(),ridge_pixels=ridge,native_parent=444,manual_uncertainty_pixels=1),indent=2)+'\n')
   mp=out/f'{name}-masks.json';mp.write_text(json.dumps(m,indent=2)+'\n');dest=WORK/f'round-{a.round}/assets/{cfg["asset_id"]}'
   prepare(dest,asset_id=cfg['asset_id'],scene_name=cfg['scene_name'],collection_name=cfg['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=mp,width=cfg['width'],height=cfg['height'],context_padding=cfg['context_padding'],framing_padding=cfg.get('framing_padding',1.04))
   modified(dest);assert before==geometry()
   (dest/'projection-correction.json').write_text(json.dumps(dict(status='awaiting-independent-review',geometry_unchanged=True,geometry_before_sha256=geometry_sha(before),geometry_after_sha256=geometry_sha(geometry()),previous_workspace=str(old)),indent=2)+'\n')
if __name__=='__main__':main()
