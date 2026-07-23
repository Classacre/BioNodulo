"""Stable owner for ``beacon2_biosamples``."""

from .adapter import _Beacon2BiosamplesContract


class Beacon2BiosamplesNode(_Beacon2BiosamplesContract):
    NODE_ID = "beacon2_biosamples"
    UPSTREAM_SYMBOL = "Beacon2BiosamplesNode"
