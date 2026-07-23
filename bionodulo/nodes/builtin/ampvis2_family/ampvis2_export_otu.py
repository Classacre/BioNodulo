"""Focused registered node for ``ampvis2_export_otu``."""

from .io_adapter import Ampvis2ExportOtuNode as _NodeContract


class Ampvis2ExportOtuNode(_NodeContract):
    NODE_ID = "ampvis2_export_otu"
