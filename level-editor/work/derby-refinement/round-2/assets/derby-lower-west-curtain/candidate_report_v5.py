"""Build a self-contained report from completed Lower West review artifacts."""
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent
out = root / 'inspection/complete-wall-candidate-v5'
shutil.copytree(root / 'inspection/complete-wall-candidate/corners', out / 'corners', dirs_exist_ok=True)
geometry = json.loads((out / 'geometry.json').read_text())
preservation = json.loads((out / 'preservation-validation.json').read_text())
assert preservation['protected_geometry_unchanged'] and preservation['wall_bottom_footprints_unchanged']
for side in ('north', 'south'):
    for name in ('solid.png', 'textured.png', 'context.png', 'views.json'):
        assert (out / f'{side}-48' / name).is_file(), (side, name)
    views = json.loads((out / f'{side}-48/views.json').read_text())
    assert abs(views['lighting']['toward_sun'][2] - .7431448255) < 1e-6
audit = json.loads((out / 'mesh-edge-audit/edge-residuals.json').read_text())
rows = '\n'.join(f"| {r['node']} | {r['rms_nearest_vertex']:.2f} |" for r in audit['reports'])
text = '''# Lower West wall walks — revised geometry for inspection

Both complete wall bodies remain present. The rejected detached-box version is
not used. Source projection has been reapplied, and these new eight-view sheets
use the selected 48° sun elevation and the unchanged 35° source camera.

North has eight notch cuts. South has six end-run notches and a revised long run:
the visible openings now use individually picked source-corner coordinates;
two overlapping cutters make a continuous opening across the bend. The number
of Boolean operations is not the number of openings. Opening depth was reduced
from 26 to 23.5 world units to better match the observed shoulders.

All three wall meshes have positive volume, no nonmanifold edges and no
degenerate faces. The ground footprints and approved stair/turret/support
geometry match the earlier complete-wall model exactly. See `geometry.json`
and `preservation-validation.json` for checks. This is not published to the editor.

## North — solid and source-projected views

![North solid](north-48/solid.png)

![North source projection](north-48/textured.png)

![North unmodified context](north-48/context.png)

## South — solid and source-projected views

![South solid](south-48/solid.png)

![South source projection](south-48/textured.png)

![South unmodified context](south-48/context.png)

## Remaining alignment uncertainty

These are review candidates, not a claim of pixel-perfect recovery. Source
corner picks have approximately 2–3 pixel uncertainty. The grazing long-run
bend and north return still show mismatches. Concealed openings beneath the
roof remain inferred. Review the red mesh edges against the untouched artwork;
do not treat the statistics alone as a pass.

The edge check reads actual saved mesh vertices and performs self-visibility
tests. Cyan marks the observed source corners; red shows visible mesh edges;
yellow joins each observation to its nearest visible mesh vertex. The nearest
vertex is not always the corresponding semantic corner, particularly when a
far-side crown edge is hidden by the near side. Neighboring roofs are excluded
from this wall-only visibility check. These residuals cannot certify the whole
wall or replace visual inspection.

| Wall | Nearest-visible-vertex RMS (source pixels) |
| --- | ---: |
''' + rows + '''

### North025

![Original artwork](mesh-edge-audit/building-025-source.png)

![Actual mesh edge overlay](mesh-edge-audit/building-025-edges.png)

![Numbered front corners](corners/north-025-four-gaps-front-run.png)

![Numbered return corners](corners/north-025-return-four-gaps.png)

### South023, long run and bend

![Original artwork](mesh-edge-audit/building-023-source.png)

![Actual mesh edge overlay](mesh-edge-audit/building-023-edges.png)

![Numbered source corners](corners/south-023-visible-long-run.png)

### South042, end run

![Original artwork](mesh-edge-audit/building-042-source.png)

![Actual mesh edge overlay](mesh-edge-audit/building-042-edges.png)

![Numbered source corners](corners/south-042-six-gaps.png)
'''
(out / 'review.md').write_text(text)
print(out / 'review.md')
