from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent;out=root/'inspection/north-corner-v12'
im=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
for name,box in [('front2',(346,1580,372,1622)),('front3',(350,1588,380,1642)),('front4',(368,1610,398,1664)),('front1',(326,1552,358,1606)),('return3',(355,1680,382,1730)),('return1',(326,1715,358,1765)),('return5',(375,1642,402,1692))]:
 scale=18;pad=60
 raw=im.crop(box).resize(((box[2]-box[0])*scale,(box[3]-box[1])*scale),Image.Resampling.NEAREST)
 result=Image.new('RGB',(raw.width+pad,raw.height+pad),'#111111');result.paste(raw,(pad,pad));d=ImageDraw.Draw(result)
 for x in range(box[0],box[2]):
  xx=pad+(x-box[0]+.5)*scale
  d.line((xx,pad-5,xx,pad),fill='white')
  if x%2==0:d.text((xx-8,pad-20),str(x),fill='cyan')
 for y in range(box[1],box[3]):
  yy=pad+(y-box[1]+.5)*scale
  d.line((pad-5,yy,pad,yy),fill='white')
  if y%2==0:d.text((8,yy-4),str(y),fill='cyan')
 result.save(out/(name+'-pixel-axes.png'))
