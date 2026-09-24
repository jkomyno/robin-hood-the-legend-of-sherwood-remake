"""Estimate local inferred-color gains from explicit observed pixel support."""
import numpy as np
from scipy.ndimage import gaussian_filter, distance_transform_edt


def reconcile_tile(generated, source, predicted, known, *, fade_pixels=24, gain_mode="rgb"):
    """Leave observed pixels exact; derive gains from the uncomposited prediction.

    Dark or unsupported samples carry no reliable multiplicative color evidence.
    In particular identical inputs must produce an identity transformation even
    when their observed channels are black.
    """
    if generated.shape != source.shape or predicted.shape != source.shape or known.shape != source.shape[:2]:
        raise ValueError('Reconciliation source, prediction, and ownership dimensions differ')
    if isinstance(fade_pixels, bool) or not isinstance(fade_pixels, (int, float)) or not np.isfinite(fade_pixels) or not 1 <= fade_pixels <= 1024:
        raise ValueError("Reconciliation fade must be finite and between 1 and 1024 pixels")
    if gain_mode not in ("rgb", "luminance"):
        raise ValueError("Reconciliation gain mode must be rgb or luminance")
    corrected = generated.copy()
    if not known.any():
        return corrected
    support = gaussian_filter(known.astype(float), 6)
    ratios = np.ones((*known.shape, 3))
    if gain_mode == "luminance":
        weights = np.array([.2126, .7152, .0722])
        source = np.repeat((source[:, :, :3] @ weights)[:, :, None], 3, axis=2)
        predicted = np.repeat((predicted[:, :, :3] @ weights)[:, :, None], 3, axis=2)
    for channel in range(3):
        observed = gaussian_filter(source[:, :, channel] * known, 6)
        estimate = gaussian_filter(predicted[:, :, channel] * known, 6)
        valid = (support > 1e-8) & (estimate > .015 * support)
        ratios[:, :, channel][valid] = np.clip(observed[valid] / estimate[valid], .4, 1.8)
    distance, nearest = distance_transform_edt(~known, return_indices=True)
    gains = 1 + (ratios[nearest[0], nearest[1]] - 1) * np.exp(-distance / fade_pixels)[:, :, None]
    corrected[~known, :3] = np.clip(corrected[~known, :3] * gains[~known], 0, 1)
    return corrected
