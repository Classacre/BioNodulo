"""Stable owner for ``mothur_taxonomy_to_krona``."""

from .adapter import _MothurTaxonomyToKronaContract


class MothurTaxonomyToKronaNode(_MothurTaxonomyToKronaContract):
    NODE_ID = "mothur_taxonomy_to_krona"
    UPSTREAM_SYMBOL = "MothurTaxonomyToKronaNode"
