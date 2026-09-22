from pathlib import Path
import json,math,shutil
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
packet=root/'inspection/complete-wall-candidate-v3'
packet.mkdir(exist_ok=True)
corners=packet/'corners';corners.mkdir(exist_ok=True)
for p in (root/'inspection/complete-wall-candidate/corners').iterdir():
 if p.is_file():shutil.copy2(p,corners/p.name)
observations=json.loads((corners/'points.json').read_text())['records']
result=json.loads((root/'traced-crenel-revision.json').read_text())
shift=result['results'][1]['source_corner_height_fit']['source_y_shift']
source=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
residuals=[]
for record in observations:
 name=record['id'];box=record['box'];north=name.startswith('north')
 a,b=((318.9380798,1535.382262),(392.6815491,1644.803565)) if north else ((386.4078064,2118.757557),(511.4077759,2216.992439))
 rows=[]
 im=source.crop(box).resize(((box[2]-box[0])*10,(box[3]-box[1])*10),Image.Resampling.NEAREST);draw=ImageDraw.Draw(im)
 for i,(x,y) in enumerate(record['points']):
  expected=a[1]+(x-a[0])*(b[1]-a[1])/(b[0]-a[0])+(shift if north else 0)
  if i%4 in (1,2):expected+=26*math.cos(math.radians(35))
  rows.append({'id':i+1,'observed':[x,y],'predicted':[x,expected],'error_pixels':abs(expected-y)})
  px=(x-box[0]+.5)*10;oy=(y-box[1]+.5)*10;py=(expected-box[1]+.5)*10
  draw.line((px,oy,px,py),fill='red',width=3)
  draw.ellipse((px-3,oy-3,px+3,oy+3),fill='yellow')
  draw.line((px-4,py,px+4,py),fill='cyan',width=2)
  draw.text((px+5,oy-10),str(i+1),fill='white')
 im.save(corners/(name+'-residual.png'))
 residuals.append({'run':name,'scope':'first two gaps only; remainder unmeasured','points':rows,'rms_pixels':math.sqrt(sum(r['error_pixels']**2 for r in rows)/len(rows))})
(packet/'corner-residuals.json').write_text(json.dumps(residuals,indent=2)+'\n')
(packet/'review.md').write_text('''# Lower West complete-wall candidate — partial trace, not approval-ready

The rejected detached-box revision is withdrawn. These models are closed wall
solids with Boolean notch cuts. All three walls have zero nonmanifold edges,
zero degenerate faces and positive volume. They retain the wall body down to
ground. The approved access stair, turret and wall-walk support are preserved.
Source projection was reapplied. Both section sheets explicitly use48° sun
elevation while keeping the earlier section camera framing.

| Section | Node | Previous notch cuts | Candidate notch cuts |
| --- | --- | ---: | ---: |
| North |025|6|8|
| South |023|11|13|
| South |042|5|6|

The north crown was6.18 source pixels too high at the four directly inspected
top corners. A height-only fit lowers it7.545 world units; these four crown
residuals are0.91,-0.19,0.69,-1.41 pixels. This is local evidence, not proof of
every corner on both complete sections. Other cuts are provisional: the full
ordered source trace and independent rendered-contour residual audit remain
unfinished. Concealed repeats near the roof are explicitly inferred.

## North

![Solid](north/solid.png)

![Source-projected](north/textured.png)

![Original first two gaps](corners/north-025-first-two-gaps-raw.png)

![Numbered source corners](corners/north-025-first-two-gaps.png)

![Observed yellow; predicted cyan; error red](corners/north-025-first-two-gaps-residual.png)

## South

![Solid](south/solid.png)

![Source-projected](south/textured.png)

![Original first two gaps](corners/south-042-first-two-gaps-raw.png)

![Numbered source corners](corners/south-042-first-two-gaps.png)

![Observed yellow; predicted cyan; error red](corners/south-042-first-two-gaps-residual.png)

Exact observations and local analytic crown/notch predictions are recorded in
`corners/points.json` and `corner-residuals.json`. Predictions use the same outer
wall edges and notch depth as the mesh builder; they are not a full raster
contour comparison. Geometry, reprojection and complete source-trace approval
must not be conflated. No catalog, gallery or production scene was changed.
''')
