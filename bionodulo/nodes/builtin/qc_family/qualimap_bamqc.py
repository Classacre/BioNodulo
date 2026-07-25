"""Focused registered node for ``qualimap_bamqc``."""

from bionodulo.nodes.builtin.qc_family.qualimap_adapter import QualiMapNode as _NodeContract


class QualiMapNode(_NodeContract):
    NODE_ID = 'qualimap_bamqc'
