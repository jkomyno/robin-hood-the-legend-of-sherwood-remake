"""Freeze a conservative ladder-band exclusion for hidden cottage wall pixels.

This is a derived ownership exclusion, not a replacement native silhouette.
The band includes gaps between rungs, so the wall behind them stays unknown.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    root=next(p for p in Path(__file__).resolve().parents if (p/'level-editor/work/leicester-refinement/mask-audit/source-masks.json').exists())
    original=root/'level-editor/work/leicester-refinement/mask-audit/source-masks.json';constraints=json.loads(original.read_text());inventory_path=(original.parent/constraints['mask_inventory']).resolve();inventory=json.loads(inventory_path.read_text())
    for m in inventory['masks']:
        if m.get('png'):m['png']=str((inventory_path.parent/m['png']).resolve())
    box=[2412,618,30,94];points=[]
    for x,y,z in [(2416.394,-1206.113,76.946),(2428,-1197.823,76.946),(2435.569,-1221.603,0),(2422.819,-1230.717,0)]:points.append((x-box[0],-y*math.sin(math.radians(35))-z*math.cos(math.radians(35))-box[1]))
    mask=Image.new('L',tuple(box[2:]));ImageDraw.Draw(mask).polygon(points,fill=255);mask=mask.filter(ImageFilter.MaxFilter(5));mask.save(out/'ladder-band.png')
    inventory['masks'].append({'index':100021,'layer':-1,'layer_index':100021,'png':'ladder-band.png','box_top_left':box[:2],'box_size':box[2:],'derived':True,'purpose':'Conservative exclusion of ladder source pixels and unseen wall between rungs; not a native game mask.'})
    (out/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n');constraints['mask_inventory']='inventory.json'
    for record in constraints['projections']['exterior']['assignments']:
        if record['source_node'] in ['building-016','building-017','building-018','building-020','building-022','building-023']:
            record.setdefault('exclude_mask_indices',[]).append(100021);record['exclusions_reviewed']=True;record['exclusion_reason']+=' Conservative derived ladder band100021 excludes foreground ladder artwork and unseen wall behind it.'
    (out/'source-masks.json').write_text(json.dumps(constraints,indent=2)+'\n')
    source=root/'level-editor/work/leicester-refinement/layers/covered.png';crop=Image.open(source).convert('RGB').crop((box[0],box[1],box[0]+box[2],box[1]+box[3]));crop.resize((180,564)).save(out/'source-closeup.png')
    overlay=crop.copy();overlay.paste((255,0,255),(0,0),mask.point(lambda x:x//3));overlay.resize((180,564)).save(out/'exclusion-overlay.png')
    (out/'evidence.json').write_text(json.dumps({'source_sha256':sha(source),'native_manifest_sha256':sha(inventory_path),'derived_mask_sha256':sha(out/'ladder-band.png'),'source_region':box,'world_anchor_source':'Canonical ladder021 endpoint geometry, checked against source closeup.','policy':'Exclude conservatively from house; keep ladder receiver constrained by native146. Unknown wall pixels are gray. No source colors changed.','review':'Source-closeup and exclusion-overlay must be visually inspected before packet preparation.'},indent=2)+'\n')
if __name__=='__main__':main()
