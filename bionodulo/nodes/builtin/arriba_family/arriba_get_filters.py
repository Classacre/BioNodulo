"""Focused owner for ``arriba_get_filters``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _ArribaGetFiltersContract


class ArribaGetFiltersNode(_ArribaGetFiltersContract):
    NODE_ID = "arriba_get_filters"
