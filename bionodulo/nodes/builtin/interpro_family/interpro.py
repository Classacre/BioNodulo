"""Compatibility InterPro operation backed by the InterProScan REST contract."""

from .scan import InterProScanNode


class InterProNode(InterProScanNode):
    """Preserve the original InterPro node ID."""

    NODE_ID = "interpro"
    DISPLAY_NAME = "InterPro"
    DESCRIPTION = "Submit a protein sequence to InterProScan and return InterPro annotations."
