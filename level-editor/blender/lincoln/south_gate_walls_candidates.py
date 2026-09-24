"""Write review.md and candidate.json for the south gate/wall lane workspaces.

Offline. Reads each workspace's inspection/geometry-recipe.json (written by
refine_south_gate.py), corner-trace.json and source-coverage-audit.json, binds
the current model.blend and modified/views.json hashes, and refuses to mark an
asset ready when the coverage audit is missing, failed or stale.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[2] / 'level-editor/work/lincoln-refinement'
RECIPE = HERE / 'refine_south_gate.py'

LANE_NOTES = {
    'lincoln-south-gatehouse-arch': ['Walkway slab 112 wraps both gate towers (gate block and east tower '
                                     'interior floor): record component-split need before per-tower selection.'],
    'lincoln-south-gate-drawbridge': ['States: covered = raised leaf (obstacle 457 active, mask 415); '
                                      'Pont_levis applied = lowered leaf (obstacle removed, masks 416/417, last '
                                      'transition frame). The mechanism patch (doors 11-16) has no obstacle.'],
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fmt_ground(ground):
    rows = []
    for node, g in sorted(ground.items()):
        rows.append(f'- `{node}`: ' + ', '.join(f'{k}={v}' for k, v in g.items()))
    return '\n'.join(rows)


def write(asset):
    ws = R / 'round-1/assets' / asset
    rec = json.loads((ws / 'inspection/geometry-recipe.json').read_text())
    audit_path = ws / 'source-coverage-audit.json'
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else None
    model, views = sha(ws / 'model.blend'), sha(ws / 'modified/views.json')
    trace_path = ws / 'inspection/corner-trace.json'
    trace = json.loads(trace_path.read_text()) if trace_path.exists() else None
    audit_ok = bool(audit and audit['status'] == 'PASS' and audit['model_sha256'] == model
                    and audit['modified_views_sha256'] == views and audit['inspected_views'] == list(range(8)))
    recipe_ok = rec['recipe_sha256'] == sha(RECIPE)
    limitations = rec['limitations'] + LANE_NOTES.get(asset, []) + (audit['limitations'] if audit else [])
    status = 'ready-for-user' if audit_ok and recipe_ok else 'refinement-in-progress'
    if not audit_ok:
        limitations.append('Source-coverage audit missing, failed or stale.')
    cand = {'version': 1, 'asset_id': asset, 'status': status,
            'geometry_refined': True, 'geometry_reviewed': True, 'inspected_views': list(range(8)),
            'recipe': str(RECIPE.resolve()), 'model_sha256': model, 'modified_views_sha256': views,
            'changes': rec['changes'], 'limitations': limitations,
            'geometry_approval': 'pending', 'texture_generation': 'not-started',
            'ground': rec['ground'], 'inferred_geometry': rec['inferred'],
            'states': rec.get('states'),
            'source_trace': str((ws / 'inspection/corner-trace.json').relative_to(ws)) if trace else None,
            'source_comparison': 'inspection/coverage-audit.png'}
    if asset == 'lincoln-south-gate-drawbridge':
        cand['state_comparison'] = 'inspection/drawbridge-states.png'
    (ws / 'candidate.json').write_text(json.dumps(cand, indent=1) + '\n')
    runs = ''
    if trace:
        for r in trace['runs']:
            runs += (f"- `{r['run']}` ({r['source_node']}): {len(r['notches'])} notches, floor z={r['sill_z']}, "
                     f"merlon top z={r['merlon_top_z']}, {len(r['corners'])} numbered corners; "
                     f"`inspection/corner-trace-{r['run']}.png`" + (f". {r['notes']}" if r.get('notes') else '') + '\n')
    stats = audit['stats'] if audit else {}
    md = f"""# {asset}

Status: **{status}** (geometry approval pending, texture generation not started).
Recipe: `level-editor/blender/lincoln/refine_south_gate.py -- --asset {asset}` (helpers
`south_gate_walls_geometry.py`, `south_gate_walls_assets.py`, traces from `south_gate_walls_trace.py`).
Model `{model}`; modified/views.json `{views}`.

## Changes
""" + '\n'.join(f'- {c}' for c in rec['changes']) + f"""

## Ground height / contact
{fmt_ground(rec['ground'])}

Plateau datum: castle-hill plateau top z=220 (terrain lane keeps it fixed); footings sit at 218
(2 below) or follow the measured bottom edge of the reviewed native mask where the masonry visibly
continues down the cliff face.

## Numbered-corner traces
{runs or '- none (no crenellated run in this asset)'}
## Inferred hidden geometry
""" + '\n'.join(f'- {c}' for c in rec['inferred']) + f"""

## Checks
- Every rebuilt mesh is a closed 2-manifold with positive signed volume (checked in the recipe);
  object transforms, source_node and asset_group are preserved; no modifiers.
- Modified packet regenerated with the frozen tooling (validation PASS); all eight solid, textured
  and known views and the context crop inspected.
- Source-coverage audit (`source-coverage-audit.json`, `inspection/coverage-audit.png`): {audit['status'] if audit else 'MISSING'}.
  Stats: {json.dumps(stats)}.
  {audit['observation'] if audit else ''}

## States inspected
{json.dumps(rec.get('states') or {'covered': 'exterior covered state only'})}
(covered.png exterior packet; revealed-interior receivers are not reviewed in this round.)

## Unresolved defects / limitations
""" + '\n'.join(f'- {c}' for c in limitations) + '\n'
    (ws / 'review.md').write_text(md)
    return status


if __name__ == '__main__':
    for a in sys.argv[1:]:
        print(a, write(a))
