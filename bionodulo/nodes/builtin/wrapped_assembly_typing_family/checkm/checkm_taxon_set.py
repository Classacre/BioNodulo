"""Stable owner for ``checkm_taxon_set``."""

from .adapter import _CheckMTaxonSetContract


class CheckMTaxonSetNode(_CheckMTaxonSetContract):
    NODE_ID = "checkm_taxon_set"
    UPSTREAM_SYMBOL = "CheckMTaxonSetNode"
