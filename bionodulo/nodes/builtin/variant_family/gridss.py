"""Stable owner for ``gridss``."""

from .legacy import _GRIDSSContract


class GRIDSSNode(_GRIDSSContract):
    NODE_ID = "gridss"
