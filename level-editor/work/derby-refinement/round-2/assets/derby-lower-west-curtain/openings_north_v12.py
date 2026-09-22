"""Independent saved-mesh edges beside raw art and semantic source landmarks."""
import json,math
from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent;out=root/'inspection/north-corner-v12'
original=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
data=json.loads((out/'source-correspondences.json').read_text());segments=json.loads((out/'mesh-on-artwork.json').read_text())['segments_source_pixels']
paths=[]
for run in data['runs']:
 for i in range(0,len(run['corners']),2):
  corners=run['corners'][i:i+2];points=[p for c in corners for p in c]
  box=[min(p[0] for p in points)-7,min(p[1] for p in points)-8,max(p[0] for p in points)+8,max(p[1] for p in points)+7]
  scale=12;size=((box[2]-box[0])*scale,(box[3]-box[1])*scale)
  raw=original.crop(box).resize(size,Image.Resampling.NEAREST);marks=raw.copy();mesh=raw.copy()
  def xy(p):return ((p[0]-box[0])*scale,(p[1]-box[1])*scale)
  d=ImageDraw.Draw(mesh)
  for a,b in segments:d.line((xy(a),xy(b)),fill=(255,40,70),width=1)
  d=ImageDraw.Draw(marks)
  for index,corner in enumerate(corners):
   for role,(p,color,label) in enumerate(zip(corner,['cyan','#ff80ff','yellow'],['near cap','far cap','floor'])):
    x,y=xy(p);d.ellipse((x-2,y-2,x+2,y+2),fill=color);d.text((x+4,y-10),str(index+1)+' '+label,fill=color,stroke_width=1,stroke_fill='black')
   d.line([xy(corner[0]),xy(corner[1])],fill='cyan',width=1);d.line([xy(corner[0]),xy(corner[2])],fill='yellow',width=1)
  d.line([xy(corners[0][2]),xy(corners[1][2])],fill='yellow',width=1)
  sheet=Image.new('RGB',(size[0]*3,size[1]+28),'#222222');d=ImageDraw.Draw(sheet)
  for col,(title,im) in enumerate([('Unmodified source pixels',raw),('Observed semantic corners',marks),('Actual saved mesh edges',mesh)]):
   sheet.paste(im,(col*size[0],28));d.text((col*size[0]+6,8),title,fill='white')
  name=f"{run['name']}-opening-{i//2+1}.png";sheet.save(out/name);paths.append(name)
(out/'openings.md').write_text('# Each North wall opening: raw art, observations, saved geometry\n\nThe red edges are the actual mesh, independently projected and self-visibility tested. Cyan/magenta/yellow dots are the separately recorded source observations. No source contrast or pixels are modified in the first column.\n\n'+'\n\n'.join('!['+p+']('+p+')' for p in paths)+'\n')
