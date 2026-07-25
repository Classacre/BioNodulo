"""Focused registered node for ``ampvis2_export_fasta``."""

from .io_adapter import Ampvis2ExportFastaNode as _NodeContract


class Ampvis2ExportFastaNode(_NodeContract):
    NODE_ID = "ampvis2_export_fasta"
