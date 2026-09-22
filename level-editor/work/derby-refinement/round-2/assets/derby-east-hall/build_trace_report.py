from pathlib import Path
import json,shutil,math
W=Path(__file__).parent;D=W/'next-zigzag-v3';images=D/'images';images.mkdir(exist_ok=True)
obs=json.loads((D/'source-corners.json').read_text())
residuals=json.loads((D/'candidate-residuals.json').read_text())
validation=json.loads((D/'candidate-validation.json').read_text())
for file in D.glob('*-source-corners.png'):shutil.copyfile(file,images/file.name)
for file in D.glob('*-residuals.png'):shutil.copyfile(file,images/file.name)
for file in D.glob('*-actual-edges.png'):shutil.copyfile(file,images/file.name)
shutil.copyfile(W/'asset-reference/source-context.png',images/'original-context.png')
for name,folder in [('before',D/'before-48'),('after',D/'recovery-review/modified')]:
    for mode in ['solid','textured']:shutil.copyfile(folder/(mode+'.png'),images/(name+'-'+mode+'.png'))
lines=['# East Hall: source-traced parapet revision',
 '','Status: **source-alignment review; topology repair still required before approval or publication.**',
 '', 'The cumulative casement/facade checkpoint is the baseline. Only eight visible parapet meshes were edited. '
 'The rejected historical one-notch rebuild must not be used; it regressed lower facade work.',
 '', '![Unmodified source context](images/original-context.png)',
 '', '## What changed',
 '', '- Foreground west/south run: eight observed notches, including four missing from the earlier modeled run. '
 'The east-facing run retains five notches but corrects their phase, widths and depth.',
 '- Foreground cap thickness comes from measured four-corner cap polygons: west inward image displacement (+7,-5), '
 'east (-4,-3). A source shoulder crossing the old mesh boundary at x=1337 is modeled explicitly.',
 '- Rear run: seven directly observed caps plus two explicitly inferred continuation caps hidden by the dormer/chimney. '
 'The far end behind the round turret is retained. Inferred coordinates are excluded from the observed-corner JSON.',
 '- Stair turret: outer notch shoulders and floors adjusted to the native silhouette. The inner stair-facing gap floor remains inherited; '
 'its internal edge has not been traced confidently.',
 '', '## Source coordinates and residuals',
 '', f"The observation file contains {sum(len(r['points']) for r in obs['runs'])} listed pixel points, including closed-cap polygon endpoints. "
 'Coordinates use the original 1920×2752 artwork. Native silhouette observations carry ±1px uncertainty; hand-traced internal edges ±2px.',
 '', '[Exact source corners](source-corners.json) · [Measured residuals](candidate-residuals.json)',
 '', 'Numbered cyan points are source observations. In residual images, red squares are model locations and yellow lines show errors. '
 'Rear/stair residuals use the actual source-camera rendered upper silhouette. Foreground residuals use nearest projected upper mesh edges '
 'and are **not visibility filtered**. Zero means the selected coordinates were fitted; it does not independently validate the annotations.',
 '', '| Run | Mean error (px) | Maximum (px) |', '|---|---:|---:|']
for r in residuals:lines.append(f"| {r['id']} | {r['mean_px']:.2f} | {r['max_px']:.2f} |")
for run in obs['runs']:
    ident=run['id'];lines += ['',f'### {ident}', '',run['evidence'],
       '',f'![Numbered original pixels: {ident}](images/{ident}-source-corners.png)',
       '',f'![Measured errors: {ident}](images/{ident}-residuals.png)']
lines += ['', '## Actual saved-mesh contours', '', 'Cyan lines are projected edges from the saved mesh, including hidden edges; these are wireframes, not silhouette-only contours.']
for ident in ['front-west','front-south','front-east','rear','stair-turret']:
    lines += ['',f'### {ident}', '',f'![Before {ident}](images/{ident}-before-actual-edges.png)',
              '',f'![After {ident}](images/{ident}-after-actual-edges.png)']
lines += ['', '## Eight views — identical framing and 48° sunlight',
 '', 'Before solid:', '', '![Before solid](images/before-solid.png)',
 '', 'After solid:', '', '![After solid](images/after-solid.png)',
 '', 'Before source texture:', '', '![Before textured](images/before-textured.png)',
 '', 'After source texture:', '', '![After textured](images/after-textured.png)',
 '', '## Validation and remaining limits',
 '', f"- {validation['protected_mesh_count']} protected meshes are unchanged, including hidden historical originals and interior receivers.",
 f"- Lower geometry below z=365 is preserved: maximum float serialization displacement {max(validation['lower_max_displacement'].values()):.7f} world units; no missing lower vertices.",
 '- Zero degenerate faces on the edited meshes. The new foreground seam correction restores the east corner to zero boundary edges and reduces the southwest wall from 61 to one boundary edge, but six nonmanifold edges remain there. Rear-wall boundaries increased from 37 to 127. These are explicit topology blockers, not a watertight-mesh certification.',
 '- Projection was rerun using the accepted casement source assignments plus the reviewed native Hall mask146 envelope on previously unconstrained receivers 192, 194 and 198. '
 'The immutable native-mask checkpoint was initialized from the accepted review hashes, not from modified masks.',
 '- Largest remaining silhouette error is 5.83px at the stair-turret/roof junction. The first stair cap transition has a 3.16px residual. '
 'The roof junction and concealed inner stair-floor edge are not declared solved.',
 '- Interior geometry was not altered. The existing revealed image is a receiver-only diagnostic, not a full gameplay reveal state; its large gray upper walls are unsupported source regions. '
 'No new interior geometry correction is claimed.',
 '', 'Reprojected candidate: [recovery-review/model.blend](recovery-review/model.blend). '
 'Coordinator must inspect the numbered overlays and the remaining limitations before this returns to the approval gallery.']
(D/'review.md').write_text('\n'.join(lines)+'\n')
for target in images.iterdir():assert target.stat().st_size>0,target
print(D/'review.md')
