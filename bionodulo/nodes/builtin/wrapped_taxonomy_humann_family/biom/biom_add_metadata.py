"""Stable owner for ``biom_add_metadata``."""

from .adapter import _BiomAddMetadataContract


class BiomAddMetadataNode(_BiomAddMetadataContract):
    NODE_ID = "biom_add_metadata"
    UPSTREAM_SYMBOL = "BiomAddMetadataNode"
