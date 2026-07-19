"""Stable owner for ``cherri_train``."""

from .adapter import _CheRRITrainContract


class CheRRITrainNode(_CheRRITrainContract):
    NODE_ID = "cherri_train"
    UPSTREAM_SYMBOL = "CheRRITrainNode"
