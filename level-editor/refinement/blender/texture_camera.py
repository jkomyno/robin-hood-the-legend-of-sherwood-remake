"""Frozen review camera extents for Blender's default AUTO sensor fit."""


def orthographic_extents(view):
    """Return horizontal and vertical world spans, matching review rendering.

    Review cameras use square pixels and default AUTO sensor fit. Blender's
    ortho_scale covers the larger image dimension, not always its height.
    """
    crop = view['crop']
    width, height = crop['width'], crop['height']
    scale = view['ortho_scale']
    if width <= 0 or height <= 0 or scale <= 0:
        raise ValueError('Orthographic view requires positive dimensions and scale')
    largest = max(width, height)
    return scale * width / largest, scale * height / largest
