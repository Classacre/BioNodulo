"""Stable owner for ``centrifuge``."""

from bionodulo.nodes.builtin.kraken_family.adapter import _CentrifugeContract


class CentrifugeNode(_CentrifugeContract):
    NODE_ID = "centrifuge"
    UPSTREAM_SYMBOL = "CentrifugeNode"
