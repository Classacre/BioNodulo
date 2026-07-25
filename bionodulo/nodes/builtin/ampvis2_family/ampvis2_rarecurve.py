"""Focused registered node for ``ampvis2_rarecurve``."""

from .diversity_adapter import Ampvis2RarecurveNode as _NodeContract


class Ampvis2RarecurveNode(_NodeContract):
    NODE_ID = "ampvis2_rarecurve"
