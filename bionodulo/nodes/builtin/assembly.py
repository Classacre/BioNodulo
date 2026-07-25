"""Compatibility facade for focused genome-assembly nodes."""

# ruff: noqa: F401
from bionodulo.nodes.builtin.assembly_family.canu import CanuNode
from bionodulo.nodes.builtin.assembly_family.flye import FlyeNode
from bionodulo.nodes.builtin.assembly_family.megahit import MEGAHITNode
from bionodulo.nodes.builtin.assembly_family.quast import QuastNode
from bionodulo.nodes.builtin.assembly_family.spades import SPAdesNode
from bionodulo.nodes.builtin.assembly_family.unicycler import UnicyclerNode

__all__ = [
    "CanuNode",
    "FlyeNode",
    "UnicyclerNode",
    "SPAdesNode",
    "MEGAHITNode",
    "QuastNode",
]
