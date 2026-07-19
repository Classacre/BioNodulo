"""Stable owner for ``collection_element_identifiers``."""

from .adapter import _CollectionElementIdentifiersContract


class CollectionElementIdentifiersNode(_CollectionElementIdentifiersContract):
    NODE_ID = "collection_element_identifiers"
    UPSTREAM_SYMBOL = "CollectionElementIdentifiersNode"
