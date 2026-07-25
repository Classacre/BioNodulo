"""Focused registered node for ``ampvis2_venn``."""

from .multivariate_adapter import Ampvis2VennNode as _NodeContract


class Ampvis2VennNode(_NodeContract):
    NODE_ID = "ampvis2_venn"
