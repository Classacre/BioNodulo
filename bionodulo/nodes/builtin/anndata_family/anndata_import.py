"""Focused registered node for ``anndata_import``."""

from .io_adapter import AnnDataImportNode as _NodeContract


class AnnDataImportNode(_NodeContract):
    NODE_ID = "anndata_import"
