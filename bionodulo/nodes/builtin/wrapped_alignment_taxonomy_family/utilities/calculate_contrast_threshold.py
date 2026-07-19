"""Stable owner for ``calculate_contrast_threshold``."""

from .adapter import _CalculateContrastThresholdContract


class CalculateContrastThresholdNode(_CalculateContrastThresholdContract):
    NODE_ID = "calculate_contrast_threshold"
    UPSTREAM_SYMBOL = "CalculateContrastThresholdNode"
