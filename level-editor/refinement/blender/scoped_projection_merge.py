"""Select only proved new generated samples within an explicit physical face."""
import numpy as np


def newly_generated_mask(physical, previous, projected):
    if physical.shape != previous.shape or previous.shape != projected.shape:
        raise ValueError('Projection atlas shapes differ')
    if physical.dtype != np.bool_:
        raise ValueError('Physical scope must be a boolean mask')
    if not np.isin(previous, [0, 1, 2, 3]).all() or not np.isin(projected, [0, 1, 2, 3]).all():
        raise ValueError('Unknown texture provenance class')
    return physical & (previous == 0) & (projected == 2)
