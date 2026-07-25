"""Focused, source-pinned metagenomics operations."""

from .bracken import BrackenNode
from .kraken2 import Kraken2Node
from .kraken2_build import Kraken2BuildNode
from .krona import KronaTaxonomyNode
from .maxbin import MaxBinNode

__all__ = [
    "BrackenNode",
    "CheckMNode",
    "HUMAnNNode",
    "Kraken2Node",
    "Kraken2BuildNode",
    "KronaTaxonomyNode",
    "MaxBinNode",
    "MetaPhlAnNode",
]


def __getattr__(name: str):
    if name == "CheckMNode":
        from bionodulo.nodes.builtin.checkm_family.checkm import CheckMNode

        return CheckMNode
    if name == "HUMAnNNode":
        from bionodulo.nodes.builtin.humann_family.humann import HUMAnNNode

        return HUMAnNNode
    if name == "MetaPhlAnNode":
        from bionodulo.nodes.builtin.metaphlan_family.metaphlan import MetaPhlAnNode

        return MetaPhlAnNode
    raise AttributeError(name)
