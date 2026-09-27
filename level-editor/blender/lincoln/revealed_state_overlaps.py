"""Count same-facing coplanar overlaps among the objects a state shows (Blender).

    blender --background <blend> --python revealed_state_overlaps.py -- <out.json> <assets,comma> <patch,...> [...]

Each patch set (comma-separated patches; '-' for covered) selects visibility exactly like the
editor's PatchDisplay. Every pair of shown meshes of the listed assets is checked for triangle
pairs facing the same way, closer than 0.3 units and overlapping by more than 1 unit^2.
Downward-facing undersides are skipped: no editor view looks up at them.
"""
import json
from pathlib import Path
import sys
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
import revealed_state_geometry as RG


def shown(obj, applied):
    if set(obj.get('reveal_hide_when_applied', [])) & applied:
        return False
    show = obj.get('reveal_show_when_applied')
    return bool(set(show) & applied) if show is not None else True


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    out, assets, states = Path(args[0]), set(args[1].split(',')), args[2:]
    report = {'assets': sorted(assets), 'blend': bpy.data.filepath, 'states': {}}
    for state in states:
        applied = set() if state == '-' else set(state.split(','))
        objects = [o for o in bpy.data.objects if o.type == 'MESH' and o.get('asset_group') in assets
                   and not o.get('state_context_recipe') and shown(o, applied)]
        pairs = []
        for i, a in enumerate(objects):
            for b in objects[i + 1:]:
                found = RG.coplanar_pairs(a, b, visible_only=True) + RG.coplanar_pairs(b, a, visible_only=True)
                if found:
                    pairs.append({'a': a.name, 'b': b.name, 'triangle_pairs': len(found),
                                  'area': round(sum(x[2] for x in found), 1)})
        report['states'][state] = {'objects': len(objects), 'overlapping_pairs': len(pairs), 'pairs': pairs}
        print('OVERLAPS', state, len(objects), len(pairs), flush=True)
    out.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
