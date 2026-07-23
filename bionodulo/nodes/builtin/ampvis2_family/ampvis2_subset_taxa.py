"""Focused registered node for ``ampvis2_subset_taxa``."""

from .filtering_adapter import Ampvis2SubsetTaxaNode as _NodeContract


class Ampvis2SubsetTaxaNode(_NodeContract):
    NODE_ID = "ampvis2_subset_taxa"
