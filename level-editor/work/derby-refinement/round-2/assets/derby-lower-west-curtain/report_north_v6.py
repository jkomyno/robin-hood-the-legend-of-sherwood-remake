from pathlib import Path
import json
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
out=root/'inspection/north-corner-v6'
source=Image.open(root/'reference/mission-patches/H03_Der_MK-initial.png').convert('RGB')
points=[[338,1736],[341,1728],[349,1718],[354,1708],[363,1697],[367,1690],[372,1682],[376,1675]]
box=(328,1660,392,1764);scale=8
im=source.crop(box).resize(((box[2]-box[0])*scale,(box[3]-box[1])*scale),Image.Resampling.NEAREST)
im.save(out/'return-original.png');d=ImageDraw.Draw(im)
for i,(x,y) in enumerate(points):
 xx=(x-box[0]+.5)*scale;yy=(y-box[1]+.5)*scale
 d.ellipse((xx-3,yy-3,xx+3,yy+3),fill='cyan')
 d.text((xx+5,yy-12),str(i+1),fill='white',stroke_width=1,stroke_fill='black')
 if i%2==1:
  a,b=points[i-1];d.line(((a-box[0]+.5)*scale,(b-box[1]+.5)*scale,xx,yy),fill='cyan',width=1)
im.save(out/'return-cap-endpoints.png')
(out/'source-points.json').write_text(json.dumps({'coordinate_system':'original map top-left pixel coordinates','description':'Gap boundary endpoints on bright far-side cap edge; not presumed visible lower corners','uncertainty_pixels':2,'points':points},indent=2)+'\n')
before=Image.open(root/'inspection/complete-wall-candidate-v5/mesh-edge-audit/building-025-edges.png').convert('RGB')
after=Image.open(out/'mesh-edge-audit/building-025-edges.png').convert('RGB')
raw=Image.open(out/'mesh-edge-audit/building-025-source.png').convert('RGB')
sheet=Image.new('RGB',(raw.width*3,raw.height+28),'#202020');draw=ImageDraw.Draw(sheet)
for i,(name,image) in enumerate([('Original artwork',raw),('Previous geometry',before),('Corrected return',after)]):
 sheet.paste(image,(i*raw.width,28));draw.text((i*raw.width+8,8),name,fill='white')
sheet.save(out/'source-before-after.png')
(out/'review.md').write_text('''# Lower West wall walk — North return correction

This is a new geometry candidate, not yet approved or published. Only building-025
changed. The previous return trace mixed opposite cap sides and placed the last
opening over a visible merlon. The four return gaps now use separately inspected
cap endpoints. Crown height rose 2.5 world units (about two source pixels), and
the return cap is narrower. The front run and eight-opening total remain.

## Artwork and actual saved mesh

![Original, previous, corrected](source-before-after.png)

Red is the visible saved-mesh edge, cyan the picked artwork landmark. These are
source-camera views, not alternative perspectives. The annotations have about
two pixels of uncertainty. The old lower-corner return picks are withdrawn;
some blended shadow/masonry corners did not identify the same side of the cap.

![Unmodified return artwork](return-original.png)

![Numbered bright cap endpoints](return-cap-endpoints.png)

## Fresh 48-degree sunlight and authoritative reprojection

![Solid eight-view sheet](north-48/solid.png)

![Source-textured eight-view sheet](north-48/textured.png)

![Unmodified context](north-48/context.png)

The source camera remains35degrees. Gray surfaces have no source-visible
ownership and are not synthesized. Reprojection uses the frozen source-mask
reference, not the painted color as a visibility test.

## Checks and limitations

The changed wall is closed with positive signed volume, zero nonmanifold edges,
and zero degenerate faces. All503 other mesh geometries are unchanged. Ground
footprint stays fixed; the return masonry tapers toward the narrower crown.
The corrected openings are individually fitted; the cap thickness is inferred
from low-resolution bright edges. Blended lower shadow corners remain uncertain.
Nearest-visible-vertex diagnostics cannot establish semantic correspondences;
the actual red contours and numbered artwork landmarks are the review evidence.
No geometry from this candidate has been merged into the editor yet.
''')
