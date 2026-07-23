"""Focused registered node for ``anndata_export``."""

from .io_adapter import AnnDataExportNode as _NodeContract


class AnnDataExportNode(_NodeContract):
    NODE_ID = "anndata_export"
