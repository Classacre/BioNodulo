"""Focused owner for ``collection_element_identifiers``."""

from bionodulo.nodes.builtin._alignment_taxonomy_utilities_adapter import _CollectionElementIdentifiersContract


class CollectionElementIdentifiersNode(_CollectionElementIdentifiersContract):
    NODE_ID = "collection_element_identifiers"
    UPSTREAM_SYMBOL = "CollectionElementIdentifiersNode"
