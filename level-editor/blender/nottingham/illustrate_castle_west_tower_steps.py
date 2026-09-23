"""Show unchanged source pixels beside measured and actual stair corners."""
import json
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3];w=ROOT/'level-editor/work/nottingham-refinement/round-28/assets/nottingham-castle-gate-west-tower'
r=json.loads((w/'inspection/steps-structure-validation.json').read_text());box=(718,1325,799,1418);scale=6
im=Image.open(w/'reference/source.png').convert('RGB').crop(box).resize((486,558),Image.Resampling.NEAREST);trace=im.copy();actual=im.copy();d=ImageDraw.Draw(trace);a=ImageDraw.Draw(actual)
def xy(p):return ((p[0]-box[0])*scale,(p[1]-box[1])*scale)
for row in r['measured_corner_construction_checks']:
 x,y=xy(row['source_pixel']);d.ellipse((x-5,y-5,x+5,y+5),fill='yellow');d.text((x-18,y-17),str(row['number']),fill='cyan',stroke_width=1)
for u,v in r['actual_mesh_edges']:a.line((xy(r['actual_source_vertices'][u]),xy(r['actual_source_vertices'][v])),fill=(0,210,255),width=1)
out=Image.new('RGB',(1458,585),'white');out.paste(im,(0,27));out.paste(trace,(486,27));out.paste(actual,(972,27));d=ImageDraw.Draw(out)
for x,t in [(4,'Original source, nearest-neighbor'),(490,'Three measured far tread leading corners'),(976,'Actual saved mesh edges (hidden ends behind parapet)')]:d.text((x,7),t,fill='black')
out.save(w/'inspection/steps-source-comparison.png')
