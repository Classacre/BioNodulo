"""Compatibility exports for relocated phylogeny and assembly nodes."""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "AbriTAMRNode": "bionodulo.nodes.builtin.annotation_family.abritamr",
    "AllegroNode": "bionodulo.nodes.builtin.population_genetics_family.allegro",
    "AlphaGenomeISMScannerNode": "bionodulo.nodes.builtin.alphagenome_family.alphagenome_ism_scanner",
    "AlphaGenomeIntervalPredictorNode": "bionodulo.nodes.builtin.alphagenome_family.alphagenome_interval_predictor",
    "AlphaGenomeSequencePredictorNode": "bionodulo.nodes.builtin.alphagenome_family.alphagenome_sequence_predictor",
    "AlphaGenomeVariantEffectNode": "bionodulo.nodes.builtin.alphagenome_family.alphagenome_variant_effect",
    "AlphaGenomeVariantScorerNode": "bionodulo.nodes.builtin.alphagenome_family.alphagenome_variant_scorer",
    "AMASConcatNode": "bionodulo.nodes.builtin.amas_family.amas_concat",
    "AMASRemoveNode": "bionodulo.nodes.builtin.amas_family.amas_remove",
    "AMASReplicateNode": "bionodulo.nodes.builtin.amas_family.amas_replicate",
    "AMASSplitNode": "bionodulo.nodes.builtin.amas_family.amas_split",
    "AMASSummaryNode": "bionodulo.nodes.builtin.amas_family.amas_summary",
    "AmpliCanNode": "bionodulo.nodes.builtin.crispr_family.amplican",
    "ART454Node": "bionodulo.nodes.builtin.art_family.art_454",
    "ARTIlluminaNode": "bionodulo.nodes.builtin.art_family.art_illumina",
    "ARTSOLiDNode": "bionodulo.nodes.builtin.art_family.art_solid",
    "AssemblyStatsNode": "bionodulo.nodes.builtin.assembly_family.assembly_stats",
    "BBToolsBBDukNode": "bionodulo.nodes.builtin.bbtools_family.bbtools_bbduk",
    "BBToolsBBMapNode": "bionodulo.nodes.builtin.bbtools_family.bbtools_bbmap",
    "BBToolsBBMergeNode": "bionodulo.nodes.builtin.bbtools_family.bbtools_bbmerge",
    "BBToolsBBNormNode": "bionodulo.nodes.builtin.bbtools_family.bbtools_bbnorm",
    "BBToolsCallVariantsNode": "bionodulo.nodes.builtin.bbtools_family.bbtools_callvariants",
    "BBToolsTadpoleNode": "bionodulo.nodes.builtin.bbtools_family.bbtools_tadpole",
    "ClustalWNode": "bionodulo.nodes.builtin.phylogeny_family.clustalw",
    "EukRepNode": "bionodulo.nodes.builtin.metagenomics_family.eukrep",
    "FLASHNode": "bionodulo.nodes.builtin.trimming_family.flash",
    "FragGeneScanNode": "bionodulo.nodes.builtin.annotation_family.fraggenescan",
    "GAMMANode": "bionodulo.nodes.builtin.annotation_family.gamma",
    "GAMMASNode": "bionodulo.nodes.builtin.annotation_family.gamma_s",
    "GenomeScopeNode": "bionodulo.nodes.builtin.assembly_family.genomescope",
    "MiniaNode": "bionodulo.nodes.builtin.assembly_family.minia",
    "NonpareilNode": "bionodulo.nodes.builtin.metagenomics_family.nonpareil",
    "PEARNode": "bionodulo.nodes.builtin.trimming_family.iuc_pear",
    "PhyMLNode": "bionodulo.nodes.builtin.phylogeny_family.phyml",
    "PlasClassNode": "bionodulo.nodes.builtin.metagenomics_family.plasclass",
    "PlasFlowNode": "bionodulo.nodes.builtin.metagenomics_family.plasflow",
    "ProdigalNode": "bionodulo.nodes.builtin.annotation_family.prodigal",
    "QuicktreeNode": "bionodulo.nodes.builtin.phylogeny_family.quicktree",
    "RapidNJNode": "bionodulo.nodes.builtin.phylogeny_family.rapidnj",
    "RedNode": "bionodulo.nodes.builtin.genomics_family.red",
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
