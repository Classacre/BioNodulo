"""Focused registered node for ``bismark_methylation``."""

from bionodulo.nodes.builtin.bismark_family.methylation_extractor_adapter import BismarkMethylationNode as _NodeContract
from bionodulo.nodes.builtin.bismark_family.bismark_methylation_extractor import BismarkMethylationExtractorNode


class BismarkMethylationNode(_NodeContract, BismarkMethylationExtractorNode):
    NODE_ID = 'bismark_methylation'
