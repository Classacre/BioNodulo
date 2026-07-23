"""Stable owner for ``beacon2_datasets``."""

from .adapter import _Beacon2DatasetsContract


class Beacon2DatasetsNode(_Beacon2DatasetsContract):
    NODE_ID = "beacon2_datasets"
    UPSTREAM_SYMBOL = "Beacon2DatasetsNode"
