"""Focused owner for ``nonpareil``."""

from bionodulo.nodes.builtin.annotation_family.microbial_gene_tools_adapter import (
    NonpareilNode as _NodeContract,
)


class NonpareilNode(_NodeContract):
    NODE_ID = "nonpareil"
