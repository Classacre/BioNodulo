"""Stable owner for ``kaiju2table``."""

from .table_adapter import _Kaiju2TableContract


class Kaiju2TableNode(_Kaiju2TableContract):
    NODE_ID = "kaiju2table"
    UPSTREAM_SYMBOL = "Kaiju2TableNode"
