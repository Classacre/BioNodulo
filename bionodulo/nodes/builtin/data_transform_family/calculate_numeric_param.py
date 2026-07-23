"""Focused owner for ``calculate_numeric_param``."""

from bionodulo.nodes.builtin._alignment_taxonomy_utilities_adapter import _CalculateNumericParamContract


class CalculateNumericParamNode(_CalculateNumericParamContract):
    NODE_ID = "calculate_numeric_param"
    UPSTREAM_SYMBOL = "CalculateNumericParamNode"
