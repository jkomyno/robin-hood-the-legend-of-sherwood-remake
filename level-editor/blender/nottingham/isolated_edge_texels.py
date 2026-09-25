"""Select explicitly measured isolated missing texels without crossing face authority."""
import numpy as np
from scipy.ndimage import label


def donor(ownership, physical, positions, target, *, max_texels, max_world, expected_component=None):
    y, x = target
    if not physical[y, x] or ownership[y, x] != 0:
        raise ValueError('Target must be an unfilled physical face texel')
    components, _ = label(physical & (ownership == 0))
    component = components[y, x]
    actual_component = {tuple(p) for p in np.argwhere(components == component)}
    expected = {tuple(target)} if expected_component is None else set(map(tuple, expected_component))
    if actual_component != expected:
        raise ValueError('Physical missing component differs from exact approved coordinates')
    candidates = np.argwhere(physical & (ownership == 2))
    if not len(candidates):
        raise ValueError('No original generated physical-face donor')
    distances = np.linalg.norm(candidates - [y, x], axis=1)
    world = np.linalg.norm(positions[candidates[:, 0], candidates[:, 1]] - positions[y, x], axis=1)
    allowed = (distances <= max_texels) & (world <= max_world)
    if not allowed.any():
        raise ValueError('No donor satisfies both measured distance bounds')
    choices = np.flatnonzero(allowed)
    selected = min(choices, key=lambda i: (distances[i], world[i], *candidates[i]))
    return tuple(candidates[selected]), float(distances[selected]), float(world[selected])
