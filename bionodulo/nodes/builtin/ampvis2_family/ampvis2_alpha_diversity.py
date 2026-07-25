"""Focused registered node for ``ampvis2_alpha_diversity``."""

from .diversity_adapter import Ampvis2AlphaDiversityNode as _NodeContract


class Ampvis2AlphaDiversityNode(_NodeContract):
    NODE_ID = "ampvis2_alpha_diversity"
