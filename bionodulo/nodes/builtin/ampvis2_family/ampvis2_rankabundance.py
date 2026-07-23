"""Focused registered node for ``ampvis2_rankabundance``."""

from .diversity_adapter import Ampvis2RankAbundanceNode as _NodeContract


class Ampvis2RankAbundanceNode(_NodeContract):
    NODE_ID = "ampvis2_rankabundance"
