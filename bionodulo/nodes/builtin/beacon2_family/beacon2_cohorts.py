"""Stable owner for ``beacon2_cohorts``."""

from .adapter import _Beacon2CohortsContract


class Beacon2CohortsNode(_Beacon2CohortsContract):
    NODE_ID = "beacon2_cohorts"
    UPSTREAM_SYMBOL = "Beacon2CohortsNode"
