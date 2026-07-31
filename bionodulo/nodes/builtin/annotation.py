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

# Explicit, not `[name for name in globals() ...]`: mypy evaluates __all__
# statically, so a comprehension over globals() made `import *` export
# nothing as far as the type checker was concerned, and every name in every
# consuming module became an undefined-name error. That pattern accounted
# for roughly 8000 of the repository's 8535 mypy errors. The contents below
# are exactly what the comprehension produced at import time.
__all__ = [
    "ANNOVARNode",
    "AnnotateVCFNode",
    "BEDToolsClosestNode",
    "BaktaNode",
    "BcftoolsAnnotateNode",
    "EggNOGMapperNode",
    "FuncotateTableNode",
    "FuncotatorNode",
    "InterProScanNode",
    "IntersectGenesNode",
    "ProkkaNode",
    "SnpEffNode",
    "VEPAnnotateNode",
    "VEPNode",
]
