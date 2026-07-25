"""Focused owner for ``eukrep``."""

from bionodulo.nodes.builtin.annotation_family.microbial_gene_tools_adapter import (
    EukRepNode as _NodeContract,
)


class EukRepNode(_NodeContract):
    NODE_ID = "eukrep"
