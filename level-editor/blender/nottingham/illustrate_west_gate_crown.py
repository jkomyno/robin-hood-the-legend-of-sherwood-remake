"""Source, numbered observations and actual saved crown mesh comparison."""
import json
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement';W=R/'round-38/assets/nottingham-castle-gate-west-tower';box=(740,1198,904,1330);scale=5
im=Image.open(W/'reference/source.png').convert('RGB').crop(box).resize((820,660),Image.Resampling.NEAREST);trace=im.copy();actual=im.copy();d=ImageDraw.Draw(trace);a=ImageDraw.Draw(actual);r=json.loads((W/'crown-correction.json').read_text());mesh=json.loads((W/'inspection/crown-structure-validation.json').read_text())
def xy(p):return((p[0]-box[0])*scale,(p[1]-box[1])*scale)
number=0
for row in r['corners']:
 for role in ['outer_source','inner_source','notch_floor_source']:
  number+=1;x,y=xy(row[role]);color='magenta'if role=='notch_floor_source'and row['notch_floor_visibility'].startswith('inferred')else'yellow';d.ellipse((x-2,y-2,x+2,y+2),fill=color);d.text((x+3,y),str(number),fill=color,stroke_width=1,stroke_fill='black')
for o in mesh['actual_meshes']:
 for u,v in o['edges']:
  p,q=o['vertices'][u],o['vertices'][v]
  if max(p[1],q[1])<1330:a.line((xy(p),xy(q)),fill=(0,210,255),width=1)
canvas=Image.new('RGB',(2460,690),'white')
for i,p in enumerate([im,trace,actual]):canvas.paste(p,(i*820,30))
d=ImageDraw.Draw(canvas)
for i,t in enumerate(['Original source','Measured corners (yellow); inferred hidden notch floors (magenta)','Actual saved mesh edges']):d.text((i*820+5,8),t,fill='black')
canvas.save(W/'inspection/crown-source-comparison.png');trace.save(W/'inspection/crown-numbered-corners.png');im.save(W/'inspection/crown-source.png')
