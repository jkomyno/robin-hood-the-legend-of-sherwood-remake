from pathlib import Path
root=Path(__file__).resolve().parent
code=(root/'report_north_v10.py').read_text().replace('north-corner-v10','north-corner-v14').replace('[322,1550,392,1664]','[322,1550,404,1664]')
exec(compile(code.split("(out/'review.md').write_text")[0],str(root/'report_north_v10.py'),'exec'))
out=root/'inspection/north-corner-v14'
(out/'review.md').write_text('''# North wall walk — source profile and full-wall rebuild

This replaces the rejected v10 construction. It is a new audit candidate,
not an approved or integrated asset.

Three failures were found in v10. Some return-cap annotations were several pixels
away from the real bright cap edge; opening 3 was particularly wrong. Front-arm
cap and floor coordinates drifted progressively downwards, by up to eleven pixels,
and a fifth opening near the bend was missed. Also,
retaining the old lower-wall footprint while changing its crown forced diagonal
transition wedges into the model. The actual mesh overlay exposed both problems.

The return landmarks were re-picked from individual source crops with external
pixel-coordinate axes. The entire wall now follows the same vertical planes as
its upper profile, so there is no intermediate ledge or wedge. Each merlon cap
is fitted as one plane, allowing its own slope; each notch floor follows its
two endpoint observations. No universal crown elevation or notch depth is forced.
There are now five front openings and five return openings.

## Original artwork, actual solid, and freshly projected texture

![Front comparison](front-source-solid-textured.png)

![Return comparison](return-source-solid-textured.png)

These use identical source-camera crops. The first column is unchanged artwork.
Solid lighting uses the selected 48-degree sun; camera elevation remains 35 degrees.

## Actual saved mesh projected onto original artwork

![Front mesh edges](front-mesh-on-artwork.png)

![Return mesh edges](return-mesh-on-artwork.png)

Thin red lines are sharp edges from the actual saved mesh, visibility-tested
against that mesh, not target landmarks. Neighbor geometry is not used as an
occluder in this wall-only edge audit. Model/source hashes and projected segments
are in `mesh-on-artwork.json`.

## Individual openings: raw art, source observations, actual mesh

The following crops distinguish the recorded source observations from the actual
geometry. Near caps are cyan, far caps magenta, notch-floor endpoints yellow.
Dark notch-floor boundaries are less clear than the bright caps; their source
pixel selection retains approximately two pixels of uncertainty. These should
be judged from the raw pixels, not a residual score.

'''+ '\n\n'.join(f'![{side} opening {i}]({side}-opening-{i}.png)' for side,count in [('front',5),('return',5)] for i in range(1,count+1))+'''

## Whole model from eight directions

![Solid](north-48/solid.png)

![Source-only textured](north-48/textured.png)

## Geometry changes and verification

The complete wall still reaches the ground and is closed, with positive volume,
zero nonmanifold edges and no degenerate faces. All 503 other meshes are untouched.
The corrected vertical planes intentionally change the wall's footprint and
thickness; the exact signed volume is recorded in `geometry.json`.
This is a narrower full wall, not replacement by detached merlon boxes. Compare
the whole solid views as well as the source profiles before accepting the change.

Reprojection was rerun with the frozen authoritative masks. Unknown surfaces
remain gray; no synthesized texture or source-image retouching is included.
No editor assets or gallery entries were modified by this worker.
''')
