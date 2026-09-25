"""Exact physical-surface guard for explicitly scoped polygon tessellation.

Records retain oriented triangle corners, material ownership and non-atlas UVs.
This guard is necessary but not sufficient: new atlas source coverage is audited
separately before a texture candidate can be accepted.
"""
from collections import Counter


def frozen(value):
    if isinstance(value, dict):
        return tuple((key, frozen(value[key])) for key in sorted(value))
    if isinstance(value, (list, tuple)):
        return tuple(frozen(item) for item in value)
    return value


def triangle_key(triangle):
    corners = tuple(frozen(c) for c in triangle['corners'])
    if len(corners) != 3 or len(set(corners)) != 3:
        raise ValueError('Three distinct triangle corners required')
    # Cyclic rotation preserves winding; reversing it does not.
    return (frozen(triangle['material']), min(corners[i:] + corners[:i] for i in range(3)))


def verify_equivalence(before, after, scopes):
    """Verify snapshots keyed by object and original polygon identity.

    Each polygon record contains ``triangles`` and ``polygon``. Target polygon
    topology may differ, but its exact oriented triangle multiset may not.
    ``invariants`` binds vertex coordinates, transforms, non-atlas UV names,
    source image hashes and object settings. Every unscoped record is exact.
    """
    if not scopes or set(before) != set(after) or set(scopes) - set(before):
        raise ValueError('Explicit valid object scope and identical object inventory required')
    counts = {}
    for name, old in before.items():
        new = after[name]
        if name not in scopes:
            if old != new:
                raise ValueError(f'Unscoped object changed: {name}')
            continue
        ids = scopes[name]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError('Nonempty unique polygon scope required')
        if old['invariants'] != new['invariants']:
            raise ValueError(f'Object invariants changed: {name}')
        if set(old['polygons']) != set(new['polygons']) or set(ids) - set(old['polygons']):
            raise ValueError('Original polygon identity mapping changed')
        for face, polygon in old['polygons'].items():
            replacement = new['polygons'][face]
            if face not in ids:
                if polygon != replacement:
                    raise ValueError(f'Unscoped polygon changed: {name}/{face}')
            elif Counter(map(triangle_key, polygon['triangles'])) != Counter(map(triangle_key, replacement['triangles'])):
                raise ValueError(f'Physical triangle/material/non-atlas UV mismatch: {name}/{face}')
        counts[name] = sum(len(old['polygons'][face]['triangles']) for face in ids)
    return {'status': 'PASS', 'scoped_oriented_triangles': counts,
            'source_coverage_status': 'SEPARATE_PROOF_REQUIRED'}
