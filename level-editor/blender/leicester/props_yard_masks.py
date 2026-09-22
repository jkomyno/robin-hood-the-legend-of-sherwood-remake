"""Create immutable component masks for the approved mill south yard boundary."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops


def run(root, output):
    root=Path(root).resolve();output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    parent=root/'mask-audit/owned-inventory-v3.json'
    inventory=json.loads(parent.read_text());records={m['index']:m for m in inventory['masks']}
    for m in inventory['masks']:
        m['png']=str((parent.parent/m['png']).resolve())
    # Trace the stone/palisade junction through source pixels. The native
    # silhouette still supplies every outer edge and every visible board gap.
    boundary=[(3058,1100),(3058,1126),(3054,1135),(3054,1149),(3053,1164)]
    polygons={
      21050:(96,[(2974,1100)]+boundary+[(3053,1232),(2974,1232)]),
      21053:(96,boundary+[(3136,1164),(3136,1100)]),
      21051:(46,[(2974,1192),(3028,1192),(3028,1259),(2974,1259)])}
    added=[]
    for index,(native,polygon) in polygons.items():
        m=records[native];x,y=m['box_top_left'];native_image=Image.open(m['png']).convert('L')
        selection=Image.new('L',native_image.size);ImageDraw.Draw(selection).polygon([(a-x,b-y) for a,b in polygon],fill=255)
        owned=ImageChops.darker(native_image,selection);path=output/f'{index}.png';owned.save(path)
        record={'index':index,'box_top_left':m['box_top_left'],'box_size':m['box_size'],'png':str(path),'parent_native_mask':native,'parent_sha256':hashlib.sha256(Path(m['png']).read_bytes()).hexdigest(),'reviewed_polygon':polygon,'reason':{21050:'Complete diagonal stone run; traced palisade junction.',21051:'Foreground stone return from native46; barrel ends before x2974 and fence begins beyond x3028.',21053:'Complete visible palisade from native96; traced stone junction.'}[index]}
        inventory['masks'].append(record);added.append(record)
    (output/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    manifest=json.loads((root/'mask-audit/source-masks-v3.json').read_text());manifest['mask_inventory']=str(output/'inventory.json')
    for a in manifest['projections']['exterior']['assignments']:
        if a.get('source_node') in ['building-050','building-051','building-053']:
            a['mask_indices']=[21000+int(a['source_node'].split('-')[1])];a['evidence']='Reviewed source-mask comparison and junction/front coordinate crops in archived yard-wall texture-cutoff diagnosis. Native96 owns diagonal stone/palisade; native46 owns foreground stone return.'
    (output/'source-masks.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (output/'review.json').write_text(json.dumps({'status':'reviewed','reviewer':'props worker','derived_masks':added,'limitations':['Stone/timber junction follows visible pixels with approximately one pixel ambiguity.','Right palisade extends to the map image boundary; no off-map pixels are supplied.','Foremost stone/fence interface is conservatively retained through x3028.']},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('output');a=p.parse_args();run(a.root,a.output)
