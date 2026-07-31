"""Compatibility facade for focused HyPhy and metagenomics wrapper nodes."""
# ruff: noqa: F401

from bionodulo.nodes.builtin.comparative_genomics_family import FastANINode
from bionodulo.nodes.builtin.hyphy_family import (
    HyPhyABSRELNode,
    HyPhyAnnotateNode,
    HyPhyBGMNode,
    HyPhyBStillNode,
    HyPhyBUSTEDNode,
    HyPhyCFELNode,
    HyPhyCLNNode,
    HyPhyCONVNode,
    HyPhyFADENode,
    HyPhyFELNode,
    HyPhyFUBARNode,
    HyPhyGARDNode,
    HyPhyInferStasisClustersNode,
    HyPhyMEMENode,
    HyPhyPRIMENode,
    HyPhyRELAXNode,
    HyPhySLACNode,
    HyPhySM2019Node,
    HyPhyStrikeAmbigsNode,
)
from bionodulo.nodes.builtin.mash_family import (
    MashDistNode,
    MashMapNode,
    MashPasteNode,
    MashScreenNode,
    MashSketchNode,
)
from bionodulo.nodes.builtin.metaphlan_family import (
    CustomizeMetaPhlAnDatabaseNode,
    ExtractMetaPhlAnDatabaseNode,
    MergeMetaPhlAnTablesNode,
)

# Explicit, not `[name for name in globals() ...]`: mypy evaluates __all__
# statically, so a comprehension over globals() made `import *` export
# nothing as far as the type checker was concerned, and every name in every
# consuming module became an undefined-name error. That pattern accounted
# for roughly 8000 of the repository's 8535 mypy errors. The contents below
# are exactly what the comprehension produced at import time.
__all__ = [
    "CustomizeMetaPhlAnDatabaseNode",
    "ExtractMetaPhlAnDatabaseNode",
    "FastANINode",
    "HyPhyABSRELNode",
    "HyPhyAnnotateNode",
    "HyPhyBGMNode",
    "HyPhyBStillNode",
    "HyPhyBUSTEDNode",
    "HyPhyCFELNode",
    "HyPhyCLNNode",
    "HyPhyCONVNode",
    "HyPhyFADENode",
    "HyPhyFELNode",
    "HyPhyFUBARNode",
    "HyPhyGARDNode",
    "HyPhyInferStasisClustersNode",
    "HyPhyMEMENode",
    "HyPhyPRIMENode",
    "HyPhyRELAXNode",
    "HyPhySLACNode",
    "HyPhySM2019Node",
    "HyPhyStrikeAmbigsNode",
    "MashDistNode",
    "MashMapNode",
    "MashPasteNode",
    "MashScreenNode",
    "MashSketchNode",
    "MergeMetaPhlAnTablesNode",
]
