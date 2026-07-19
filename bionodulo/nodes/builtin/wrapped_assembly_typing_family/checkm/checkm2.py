"""Stable owner for ``checkm2``."""

from .checkm2_adapter import _CheckM2Contract


class CheckM2Node(_CheckM2Contract):
    NODE_ID = "checkm2"
    UPSTREAM_SYMBOL = "CheckM2Node"
