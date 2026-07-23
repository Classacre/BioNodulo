"""Focused owner for ``checkm_taxonomy_wf``."""

from .adapter import _CheckMTaxonomyWFContract


class CheckMTaxonomyWFNode(_CheckMTaxonomyWFContract):
    NODE_ID = "checkm_taxonomy_wf"
    UPSTREAM_SYMBOL = "CheckMTaxonomyWFNode"
