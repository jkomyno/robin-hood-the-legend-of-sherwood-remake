"""Self-contained review of full-height south walls and all full-run openings."""
import json,re
from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent;out=root/'inspection/south-vertical-v13'
geometry=json.loads((out/'geometry.json').read_text())
checks=json.loads((out/'vertical-wall-validation.json').read_text())
assert all(not r['ground_crossings'] and not r['sloped_full_height_faces'] for r in checks)
for node in ('023','042'):
    p=out/f'source-camera-{node}';solid=Image.open(p/'views/view-0-solid.png').convert('RGB')
    source=Image.open(p/'context.png').convert('RGB').resize(solid.size,Image.Resampling.NEAREST)
    textured=Image.open(p/'views/view-0-textured.png').convert('RGB')
    canvas=Image.new('RGB',(solid.width*3,solid.height+28),'black');draw=ImageDraw.Draw(canvas)
    for i,(label,im) in enumerate(zip(['Original source','Solid original camera, 48 degree sun','Source-only projection'],[source,solid,textured])):
        canvas.paste(im,(i*solid.width,28));draw.text((i*solid.width+5,6),label,fill='white')
    canvas.save(out/f'building-{node}-source-solid-textured.png')
rows='\n'.join(f"|{w['node']}|{w['opening_count_full']}|{w['rail_fit']['max_source_pixel_shift']:.2f}|{w['max_xy_displacement']:.2f}|" for w in geometry['walls'])
text='''# Lower West south wall walk — full-height revision v13

The artificial ledge and diagonal transition faces are removed. The corrected
cap plan now extends vertically through the entire masonry wall to the ground.
This explicitly changes the two wall footprints; preserving the incompatible
old footprints had caused the previous ledge.

The rejected v12 recipe only cut the sampled visible runs and three continuation
notches. It stopped at source Y=2028 and omitted the entire incoming 042 edge.
That left the false long solid parapet. This revision replaces the partial
continuation with six regularly spaced openings through the 023 approach and
adds three openings on 042's incoming bend, including a cut spanning its turn.
Both full wall runs are now included in the images below, not just the sampled
visible sections. The underlying turret and adjacent building stay unchanged.

The terminal straight spur on 042 is now a short curved return, following the
visible source shape and retaining the end contacts with the approved southwest
postern. Its detailed curvature is reconstructed, not uniquely measured from
the low-resolution artwork. No postern mesh or other outside asset is changed.

## Original-camera source, solid and projected result

![Long run and bend](building-023-source-solid-textured.png)

![South end and curved return](building-042-source-solid-textured.png)

## Actual saved mesh edges on the artwork

These overlays are read from the saved mesh and self-visibility tested in the
original 35° camera. Red means actual cap, shoulder and floor edges. No fitted
landmark points are substituted for mesh edges. Neighboring roofs are excluded
from this edge-only visibility test.

![Long-run actual mesh](building-023-actual-overlay.png)

![South-end actual mesh](building-042-actual-overlay.png)

## Every opening, across the complete runs

[Inspect all 26 openings: original pixels, stations, actual mesh](opening-audit.md).
023 has 7 previously traced openings, 6 continuation openings and 4 retained
turret-end openings. 042 has 6 diagonal-run openings and 3 incoming-bend openings.
The split Boolean cuts across the turn count as one opening.

![All 17 openings on 023](building-023-numbered-openings.png)

![All 9 openings on 042](building-042-numbered-openings.png)

The numbered stations behind the turret roof are continuation estimates:
their hidden corners cannot be directly picked from this covered image.
They are nevertheless modeled continuously, with the visible neighboring
rhythm. The audit labels these separately from the visible traced openings.

The near and far cap observations are regularized onto parallel wall planes.
This avoids turning tiny annotation errors into fluted full-height walls.
Opening stations/counts are preserved. Floors hidden behind the neighboring
merlon use the visible floor depth as a constraint. Source picks themselves
remain uncertain by about 2 pixels, especially on the grazing 023 run.

|Wall|Full-run openings|Maximum cap-rail adjustment (source pixels)|Maximum plan displacement (world units)|
|---|---:|---:|---:|
''' + rows + '''

## Eight views

![Solid](modified/solid.png)

![Fresh source-only projection](modified/textured.png)

![Original context](modified/context.png)

## Verification

Both walls are closed, with positive volume, no nonmanifold edges and no
degenerate faces. The ground outlines have no proper crossings. No full-height
side face slopes vertically. Five hundred outside meshes, including the north
wall, approved stair and turret/support parts, are unchanged.
Independent connected-component counting of horizontal notch floors in the
saved mesh confirms 17 openings on 023 and 9 on 042, rather than merely counting
the input recipe. All 26 have numbered image evidence.

`geometry.json` records topology, source constraints, plan displacement and
the explicit footprint change. `vertical-wall-validation.json` checks the
saved ground outlines and full-height face normals. Source projection was
reapplied; the eight-view and source-camera sheets use 48° sun elevation.

No AI generation or editor publication has been performed. Geometry approval
is still required. Concealed repeats and the fine terminal curvature remain
inferred; these images do not claim pixel-perfect recovery.
'''
(out/'review.md').write_text(text)
for ref in re.findall(r'!\[[^]]*\]\(([^)]+)\)',text):assert (out/ref).is_file(),ref
assert len(list((out/'openings').glob('*.png')))==26
print(out/'review.md')
