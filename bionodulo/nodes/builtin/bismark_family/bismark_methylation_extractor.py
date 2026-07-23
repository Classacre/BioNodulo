"""Focused registered node for ``bismark_methylation_extractor``."""

from bionodulo.nodes.builtin.bismark_family.methylation_extractor_adapter import BismarkMethylationExtractorNode as _NodeContract


class BismarkMethylationExtractorNode(_NodeContract):
    NODE_ID = 'bismark_methylation_extractor'
