"""Focused registered node for ``bcftools_csq``."""

from bionodulo.nodes.builtin.bcftools_family.analysis_adapter import BCFtoolsCSQNode as _NodeContract


class BCFtoolsCSQNode(_NodeContract):
    NODE_ID = 'bcftools_csq'
