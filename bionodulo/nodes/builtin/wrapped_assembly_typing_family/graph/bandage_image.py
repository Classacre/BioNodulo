"""Stable owner for ``bandage_image``."""

from .bandage_adapter import _BandageImageContract


class BandageImageNode(_BandageImageContract):
    NODE_ID = "bandage_image"
    UPSTREAM_SYMBOL = "BandageImageNode"
