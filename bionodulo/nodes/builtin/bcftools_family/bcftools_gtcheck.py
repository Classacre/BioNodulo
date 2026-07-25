"""Focused registered node for ``bcftools_gtcheck``."""

from bionodulo.nodes.builtin.bcftools_family.reporting_adapter import BCFtoolsGTcheckNode as _NodeContract


class BCFtoolsGTcheckNode(_NodeContract):
    NODE_ID = 'bcftools_gtcheck'
