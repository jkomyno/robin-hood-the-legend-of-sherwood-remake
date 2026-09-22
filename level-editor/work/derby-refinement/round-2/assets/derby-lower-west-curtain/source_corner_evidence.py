"""Show individually inspected RGB corners separately from model predictions.

No array-spacing generator is used for observed coordinates. Uncertain points
are labelled as such and excluded from accepted fitting constraints.
"""
from pathlib import Path
import json
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
source=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
out=root/'inspection'/'complete-wall-candidate'/'corners'
out.mkdir(parents=True,exist_ok=True)
records=[
 {'id':'south-042-first-two-gaps','box':[390,2115,435,2178],
  'points':[[401,2130],[401,2149],[411,2157],[411,2138],[421,2146],[421,2165],[431,2173],[431,2154]],
  'confidence':'provisional RGB picks, about2px uncertainty; low shoulders require independent check',
  'accepted_for_final_fit':False},
 {'id':'north-025-first-two-gaps','box':[326,1550,364,1620],
  'points':[[334,1563],[334,1583],[340,1592],[340,1573],[348,1584],[348,1603],[354,1611],[354,1595]],
  'confidence':'provisional RGB picks; exterior/front cap edge ambiguity unresolved',
  'accepted_for_final_fit':False},
]
for r in records:
 box=r['box'];im=source.crop(box).resize(((box[2]-box[0])*10,(box[3]-box[1])*10),Image.Resampling.NEAREST)
 d=ImageDraw.Draw(im)
 xy=[((x-box[0]+.5)*10,(y-box[1]+.5)*10) for x,y in r['points']]
 d.line(xy,fill=(0,220,255),width=2)
 for i,(x,y) in enumerate(xy):
  d.ellipse((x-3,y-3,x+3,y+3),fill=(255,230,0));d.text((x+5,y-10),str(i+1),fill=(255,255,255))
 im.save(out/(r['id']+'.png'))
 source.crop(box).resize(im.size,Image.Resampling.NEAREST).save(out/(r['id']+'-raw.png'))
(out/'points.json').write_text(json.dumps({'status':'PROVISIONAL_NOT_COMPLETE','coordinate_system':'original map pixels, top-left origin','records':records},indent=2)+'\n')
(out/'review.md').write_text('''# Individual source corner inspection — incomplete

These are direct RGB corner picks, not projected model vertices. Yellow dots
are numbered in `points.json`; cyan lines join the inspected front-face edge.
The source is enlarged with nearest-neighbor pixels, and the untouched crop is
shown alongside the annotation. Neither trace has been accepted for a final
fit. In particular, the northern cap-edge choice still needs checking. Other
wall runs are not yet traced; there is no full-wall residual claim.

## South, first two gaps

![Raw source](south-042-first-two-gaps-raw.png)

![Numbered corner picks](south-042-first-two-gaps.png)

## North, first two gaps

![Raw source](north-025-first-two-gaps-raw.png)

![Numbered corner picks](north-025-first-two-gaps.png)
''')
