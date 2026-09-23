"""Review the Custom1 stall's dark curtain where native occlusion masks have holes."""
from pathlib import Path
import hashlib,json,shutil
from PIL import Image,ImageDraw,ImageChops
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement'
P=W/'mask-review/inventory-v11';OUT=W/'mask-review/inventory-v11-custom1-curtain';AUDIT=W/'environment-audit/custom1-props'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def freeze(path,value):
 text=json.dumps(value,indent=2)+'\n'
 if path.exists()and path.read_text()!=text:raise ValueError('Refusing authority mutation: '+str(path))
 path.write_text(text)

def main():
 source=W/'source-states/nottingham-custom1.png';inventory=json.loads((P/'manifest.json').read_text())
 if not OUT.exists():shutil.copytree(P,OUT,ignore=shutil.ignore_patterns('manifest.json'))
 polygon=[(964,1047),(1061,1069),(1060,1108),(963,1084)]
 mask=Image.new('L',(2304,3520));ImageDraw.Draw(mask).polygon(polygon,fill=255)
 # Native counter/vessels and canopy are explicit foreground exclusions.
 for index in [513,515]:
  row=next(r for r in inventory['masks']if r['index']==index);layer=Image.new('L',mask.size);layer.paste(Image.open(P/row['png']).convert('L'),tuple(row['box_top_left']));mask=ImageChops.subtract(mask,layer)
 filename='authored-custom1-stall-curtain.png';mask.save(OUT/filename);index=max(r['index']for r in inventory['masks'])+1
 inventory['masks'].append(dict(index=index,png=filename,box_top_left=[0,0],box_size=[2304,3520],layer=None,layer_index=None,synthetic=True,constraint_kind='reviewed-authored-source-domain',source_sha256=sha(source),polygon=polygon,excluded_native_masks=[513,515],scope='Dark curtain/service opening on548 only; native foreground counter/vessels and canopy excluded; exact first-hit receiver still required.'))
 freeze(OUT/'manifest.json',inventory)
 box=(952,1035,1070,1120);raw=Image.open(source).convert('RGB').crop(box);accepted=Image.new('RGB',raw.size,'#555');accepted.paste(raw,mask=mask.crop(box));scale=6;out=Image.new('RGB',(raw.width*scale*2,raw.height*scale+25),'#222');out.paste(raw.resize((raw.width*scale,raw.height*scale),Image.Resampling.NEAREST),(0,25));out.paste(accepted.resize((raw.width*scale,raw.height*scale),Image.Resampling.NEAREST),(raw.width*scale,25));ImageDraw.Draw(out).text((5,5),'Original Custom1 | Authored curtain only; counter/vessels and canopy excluded',fill='white');out.save(AUDIT/'curtain-ownership.png')
 freeze(AUDIT/'curtain-ownership.json',dict(source_sha256=sha(source),parent_inventory_sha256=sha(P/'manifest.json'),inventory_sha256=sha(OUT/'manifest.json'),authored_mask_index=index,source_node='building-548',polygon=polygon,excluded_native_masks=[513,515],accepted_pixels=sum(mask.histogram()[128:]),native_records_unchanged=inventory['masks'][:527]==json.loads((P/'manifest.json').read_text())['masks'][:527],evidence='curtain-ownership.png',rationale='The recovered mission artwork visibly contains the dark tent curtain, but native occlusion masks513–515 omit these service-opening pixels. This authored positive domain is restricted to the opening and subtracts foreground counter/vessels and canopy.'))
 print(index)
if __name__=='__main__':main()
