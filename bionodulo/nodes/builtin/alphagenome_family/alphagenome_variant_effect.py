"""Focused owner for ``alphagenome_variant_effect``."""

from .adapter import AlphaGenomeVariantEffectNode as _NodeContract


class AlphaGenomeVariantEffectNode(_NodeContract):
    NODE_ID = "alphagenome_variant_effect"
