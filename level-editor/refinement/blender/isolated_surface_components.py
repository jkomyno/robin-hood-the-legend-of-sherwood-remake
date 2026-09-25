"""Select exact hash-bound small surface holes from original same-face donors."""
import hashlib
import numpy as np
from scipy.ndimage import label, distance_transform_edt


def select(ownership, physical, positions, target_xy, origin, spec):
    from course_patch_guards import coordinates
    if ownership.shape != physical.shape or positions.shape != (*physical.shape, 3) or physical.dtype != bool or not np.isfinite(positions).all():
        raise ValueError('Invalid physical receiver domain')
    for key, cap in [('max_texels', 150), ('max_fraction', .08), ('max_distance_texels', 4.5), ('max_distance_world', 2.25)]:
        if not np.isfinite(spec[key]) or not 0 < spec[key] <= cap:
            raise ValueError('Unsafe measured component limit: '+key)
    target, _ = coordinates(target_xy, target_xy, (ownership.shape[0]+origin[1], ownership.shape[1]+origin[0]))
    if hashlib.sha256(target.astype('<i4').tobytes()).hexdigest() != spec['target_xy_sha256']:
        raise ValueError('Target coordinate hash drift')
    local = target - origin
    x, y = local.T
    if (local < 0).any() or (local >= ownership.shape[::-1]).any():
        raise ValueError('Target outside physical receiver')
    if not physical[y,x].all() or not (ownership[y,x] == 0).all():
        raise ValueError('Target is not unfilled physical surface')
    labels,_ = label(physical & (ownership == 0))
    touched = np.unique(labels[y,x])
    exact = np.zeros(physical.shape, bool); exact[y,x] = True
    if not np.array_equal(np.isin(labels,touched[touched != 0]), exact):
        raise ValueError('Targets must cover exact whole measured components')
    if len(target) > spec['max_texels'] or len(target) > physical.sum()*spec['max_fraction']:
        raise ValueError('Measured component budget exceeded')
    donors = physical & (ownership == 2)
    if not donors.any(): raise ValueError('No original generated same-face donors')
    distances,nearest = distance_transform_edt(~donors,return_indices=True)
    sy,sx = nearest[:,y,x]
    world = np.linalg.norm(positions[sy,sx]-positions[y,x],axis=1)
    if distances[y,x].max() > spec['max_distance_texels'] or world.max() > spec['max_distance_world']:
        raise ValueError('Measured donor distance exceeded')
    return np.c_[sx+origin[0],sy+origin[1]].astype('<i4'), dict(max_distance_texels=float(distances[y,x].max()),max_distance_world=float(world.max()))
