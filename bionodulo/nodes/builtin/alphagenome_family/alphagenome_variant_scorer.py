"""Focused owner for ``alphagenome_variant_scorer``."""

from .adapter import AlphaGenomeVariantScorerNode as _NodeContract


class AlphaGenomeVariantScorerNode(_NodeContract):
    NODE_ID = "alphagenome_variant_scorer"
