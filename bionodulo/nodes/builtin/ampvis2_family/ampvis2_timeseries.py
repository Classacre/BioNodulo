"""Focused registered node for ``ampvis2_timeseries``."""

from .multivariate_adapter import Ampvis2TimeseriesNode as _NodeContract


class Ampvis2TimeseriesNode(_NodeContract):
    NODE_ID = "ampvis2_timeseries"
