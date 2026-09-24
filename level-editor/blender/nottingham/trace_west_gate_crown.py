"""Measured source cap endpoints for the western castle gate crown."""
import json,hashlib
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement';W=R/'round-28/assets/nottingham-castle-gate-west-tower'
# Each pair follows the ring from front-left around the rear to front-right.
CAPS=[
 ('left-front',[(764,1279),(752,1263)],[(781,1272),(765,1261)]),
 ('left-side',[(752,1253),(761,1235)],[(766,1252),(769,1238)]),
 ('rear-left',[(773,1223),(798,1214)],[(781,1229),(798,1224)]),
 ('rear-center',[(823,1211),(851,1215)],[(823,1222),(846,1225)]),
 ('rear-right',[(868,1224),(887,1239)],[(860,1230),(875,1243)]),
 ('right-side',[(891,1252),(883,1266)],[(878,1250),(872,1259)]),
 ('right-front',[(873,1278),(843,1289)],[(864,1268),(842,1278)]),
 ('front-center',[(821,1293),(790,1290)],[(821,1282),(799,1280)]),
]
def main():
 out=R/'castle-audit/batch6-west-crown';out.mkdir(exist_ok=True);src=W/'reference/source.png';box=(740,1198,904,1330);rows=[]
 im=Image.open(src).convert('RGB').crop(box).resize((984,792),Image.Resampling.NEAREST);marked=im.copy();d=ImageDraw.Draw(marked)
 for j,(name,outer,inner) in enumerate(CAPS):
  points=outer+list(reversed(inner));screen=[((x-box[0])*6,(y-box[1])*6) for x,y in points];d.line(screen+[screen[0]],fill='cyan',width=2)
  for k,((x,y),(sx,sy)) in enumerate(zip(points,screen)):
   number=j*4+k+1;d.ellipse((sx-3,sy-3,sx+3,sy+3),fill='yellow');d.text((sx+4,sy+2),str(number),fill='red',stroke_width=1,stroke_fill='white');rows.append(dict(number=number,cap=name,role=['outer-start','outer-end','inner-end','inner-start'][k],source_pixel=[x,y],uncertainty_pixels=2,visibility='measured'))
 im.save(out/'source.png');marked.save(out/'numbered-corners.png');(out/'trace.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),crop_origin=box[:2],cap_count=8,corners=rows),indent=2)+'\n')
if __name__=='__main__':main()
