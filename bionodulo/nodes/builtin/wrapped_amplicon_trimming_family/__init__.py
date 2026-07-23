"""Compatibility exports for relocated amplicon and trimming nodes."""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "AdapterRemovalNode": "bionodulo.nodes.builtin.trimming_family.adapter_removal",
    "ALDEx2Node": "bionodulo.nodes.builtin.differential_abundance_family.aldex2",
    "ANCOMBCNode": "bionodulo.nodes.builtin.differential_abundance_family.ancombc",
    "ANGSDContaminationNode": "bionodulo.nodes.builtin.angsd_family.angsd_contamination",
    "ANGSDNode": "bionodulo.nodes.builtin.angsd_family.angsd",
    "Ampvis2AlphaDiversityNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_alpha_diversity",
    "Ampvis2BoxplotNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_boxplot",
    "Ampvis2CoreNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_core",
    "Ampvis2ExportFastaNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_export_fasta",
    "Ampvis2ExportOtuNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_export_otu",
    "Ampvis2FrequencyNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_frequency",
    "Ampvis2HeatmapNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_heatmap",
    "Ampvis2LoadNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_load",
    "Ampvis2MergeAmpvis2Node": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_merge_ampvis2",
    "Ampvis2MergeReplicatesNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_mergereplicates",
    "Ampvis2OctaveNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_octave",
    "Ampvis2OrdinateNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_ordinate",
    "Ampvis2OtuNetworkNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_otu_network",
    "Ampvis2RankAbundanceNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_rankabundance",
    "Ampvis2RarecurveNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_rarecurve",
    "Ampvis2SetMetadataNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_setmetadata",
    "Ampvis2SubsetSamplesNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_subset_samples",
    "Ampvis2SubsetTaxaNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_subset_taxa",
    "Ampvis2TimeseriesNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_timeseries",
    "Ampvis2VennNode": "bionodulo.nodes.builtin.ampvis2_family.ampvis2_venn",
    "MegahitContig2FastgNode": "bionodulo.nodes.builtin.assembly_family.megahit_contig2fastg",
    "MiniasmNode": "bionodulo.nodes.builtin.assembly_family.miniasm",
    "PrinseqNode": "bionodulo.nodes.builtin.trimming_family.prinseq",
    "TrimNGalaxyNode": "bionodulo.nodes.builtin.trimming_family.trimns",
    "TrimNNode": "bionodulo.nodes.builtin.trimming_family.trimn",
    "VSearchAlignmentNode": "bionodulo.nodes.builtin.vsearch_family.vsearch_alignment",
    "VSearchChimeraDetectionNode": "bionodulo.nodes.builtin.vsearch_family.vsearch_chimera_detection",
    "VSearchClusterNode": "bionodulo.nodes.builtin.vsearch_family.vsearch_cluster",
    "VSearchDereplicationNode": "bionodulo.nodes.builtin.vsearch_family.vsearch_dereplication",
    "VSearchMaskingNode": "bionodulo.nodes.builtin.vsearch_family.vsearch_masking",
    "VSearchSearchNode": "bionodulo.nodes.builtin.vsearch_family.vsearch_search",
    "VSearchShufflingNode": "bionodulo.nodes.builtin.vsearch_family.vsearch_shuffling",
    "VSearchSortingNode": "bionodulo.nodes.builtin.vsearch_family.vsearch_sorting",
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
