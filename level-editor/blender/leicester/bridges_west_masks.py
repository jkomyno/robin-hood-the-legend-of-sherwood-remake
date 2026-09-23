"""Add source-reviewed west landing deck ownership before freezing its packet."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageChops
from bridges_west_supports import SUPPORTS
ROOT=Path('level-editor/work/leicester-refinement').resolve()
def main():
 workspace=ROOT/'round-1/bridge-revision-archive/pre-hardware/assets-v2/leicester-west-tower-footbridge'
 if not workspace.exists():workspace=ROOT/'round-1/assets-v2/leicester-west-tower-footbridge'
 old=json.loads((workspace/'source-masks.json').read_text());inventory=Path(old['mask_inventory']);native=json.loads(inventory.read_text());records=[dict(m,png=str((inventory.parent/m['png']).resolve())) if m.get('png') else m for m in native['masks']];lookup={m['index']:m for m in records}
 source=workspace/'reference/source.png';image=Image.open(source);points=json.load(open('datadirs/fullgame_gog_hackable/Data/Levels/Leicester.rhp.json'))['sight_obstacles'][226]['points'];top=[(p['x'],p['y']-p['z_top']) for p in points]
 mask=Image.new('L',image.size);ImageDraw.Draw(mask).polygon(top,fill=255)
 for index in [330,331,333,352]:
  m=lookup[index];layer=Image.new('L',image.size);layer.paste(Image.open(m['png']).convert('L'),tuple(m['box_top_left']));mask=ImageChops.subtract(mask,layer)
 out=ROOT/'bridge-evidence/west-footbridge-ownership-supports-v2';out.mkdir(exist_ok=True);bbox=mask.getbbox();bitmap=out/'deck.png';mask.crop(bbox).save(bitmap)
 records.append({'index':213226,'layer':-1,'layer_index':213226,'png':str(bitmap),'mask_type':0,'box_top_left':list(bbox[:2]),'box_size':[bbox[2]-bbox[0],bbox[3]-bbox[1]],'ownership_derivation':{'role':'visible deck','method':'Native deck footprint projected to source, excluding native castle330/331, foreground rail333 and tower352.'}})
 supports=Image.new('L',image.size)
 def contains(outline,x,y):
  inside=False
  for (ax,ay),(bx,by) in zip(outline,outline[1:]+outline[:1]):
   if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:inside=not inside
  return inside
 for _,_,outline in SUPPORTS:
  for y in range(int(min(p[1] for p in outline)),int(max(p[1] for p in outline))+1):
   for x in range(int(min(p[0] for p in outline)),int(max(p[0] for p in outline))+1):
    if contains(outline,x+.5,y+.5):supports.putpixel((x,y),255)
 for index in [330,331,333,352]:
  m=lookup[index];layer=Image.new('L',image.size);layer.paste(Image.open(m['png']).convert('L'),tuple(m['box_top_left']));supports=ImageChops.subtract(supports,layer)
 bounds=supports.getbbox();support_bitmap=out/'supports.png';supports.crop(bounds).save(support_bitmap)
 records.append({'index':213227,'layer':-1,'layer_index':213227,'png':str(support_bitmap),'mask_type':0,'box_top_left':list(bounds[:2]),'box_size':[bounds[2]-bounds[0],bounds[3]-bounds[1]],'ownership_derivation':{'role':'visible structural timber','source_polygons':[outline for _,_,outline in SUPPORTS]}})
 support_view=image.convert('RGBA');support_view.putalpha(supports);support_view.crop((270,875,475,1130)).resize((820,1020)).save(out/'owned-supports.png')
 path=out/'inventory.json';path.write_text(json.dumps({'version':1,'source':str(inventory),'masks':records},indent=2)+'\n');old['mask_inventory']=str(path)
 entries=old['projections']['exterior']['assignments'];entries[:]=[entry for entry in entries if not(entry.get('source_node')=='building-226' and entry.get('projection_component'))]
 (out/'initial-masks.json').write_text(json.dumps(old,indent=2)+'\n')
 image=image.convert('RGBA');image.putalpha(mask);image.crop((270,875,470,1060)).resize((800,740)).save(out/'owned-source.png');(out/'review.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'accepted_pixels':sum(v>0 for v in mask.getdata()),'deck_source_polygon':top,'excluded_native_masks':[330,331,333,352],'support_source_polygons':SUPPORTS,'support_owned_pixels':sum(v>0 for v in supports.getdata()),'support_depth_hypothesis':'Landing-edge plane extended downward to ground0. Dark pixels below the ground intersection may be water reflection and are not assigned without separate depth authority.'},indent=2)+'\n')
if __name__=='__main__':main()
