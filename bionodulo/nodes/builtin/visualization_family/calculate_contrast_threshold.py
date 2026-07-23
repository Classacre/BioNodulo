"""Focused owner for ``calculate_contrast_threshold``."""

from bionodulo.nodes.builtin._alignment_taxonomy_utilities_adapter import _CalculateContrastThresholdContract


class CalculateContrastThresholdNode(_CalculateContrastThresholdContract):
    NODE_ID = "calculate_contrast_threshold"
    UPSTREAM_SYMBOL = "CalculateContrastThresholdNode"
