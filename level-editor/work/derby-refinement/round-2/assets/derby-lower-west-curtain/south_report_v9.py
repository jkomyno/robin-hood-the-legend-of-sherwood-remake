"""Assemble actual source-camera panels only after all renders exist."""
import json,re
from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent;out=root/'inspection/south-cap-fit-v9'
for node in ('023','042'):
    p=out/f'source-camera-{node}'
    solid=Image.open(p/'views/view-0-solid.png').convert('RGB')
    source=Image.open(p/'context.png').convert('RGB').resize(solid.size,Image.Resampling.NEAREST)
    textured=Image.open(p/'views/view-0-textured.png').convert('RGB')
    canvas=Image.new('RGB',(solid.width*3,solid.height+28),'black');draw=ImageDraw.Draw(canvas)
    for i,(label,im) in enumerate(zip(['Original source (nearest enlargement)','Solid, original camera, 48 degree sun','Source-only projection'],[source,solid,textured])):
        canvas.paste(im,(i*solid.width,28));draw.text((i*solid.width+5,6),label,fill='white')
    canvas.save(out/f'building-{node}-source-solid-textured.png')
text='''# Lower West south wall walk — cap and notch revision v9

The rejected v7 trace missed an opening in the long run and used several points
inside cap tops as if they were corners. Its excellent fitting residuals did
not establish correct geometry. This revision retraces the near cap edge, far
cap edge and visible notch-floor evidence separately.

Node 023 now contains **seven source-visible openings** in the inspected run,
including the previously missed opening around source y1886–1895. Node 042
retains six openings, with corrected near/far cap alignment and thickness.
Crowns are horizontal at a common world height; no sloped cap heights were
introduced to fit pixels. The wall remains complete down to ground.

## Original camera: long run and bend

These are the exact original camera/crop, not an alternative viewing angle.
Left is original artwork enlarged with nearest-neighbor sampling; middle is
gray geometry with the selected 48° sun; right is fresh source-only projection.

![Long-run source, solid and projected geometry](building-023-source-solid-textured.png)

![Original source with rejected and new saved-mesh edges](building-023-comparison.png)

![Near/far cap and floor observations](building-023-observations.png)

## Original camera: south end

![South-end source, solid and projected geometry](building-042-source-solid-textured.png)

![Original source with rejected and new saved-mesh edges](building-042-comparison.png)

![Near/far cap and floor observations](building-042-observations.png)

In the observation images yellow marks the near crown and its vertical line;
cyan marks the far crown; red marks the floor constraint. The right-side floor
corner is often hidden behind the neighboring merlon. Those floor positions
are constrained by a common depth, not independently visible observations.
The source picks have approximately 2 px uncertainty, more at the grazing bend.

## Eight views

![Solid geometry](modified/solid.png)

![Fresh source-only projection](modified/textured.png)

![Unmodified surrounding artwork](modified/context.png)

## Checks and limits

Only nodes 023 and 042 are changed. Five hundred outside meshes are unchanged;
the north section and approved stair/turret/support geometry are preserved.
Both changed walls are closed with positive volume, no nonmanifold edges and
no degenerate faces. Full wall ground footprints are retained.

Two support loops confine the plan correction: below height 190 the wall body
is retained; a narrow transition from 190 to 196 joins it to the corrected
vertical parapet faces. This transition is inferred structural geometry,
not a recovered architectural detail. The cap thickness is traced from both
source edges. Concealed repeats beneath the roof remain inferred.

`source-correspondences.json` records the near/far/floor constraints;
`geometry.json` records counts and topology. `lower-wall-validation.json`
compares closed volumes below height 189 with v5: differences are below
0.0006%, within the tolerance of remeshing the same lower surface.
Red overlays read edges from the
saved meshes with self-visibility tests; neighboring roofs are not occluders
in this edge diagnostic. Gray surfaces in source-projected renders indicate
unavailable or rejected source evidence.

Review candidate only. No AI texture generation or editor publication.
'''
(out/'review.md').write_text(text)
for ref in re.findall(r'!\[[^]]*\]\(([^)]+)\)',text):assert (out/ref).is_file(),ref
print(out/'review.md')
