"""Focused EMBL-EBI InterProScan REST nodes."""

from .interpro import InterProNode
from .scan import InterProScanNode

__all__ = ["InterProNode", "InterProScanNode"]
