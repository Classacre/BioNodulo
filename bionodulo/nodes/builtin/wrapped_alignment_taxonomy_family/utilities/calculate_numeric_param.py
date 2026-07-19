"""Stable owner for ``calculate_numeric_param``."""

from .adapter import _CalculateNumericParamContract


class CalculateNumericParamNode(_CalculateNumericParamContract):
    NODE_ID = "calculate_numeric_param"
    UPSTREAM_SYMBOL = "CalculateNumericParamNode"
