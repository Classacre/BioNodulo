"""Focused owner for ``red``."""

from bionodulo.nodes.builtin.annotation_family.microbial_gene_tools_adapter import (
    RedNode as _NodeContract,
)


class RedNode(_NodeContract):
    NODE_ID = "red"
