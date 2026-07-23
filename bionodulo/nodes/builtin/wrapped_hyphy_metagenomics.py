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

__all__ = [name for name in globals() if name.endswith("Node")]
