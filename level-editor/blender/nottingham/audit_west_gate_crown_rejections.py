"""Expose all rejected source-domain pixels for independent ownership review."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement/round-38/assets/nottingham-castle-gate-west-tower';sys.path.insert(0,str(Path(__file__).parent));sys.argv=['audit_castle_final_source_coverage.py','--',str(W)]
code=(Path(__file__).parent/'audit_castle_final_source_coverage.py').read_text().replace('counts=collections.Counter();','rejected_pixels=collections.defaultdict(list);counts=collections.Counter();').replace('counts[key]+=1','counts[key]+=1\n  if key in ("no_receiver","hit_outside_receiver_assignment"):rejected_pixels[key].append([x,y])')
exec(compile(code,str(Path(__file__).parent/'audit_castle_final_source_coverage.py'),'exec'))
from PIL import ImageDraw
panels=[]
for key,color in [('source',None),('no_receiver',(255,0,255)),('hit_outside_receiver_assignment',(0,255,255))]:
 im=source.crop(tuple(box)).convert('RGB')
 for x,y in rejected_pixels.get(key,[]):im.putpixel((x-box[0],y-box[1]),color)
 im=im.resize((im.width*3,im.height*3),Image.Resampling.NEAREST);panels.append((key,im))
canvas=Image.new('RGB',(sum(im.width for _,im in panels),max(im.height for _,im in panels)+24),'white');d=ImageDraw.Draw(canvas);x=0
for key,im in panels:canvas.paste(im,(x,24));d.text((x+3,4),key,fill='black');x+=im.width
canvas.save(W/'inspection/source-rejection-classification.png');(W/'inspection/source-rejection-pixels.json').write_text(json.dumps(dict(model_sha256=report['model_sha256'],source_bounds=box,pixels=dict(rejected_pixels)),indent=2)+'\n')
