"""Compatibility exports for focused one-node modules."""

import bionodulo.nodes.builtin.bismark_family.methylation_extractor_adapter as _adapter
from bionodulo.nodes.builtin.bismark_family.methylation_extractor_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.bismark_family.bismark_methylation import BismarkMethylationNode
from bionodulo.nodes.builtin.bismark_family.bismark_methylation_extractor import BismarkMethylationExtractorNode

__all__ = ['BismarkMethylationNode', 'BismarkMethylationExtractorNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))
