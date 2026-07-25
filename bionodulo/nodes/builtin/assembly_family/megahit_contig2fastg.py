"""Focused registered node for ``megahit_contig2fastg``."""

from .wrapped_assembly_adapter import MegahitContig2FastgNode as _NodeContract


class MegahitContig2FastgNode(_NodeContract):
    NODE_ID = "megahit_contig2fastg"
