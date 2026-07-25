"""Focused owner for ``preseq_c_curve``."""

from .adapter import PreseqCCurveNode as _NodeContract


class PreseqCCurveNode(_NodeContract):
    NODE_ID = "preseq_c_curve"
    UPSTREAM_SYMBOL = "PreseqCCurveNode"
