"""Stable owner for ``arriba_get_filters``."""

from .legacy import _ArribaGetFiltersContract


class ArribaGetFiltersNode(_ArribaGetFiltersContract):
    NODE_ID = "arriba_get_filters"
