"""Focused registered node for ``ampvis2_ordinate``."""

from .multivariate_adapter import Ampvis2OrdinateNode as _NodeContract


class Ampvis2OrdinateNode(_NodeContract):
    NODE_ID = "ampvis2_ordinate"
