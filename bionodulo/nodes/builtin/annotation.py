"""Compatibility facade for focused annotation nodes."""

# ruff: noqa: F401

from bionodulo.nodes.builtin.annotation_family import (
    ANNOVARNode,
    AnnotateVCFNode,
    BaktaNode,
    BcftoolsAnnotateNode,
    EggNOGMapperNode,
    FuncotateTableNode,
    FuncotatorNode,
    InterProScanNode,
    IntersectGenesNode,
    ProkkaNode,
    SnpEffNode,
    VEPAnnotateNode,
    VEPNode,
)
from bionodulo.nodes.builtin.bedtools_family.closest import BEDToolsClosestNode

__all__ = [name for name in globals() if name.endswith("Node")]
