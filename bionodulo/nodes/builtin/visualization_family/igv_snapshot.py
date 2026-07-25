"""Stable owner for the ``igv_snapshot`` node."""

from .adapter import _IGVSnapshotContract


class IGVSnapshotNode(_IGVSnapshotContract):
    """Render a product-native IGV-style multi-track region view."""

    NODE_ID = "igv_snapshot"
    UPSTREAM_SYMBOL = "IGVSnapshotNode"
