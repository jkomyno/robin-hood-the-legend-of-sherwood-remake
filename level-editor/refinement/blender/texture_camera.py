"""Frozen review camera extents for Blender's default AUTO sensor fit."""

import math


def depth_clip_range(depths):
    """Enclose displayed geometry without sacrificing orthographic depth precision."""
    depths = list(depths)
    if not depths or not all(math.isfinite(value) for value in depths):
        raise ValueError('Camera clipping requires finite geometry depths')
    nearest, farthest = min(depths), max(depths)
    if farthest <= .001:
        raise ValueError('Displayed geometry must extend in front of the camera')
    margin = max(1.0, (farthest - nearest) * .05)
    return max(.001, nearest - margin), farthest + margin


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
