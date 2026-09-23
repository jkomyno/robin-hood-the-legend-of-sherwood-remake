"""Pure pixel guards for generated planar atlas replacement."""
import numpy as np


def validate_fill(original, generated, mask, surface):
    if original.shape != generated.shape or original.shape[:2] != mask.shape[:2] or surface.shape != mask.shape[:2]:
        raise ValueError('Planar output must preserve exact atlas dimensions')
    editable = mask[:, :, 3] < 128
    if np.any(editable & ~surface):
        raise ValueError('Generation mask exposes outside or physical holes')
    if np.any(original[~editable] != generated[~editable]):
        raise ValueError('Generated atlas changed protected source or outside pixels')
    return int(editable.sum())
