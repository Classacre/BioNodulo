"""Stable owner for ``kaiju_add_taxon_names``."""

from .adapter import _KaijuAddTaxonNamesContract


class KaijuAddTaxonNamesNode(_KaijuAddTaxonNamesContract):
    NODE_ID = "kaiju_add_taxon_names"
    UPSTREAM_SYMBOL = "KaijuAddTaxonNamesNode"
