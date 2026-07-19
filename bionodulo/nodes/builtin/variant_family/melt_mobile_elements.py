"""Stable owner for ``melt_mobile_elements``."""

from .legacy import _MELTMobileElementsContract


class MELTMobileElementsNode(_MELTMobileElementsContract):
    NODE_ID = "melt_mobile_elements"
