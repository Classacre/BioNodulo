"""Focused owner for ``collection_column_join``."""

from bionodulo.nodes.builtin._alignment_taxonomy_utilities_adapter import _CollectionColumnJoinContract


class CollectionColumnJoinNode(_CollectionColumnJoinContract):
    NODE_ID = "collection_column_join"
    UPSTREAM_SYMBOL = "CollectionColumnJoinNode"
