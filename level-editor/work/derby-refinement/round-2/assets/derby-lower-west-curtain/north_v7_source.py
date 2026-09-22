from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent;out=root/'inspection/north-corner-v7';out.mkdir(parents=True,exist_ok=True)
source=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
for name,box in [('front-start',(304,1520,350,1572)),('bend',(376,1630,410,1685)),('front',(322,1550,388,1664)),('return',(328,1656,394,1766))]:
 im=source.crop(box).resize(((box[2]-box[0])*10,(box[3]-box[1])*10),Image.Resampling.NEAREST)
 im.save(out/(name+'-original.png'))
 d=ImageDraw.Draw(im)
 for x in range(box[0],box[2]):
  if x%4==0:d.text(((x-box[0])*10,0),str(x),fill='cyan')
 for y in range(box[1],box[3]):
  if y%4==0:d.text((0,(y-box[1])*10),str(y),fill='cyan')
 im.save(out/(name+'-grid.png'))
