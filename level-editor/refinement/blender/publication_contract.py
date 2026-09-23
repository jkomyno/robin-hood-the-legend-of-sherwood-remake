"""Map-independent catalog coverage and staged scene naming checks."""
import sys as _refinement_sys
from pathlib import Path as _RefinementPath
_refinement_legacy = str(_RefinementPath(__file__).resolve().parents[2] / 'blender')
if _refinement_legacy not in _refinement_sys.path:
    _refinement_sys.path.append(_refinement_legacy)

from pathlib import Path
from catalog_schema import source_for_part


def canonical_parts(catalog, map_name):
    if catalog['map'] != map_name:
        raise ValueError('Publication map and catalog differ')
    parts = [source_for_part(part) for group in catalog['groups']
             for part in group['parts']]
    if not parts or len(parts) != len(set(parts)):
        raise ValueError('Publication catalog has empty or duplicate part ownership')
    return set(parts)


def scene_filename(plan):
    name = plan.get('scene_filename', plan['map_name'].lower().replace(' ', '-') + '.scene.glb')
    if not isinstance(name, str) or Path(name).name != name or not name.endswith('.glb'):
        raise ValueError('Staged scene filename must be a local GLB filename')
    return name


def validate_coverage(actual, expected):
    if actual != expected:
        raise ValueError('Publication canonical coverage differs from catalog: ' +
                         repr({'missing': sorted(expected - actual, key=str),
                               'unexpected': sorted(actual - expected, key=str)}))
