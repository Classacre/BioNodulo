"""Focused owner for ``bandage_info``."""

from .adapter import _BandageInfoContract


class BandageInfoNode(_BandageInfoContract):
    NODE_ID = "bandage_info"
    UPSTREAM_SYMBOL = "BandageInfoNode"
