"""Draw actual rock mesh edges over untouched source and numbered outline targets."""
from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw
W=Path(__file__).resolve().parents[3]/'level-editor/work/nottingham-refinement';P=W/'round-15/assets/nottingham-castle-west-rocks'
r=json.loads((P/'geometry-report.json').read_text());src=Image.open(W/'source-states/covered.png').convert('RGB');boxes=[(0,1980,365,2340),(635,2060,875,2180)];panels=[]
for box in boxes:
 scale=2;bare=src.crop(box).resize(((box[2]-box[0])*scale,(box[3]-box[1])*scale),Image.Resampling.NEAREST);overlay=bare.copy();d=ImageDraw.Draw(overlay)
 def xy(p):return ((p[0]-box[0])*scale,(p[1]-box[1])*scale)
 for obj in r['objects']:
  points=obj['source_xy']
  if not any(box[0]<=x<=box[2]for x,y in points):continue
  for a,b in obj['edges']:d.line([xy(points[a]),xy(points[b])],fill=(0,220,220),width=1)
  for section in obj['source_lobes']:
   for i,p in enumerate(section['outline']):
    x,y=xy(p);d.ellipse((x-2,y-2,x+2,y+2),fill='yellow');d.text((x+3,y-9),str(i+1),fill='yellow',stroke_width=1,stroke_fill='black')
   p=section['outline'];x=sum(q[0]for q in p)/len(p);y=sum(q[1]for q in p)/len(p);d.text(xy((x,y)),section['name'],fill='white',stroke_width=1,stroke_fill='black')
 combined=Image.new('RGB',(bare.width*2,bare.height+30),'#202020');combined.paste(bare,(0,30));combined.paste(overlay,(bare.width,30));d=ImageDraw.Draw(combined);d.text((5,8),'Untouched source',fill='white');d.text((bare.width+5,8),'Actual edges / numbered contour targets (2-3px uncertainty)',fill='white');panels.append(combined)
width=max(p.width for p in panels);out=Image.new('RGB',(width,sum(p.height for p in panels)+10),'#202020');y=0
for p in panels:out.paste(p,(0,y));y+=p.height+10
out.save(P/'inspection/source-comparison.png');print(P/'inspection/source-comparison.png')
