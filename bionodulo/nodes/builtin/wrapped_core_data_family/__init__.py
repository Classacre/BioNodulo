"""Compatibility exports for relocated core-data nodes."""

from __future__ import annotations

from importlib import import_module

from bionodulo.nodes.builtin.datamash_family.adapter import (
    _DatamashBaseNode as _DatamashBaseNode,
)


_EXPORTS = {
    "Anndata2RiNode": "bionodulo.nodes.builtin.anndata_family.anndata2ri",
    "AnnDataInspectNode": "bionodulo.nodes.builtin.anndata_family.anndata_inspect",
    "AnnDataExportNode": "bionodulo.nodes.builtin.anndata_family.anndata_export",
    "AnnDataImportNode": "bionodulo.nodes.builtin.anndata_family.anndata_import",
    "AnnDataManipulateNode": "bionodulo.nodes.builtin.anndata_family.anndata_manipulate",
    "AnnotateMyIDsNode": "bionodulo.nodes.builtin.annotation_family.annotatemyids",
    "ArgNormNode": "bionodulo.nodes.builtin.annotation_family.argnorm",
    "B2BToolsSingleSequenceNode": "bionodulo.nodes.builtin.proteomics_family.b2btools_single_sequence",
    "BamToScidxNode": "bionodulo.nodes.builtin.epigenomics_family.bam_to_scidx",
    "Baredsc1DNode": "bionodulo.nodes.builtin.baredsc_family.baredsc_1d",
    "Baredsc2DNode": "bionodulo.nodes.builtin.baredsc_family.baredsc_2d",
    "BaredscCombine1DNode": "bionodulo.nodes.builtin.baredsc_family.baredsc_combine_1d",
    "BaredscCombine2DNode": "bionodulo.nodes.builtin.baredsc_family.baredsc_combine_2d",
    "BasilNode": "bionodulo.nodes.builtin.variant_family.basil",
    "Bax2BamNode": "bionodulo.nodes.builtin.long_read_family.bax2bam",
    "BerokkaNode": "bionodulo.nodes.builtin.assembly_family.berokka",
    "BBGToBigWigNode": "bionodulo.nodes.builtin.visualization_family.bbgtobigwig",
    "CDHitNode": "bionodulo.nodes.builtin.sequence_family.cd_hit",
    "CellTypistNode": "bionodulo.nodes.builtin.single_cell_family.celltypist",
    "CEMiToolNode": "bionodulo.nodes.builtin.rna_seq_family.cemitool",
    "ChartsNode": "bionodulo.nodes.builtin.visualization_family.charts",
    "ClusteringFromDistmatNode": "bionodulo.nodes.builtin.statistics_family.clustering_from_distmat",
    "AddInputNameAsColumnNode": "bionodulo.nodes.builtin.data_transform_family.add_input_name_as_column",
    "AddInputNameAsColumnGalaxyNode": "bionodulo.nodes.builtin.data_transform_family.add_name_alias",
    "ColumnRemoveByHeaderNode": "bionodulo.nodes.builtin.data_transform_family.column_remove_by_header",
    "ColumnOrderHeaderSortNode": "bionodulo.nodes.builtin.data_transform_family.column_order_header_sort",
    "DatamashOpsNode": "bionodulo.nodes.builtin.datamash_family.datamash_ops",
    "DatamashTransposeNode": "bionodulo.nodes.builtin.datamash_family.datamash_transpose",
    "DatamashReverseNode": "bionodulo.nodes.builtin.datamash_family.datamash_reverse",
    "FalcoNode": "bionodulo.nodes.builtin.qc_family.falco",
    "FastaRegexFinderNode": "bionodulo.nodes.builtin.sequence_family.fasta_regex_finder",
    "BpGenbank2Gff3Node": "bionodulo.nodes.builtin.annotation_family.bp_genbank2gff3",
    "ModifyLoomNode": "bionodulo.nodes.builtin.single_cell_family.modify_loom",
    "AutoBIGSCliNode": "bionodulo.nodes.builtin.typing_family.autobigs_cli",
    "MLSTNode": "bionodulo.nodes.builtin.typing_family.mlst",
    "MLSTListNode": "bionodulo.nodes.builtin.typing_family.mlst_list",
    "SeqSero2Node": "bionodulo.nodes.builtin.typing_family.seqsero2",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
