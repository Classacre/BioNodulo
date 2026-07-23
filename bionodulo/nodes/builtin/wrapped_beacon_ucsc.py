"""Compatibility facade for Beacon2, HEINZ, GFF, BREW3R, QQ, and UCSC nodes."""
# ruff: noqa: F401

from bionodulo.nodes.builtin.annotation_family import Brew3rRNode, GffCompareNode, GffReadNode
from bionodulo.nodes.builtin.beacon2_family import (
    Beacon2Csv2XlsxNode,
    Beacon2ImportNode,
    Beacon2Pxf2BffNode,
    Beacon2Vcf2BffNode,
)
from bionodulo.nodes.builtin.heinz_family import (
    HeinzBumNode,
    HeinzNode,
    HeinzScoringNode,
    HeinzVisualizationNode,
)
from bionodulo.nodes.builtin.ucsc_family import (
    FaSplitNode,
    FaToVcfNode,
    GtfToBed12Node,
    MafToAxtNode,
    UcscAxtChainNode,
    UcscAxtToMafNode,
    UcscChainAntiRepeatNode,
    UcscChainNetNode,
    UcscChainPreNetNode,
    UcscChainSortNode,
    UcscChainSwapNode,
    UcscMafAddIRowsNode,
    UcscMafCoverageNode,
    UcscMafFetchNode,
    UcscMafFilterNode,
    UcscMafFragNode,
    UcscMafFragsNode,
    UcscMafGeneNode,
    UcscNetChainSubsetNode,
    UcscNetFilterNode,
    UcscNetSyntenicNode,
    UcscNetToAxtNode,
    UcscTwoBitToFaNode,
    UcscWigToBigWigNode,
)
from bionodulo.nodes.builtin.visualization_family import QQManhattanNode

__all__ = [name for name in globals() if name.endswith("Node")]
