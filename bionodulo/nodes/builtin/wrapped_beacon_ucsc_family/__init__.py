"""Lazy compatibility exports for nodes moved into final semantic families."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "Beacon2Csv2XlsxNode": "bionodulo.nodes.builtin.beacon2_family.beacon2_csv2xlsx",
    "Beacon2ImportNode": "bionodulo.nodes.builtin.beacon2_family.beacon2_import",
    "Beacon2Pxf2BffNode": "bionodulo.nodes.builtin.beacon2_family.beacon2_pxf2bff",
    "Beacon2Vcf2BffNode": "bionodulo.nodes.builtin.beacon2_family.beacon2_vcf2bff",
    "Brew3rRNode": "bionodulo.nodes.builtin.annotation_family.brew3r_r",
    "FaSplitNode": "bionodulo.nodes.builtin.ucsc_family.fasplit",
    "FaToVcfNode": "bionodulo.nodes.builtin.ucsc_family.fatovcf",
    "GffCompareNode": "bionodulo.nodes.builtin.annotation_family.gffcompare",
    "GffReadNode": "bionodulo.nodes.builtin.annotation_family.gffread",
    "GtfToBed12Node": "bionodulo.nodes.builtin.ucsc_family.gtftobed12",
    "HeinzBumNode": "bionodulo.nodes.builtin.heinz_family.heinz_bum",
    "HeinzNode": "bionodulo.nodes.builtin.heinz_family.heinz",
    "HeinzScoringNode": "bionodulo.nodes.builtin.heinz_family.heinz_scoring",
    "HeinzVisualizationNode": "bionodulo.nodes.builtin.heinz_family.heinz_visualization",
    "MafToAxtNode": "bionodulo.nodes.builtin.ucsc_family.maftoaxt",
    "QQManhattanNode": "bionodulo.nodes.builtin.visualization_family.qq_manhattan",
    "UcscAxtChainNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_axtchain",
    "UcscAxtToMafNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_axtomaf",
    "UcscChainAntiRepeatNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_chainantirepeat",
    "UcscChainNetNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_chainnet",
    "UcscChainPreNetNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_chainprenet",
    "UcscChainSortNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_chainsort",
    "UcscChainSwapNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_chainswap",
    "UcscMafAddIRowsNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_mafaddirows",
    "UcscMafCoverageNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_mafcoverage",
    "UcscMafFetchNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_maffetch",
    "UcscMafFilterNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_maffilter",
    "UcscMafFragNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_maffrag",
    "UcscMafFragsNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_maffrags",
    "UcscMafGeneNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_mafgene",
    "UcscNetChainSubsetNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_netchainsubset",
    "UcscNetFilterNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_netfilter",
    "UcscNetSyntenicNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_netsyntenic",
    "UcscNetToAxtNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_nettoaxt",
    "UcscTwoBitToFaNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_twobittofa",
    "UcscWigToBigWigNode": "bionodulo.nodes.builtin.ucsc_family.ucsc_wigtobigwig",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
