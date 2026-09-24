"""Reject generated background that intrudes into an approved silhouette."""
import numpy as np
from scipy.ndimage import binary_propagation


def support(image, approved_surface, maximum_rgb):
    """Keep dark interior details; reject only dark pixels connected to exterior.

    This is an explicit per-packet policy for sheets with a black background.
    It never changes image pixels, source ownership, or physical opacity.
    """
    if image.shape[:2] != approved_surface.shape or not 0 <= maximum_rgb <= .05:
        raise ValueError('Invalid generated background support contract')
    dark = np.max(image[:, :, :3], axis=2) <= maximum_rgb
    exterior = dark & ~approved_surface
    return ~binary_propagation(exterior, mask=dark)


def filtered_color(colors, weights, supported):
    weights = np.asarray(weights) * np.asarray(supported)
    total = weights.sum()
    return None if total <= 1e-8 else (np.asarray(colors) * weights[:, None]).sum(axis=0) / total
