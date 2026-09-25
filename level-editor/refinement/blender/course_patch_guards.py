"""Fail-closed geometry and index checks for explicit rigid atlas patches."""
import numpy as np


def coordinates(target, donor, shape):
    """Return integer xy arrays; repeated donor samples are raster aliasing."""
    values = []
    height, width = shape
    for name, raw in [('target', target), ('donor', donor)]:
        a = np.asarray(raw)
        if a.ndim != 2 or a.shape[1] != 2 or len(a) == 0:
            raise ValueError(name + ' coordinates must be nonempty xy pairs')
        if not np.isfinite(a).all() or not np.equal(a, np.floor(a)).all():
            raise ValueError(name + ' coordinates must be finite integers')
        if (a < 0).any() or (a >= [width, height]).any():
            raise ValueError(name + ' coordinates outside atlas')
        values.append(a.astype('<i4'))
    if len(values[0]) != len(values[1]):
        raise ValueError('Target and donor counts differ')
    if len(np.unique(values[0], axis=0)) != len(values[0]):
        raise ValueError('Duplicate target coordinates')
    return values


def coplanar_measurements(vertices):
    normals = []
    for raw in vertices:
        v = np.asarray(raw, dtype=np.float64)
        if v.ndim != 2 or v.shape[1] != 3 or len(v) < 3 or not np.isfinite(v).all():
            raise ValueError('Invalid face vertices')
        n = np.cross(v[1] - v[0], v[2] - v[0])
        length = np.linalg.norm(n)
        if not np.isfinite(length) or length <= 1e-12:
            raise ValueError('Degenerate face plane')
        normals.append(n / length)
    normal_delta = float(np.linalg.norm(normals[0] - normals[1]))
    offset = float(np.max(np.abs((vertices[1] - vertices[0][0]) @ normals[0])))
    return normal_delta, offset
