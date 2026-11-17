"""LROC NAC CDR window -> calibrated I/F on the binned render grid, with ISIS special-pixel classes (protocol §3.1–3.2).

DN -> I/F = DN * scaling_factor + value_offset (label). Special constants from the label: NULL (missing), LRS/LIS (low
saturation), HRS/HIS (high saturation). Binning (Amendment A1): b x b blocks aligned to the cropped window's first line and the
image's first sample; a block is INVALID if any member is NULL/LRS/LIS, SATURATED if any member is HRS/HIS (and none
invalid); otherwise its I/F is the block mean.
"""
from __future__ import annotations

import numpy as np


def classify(dn, special):
    null = dn == special.get('missing_constant', -32768)
    low = (dn == special.get('low_instrument_saturation', -32766)) | (dn == special.get('low_representation_saturation', -32767))
    high = (dn == special.get('high_instrument_saturation', -32765)) | (dn == special.get('high_representation_saturation', -32764))
    vmin = special.get('valid_minimum', -32752)
    other = (dn < vmin) & ~(null | low | high)
    return null | low | other, high


def binned_iof(dn, label, b):
    """dn (lines, samples) int16 -> (iof, invalid, saturated) arrays of shape (lines // b, samples // b)."""
    nl, ns = (dn.shape[0] // b) * b, (dn.shape[1] // b) * b
    dn = dn[:nl, :ns]
    invalid, high = classify(dn, label['special'])
    iof = dn.astype(np.float64) * label['scaling_factor'] + label.get('value_offset', 0.0)
    iof[invalid | high] = np.nan

    def blocks(a, fn):
        return fn(a.reshape(nl // b, b, ns // b, b), axis=(1, 3))
    inv = blocks(invalid, np.any)
    sat = blocks(high, np.any) & ~inv
    with np.errstate(invalid='ignore'):
        mean = blocks(iof, np.nanmean) if b > 1 else iof
    mean[inv | sat] = np.nan
    return mean, inv, sat
