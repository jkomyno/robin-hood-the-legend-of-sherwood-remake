"""Add source-reviewed west landing deck ownership before freezing its packet."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageChops
ROOT=Path('level-editor/work/leicester-refinement').resolve()
def main():
 workspace=ROOT/'round-1/bridge-revision-archive/pre-hardware/assets-v2/leicester-west-tower-footbridge'
 if not workspace.exists():workspace=ROOT/'round-1/assets-v2/leicester-west-tower-footbridge'
 old=json.loads((workspace/'source-masks.json').read_text());inventory=Path(old['mask_inventory']);native=json.loads(inventory.read_text());records=[dict(m,png=str((inventory.parent/m['png']).resolve())) if m.get('png') else m for m in native['masks']];lookup={m['index']:m for m in records}
 source=workspace/'reference/source.png';image=Image.open(source);points=json.load(open('datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.json'))['sight_obstacles'][226]['points'];top=[(p['x'],p['y']-p['z_top']) for p in points]
 mask=Image.new('L',image.size);ImageDraw.Draw(mask).polygon(top,fill=255)
 for index in [330,331,333,352]:
  m=lookup[index];layer=Image.new('L',image.size);layer.paste(Image.open(m['png']).convert('L'),tuple(m['box_top_left']));mask=ImageChops.subtract(mask,layer)
 out=ROOT/'bridge-evidence/west-footbridge-ownership';out.mkdir(exist_ok=True);bbox=mask.getbbox();bitmap=out/'deck.png';mask.crop(bbox).save(bitmap)
 records.append({'index':213226,'layer':-1,'layer_index':213226,'png':str(bitmap),'mask_type':0,'box_top_left':list(bbox[:2]),'box_size':[bbox[2]-bbox[0],bbox[3]-bbox[1]],'ownership_derivation':{'role':'visible deck','method':'Native deck footprint projected to source, excluding native castle330/331, foreground rail333 and tower352.'}})
 path=out/'inventory.json';path.write_text(json.dumps({'version':1,'source':str(inventory),'masks':records},indent=2)+'\n');old['mask_inventory']=str(path)
 entries=old['projections']['exterior']['assignments'];entries[:]=[entry for entry in entries if not(entry.get('source_node')=='building-226' and entry.get('projection_component'))]
 (out/'initial-masks.json').write_text(json.dumps(old,indent=2)+'\n')
 image=image.convert('RGBA');image.putalpha(mask);image.crop((270,875,470,1060)).resize((800,740)).save(out/'owned-source.png');(out/'review.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'accepted_pixels':sum(v>0 for v in mask.getdata()),'deck_source_polygon':top,'excluded_native_masks':[330,331,333,352],'geometry_changed':False},indent=2)+'\n')
if __name__=='__main__':main()
