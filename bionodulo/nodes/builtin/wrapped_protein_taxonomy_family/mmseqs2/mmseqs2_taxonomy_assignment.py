"""Stable owner for ``mmseqs2_taxonomy_assignment``."""

from .adapter import _MMseqs2TaxonomyAssignmentContract


class MMseqs2TaxonomyAssignmentNode(_MMseqs2TaxonomyAssignmentContract):
    NODE_ID = "mmseqs2_taxonomy_assignment"
    UPSTREAM_SYMBOL = "MMseqs2TaxonomyAssignmentNode"
