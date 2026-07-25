"""Focused registered node for ``ampvis2_boxplot``."""

from .abundance_adapter import Ampvis2BoxplotNode as _NodeContract


class Ampvis2BoxplotNode(_NodeContract):
    NODE_ID = "ampvis2_boxplot"
