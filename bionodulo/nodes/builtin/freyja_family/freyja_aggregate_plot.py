"""Focused owner for ``freyja_aggregate_plot``."""

from .adapter import FreyjaAggregatePlotNode as _NodeContract


class FreyjaAggregatePlotNode(_NodeContract):
    NODE_ID = "freyja_aggregate_plot"
    UPSTREAM_SYMBOL = "FreyjaAggregatePlotNode"
