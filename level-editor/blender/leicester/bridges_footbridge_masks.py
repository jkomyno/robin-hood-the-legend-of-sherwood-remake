"""Review source ownership for the static east village deck and timber supports."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops
ROOT=Path('level-editor/work/leicester-refinement').resolve()
NATIVE=Path('datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.d/masks/manifest.json').resolve()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
 workspace=ROOT/'round-1/assets-v2/leicester-east-village-footbridge'
 archived=ROOT/'round-1/bridge-revision-archive/user-footbridge-projection/leicester-east-village-footbridge'
 if archived.exists():workspace=archived
 old=json.loads((workspace/'source-masks.json').read_text())
 native=json.loads(NATIVE.read_text());source=workspace/'reference/source.png';size=Image.open(source).size
 out=ROOT/'bridge-evidence/east-footbridge-projection-revision-v2';out.mkdir(exist_ok=True)
 level=Path('datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.json')
 points=json.loads(level.read_text())['sight_obstacles'][385]['points']
 top=[(p['x'],p['y']-p['z_top']) for p in points]
 deck=Image.new('L',size);draw=ImageDraw.Draw(deck);draw.polygon(top,fill=255)
 for a,b in [(1,0),(2,1)]:draw.polygon([top[a],top[b],(top[b][0],top[b][1]+7),(top[a][0],top[a][1]+7)],fill=255)
 # Visible near leg and diagonal brace are measured from the native painted
 # source, independently of the inferred 3D support depths. Empty water stays out.
 supports=[[(2206,866),(2211,864),(2211,901),(2206,904)],
           [(2208,899),(2264,847),(2267,848),(2210,904)]]
 support=Image.new('L',size);draw=ImageDraw.Draw(support)
 for polygon in supports:draw.polygon(polygon,fill=255)
 guards=Image.new('L',size)
 for index in [98,176,177]:
  entry=native['masks'][index];im=Image.open(NATIVE.parent/entry['png']).convert('L');layer=Image.new('L',size);layer.paste(im,tuple(entry['box_top_left']));guards=ImageChops.lighter(guards,layer)
 deck=ImageChops.subtract(deck,guards);support=ImageChops.subtract(support,guards)
 old_inventory=Path(old['mask_inventory']);existing=json.loads(old_inventory.read_text())
 records=[dict(entry,png=str((old_inventory.parent/entry['png']).resolve())) if entry.get('png') else entry for entry in existing['masks']]
 evidence={'source_sha256':sha(source),'native_inventory_sha256':sha(NATIVE),'native_level_sha256':sha(level),
  'diagnosis':'The previous explicit include+exclude fallback removed every deck and trestle texel. Runtime native masks176/177 describe foreground railings, not the background-painted bridge deck. Mask98 is neighboring stone and must stay excluded.',
  'deck_polygon_source':top,'deck_fascia_depth_pixels':7,'support_polygons_source':supports,
  'excluded_native_masks':[98,176,177],'geometry_policy':'No geometry edits; pixel ownership only. Source samples outside reviewed timber regions remain rejected.'}
 for index,image,label in [(213850,deck,'deck'),(213851,support,'supports')]:
  bbox=image.getbbox();bitmap=out/f'{label}.png';image.crop(bbox).save(bitmap)
  records.append({'index':index,'layer':-1,'layer_index':index,'png':str(bitmap),'mask_type':0,'box_top_left':list(bbox[:2]),'box_size':[bbox[2]-bbox[0],bbox[3]-bbox[1]],
    'ownership_derivation':{'reviewer':'bootstrap','source_sha256':sha(source),'method':'Explicit source-reviewed timber silhouette with native foreground exclusions','role':label,'bitmap_sha256':sha(bitmap)}})
  evidence[label+'_accepted_pixels']=sum(v>0 for v in image.getdata())
 inventory=out/'inventory.json';inventory.write_text(json.dumps({'version':1,'source':str(NATIVE),'source_sha256':sha(NATIVE),'masks':records},indent=2)+'\n')
 old['mask_inventory']=str(inventory)
 (out/'initial-masks.json').write_text(json.dumps(old,indent=2)+'\n')
 fixed=json.loads(json.dumps(old));entries=fixed['projections']['exterior']['assignments']
 for entry in entries:
  if entry.get('source_node')=='building-385' and not entry.get('projection_component'):
   entry.clear();entry.update(source_node='building-385',mask_indices=[213850,213851],reviewed=True,review_reason='Source-reviewed deck/fascia and timber support silhouettes; native stone98 and rail176/177 removed from these receiver regions.')
 (out/'corrected-masks.json').write_text(json.dumps(fixed,indent=2)+'\n')
 evidence['inventory_sha256']=sha(inventory);(out/'review.json').write_text(json.dumps(evidence,indent=2)+'\n')
 for im,label in [(deck,'deck'),(support,'supports')]:
  preview=Image.open(source).convert('RGBA');preview.putalpha(im);preview.crop((2120,765,2310,955)).resize((760,760)).save(out/f'{label}-owned-source.png')
 print(json.dumps(evidence))
if __name__=='__main__':main()
