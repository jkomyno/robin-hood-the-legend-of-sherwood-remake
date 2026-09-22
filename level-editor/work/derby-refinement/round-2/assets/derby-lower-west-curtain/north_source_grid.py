from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
out=root/'inspection/north-corner-v6';out.mkdir(parents=True,exist_ok=True)
source=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
for name,box in [('lower',(328,1718,356,1764)),('upper',(360,1660,388,1710))]:
 im=source.crop(box).resize(((box[2]-box[0])*18,(box[3]-box[1])*18),Image.Resampling.NEAREST)
 d=ImageDraw.Draw(im)
 for x in range(box[0],box[2]):
  if x%2==0:d.text(((x-box[0])*18,0),str(x),fill='cyan')
 for y in range(box[1],box[3]):
  if y%2==0:d.text((0,(y-box[1])*18),str(y),fill='cyan')
 im.save(out/(name+'-grid.png'))
