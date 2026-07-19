"""RNA-seq compatibility nodes and legacy import aliases."""

from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


class FeatureCountsNode(CommandNode):
    """Count reads per gene with featureCounts."""
    NODE_ID = ""
    DISPLAY_NAME = "featureCounts"
    REQUIRED_CONDA_PACKAGES = ['subread']
    CATEGORY = "rna_seq"
    DESCRIPTION = "Count reads mapped to genomic features"
    SEARCH_ALIASES = ["featurecounts", "counts", "gene counts", "subread"]
    RETURN_TYPES = ("COUNTS",)
    RETURN_NAMES = ("counts",)
    REQUIRED_EXECUTABLES = ["featureCounts"]
    DOCUMENTATION_URL = "https://subread.sourceforge.net/"
    VERSION = "2.1.1"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        # Templates may connect annotation via "annotation" or "gtf"
        gtf = inputs.get("gtf") or inputs.get("annotation", "")
        cmd = [
            "featureCounts",
            "-a", str(gtf),
            "-o", f"{inputs.get('output', '.')}/counts.counts.tsv",
            "-T", str(inputs.get("threads", 8)),
        ]
        strand = str(inputs.get("strandness", "0"))
        if strand in ("1", "2"):
            cmd.extend(["-s", strand])
        if inputs.get("primary"):
            cmd.append("--primary")
        if inputs.get("count_read_pairs") is not False:
            cmd.extend(["-p", "--countReadPairs"])
        if inputs.get("feature_type"):
            cmd.extend(["-t", str(inputs["feature_type"])])
        if inputs.get("attribute"):
            cmd.extend(["-g", str(inputs["attribute"])])
        cmd.append(str(inputs.get("bam", "")))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Aligned BAM file (sorted, indexed)"}),
                "gtf": ("GTF", {"description": "Gene annotation GTF"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "strandness": ("STRING", {"default": "0", "options": ["0", "1", "2"], "label": "Strandness", "advanced": True}),
                "primary": ("BOOLEAN", {"default": True, "label": "Primary Only", "advanced": True}),
                "count_read_pairs": ("BOOLEAN", {"default": True, "label": "Count Read Pairs", "advanced": True}),
                "feature_type": ("STRING", {"default": "exon", "label": "Feature Type", "advanced": True}),
                "attribute": ("STRING", {"default": "gene_id", "label": "Attribute", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class FeatureCountsAliasNode(FeatureCountsNode):
    """Planner/workflow compatibility alias for featureCounts."""
    NODE_ID = "feature_counts"
    DISPLAY_NAME = "Feature Counts"
    DESCRIPTION = "Count reads per gene with featureCounts for RNA-seq workflows."
    SEARCH_ALIASES = [
        "feature_counts",
        "featurecounts",
        "feature counts",
        "gene counts",
        "subread",
        "rna-seq counts",
    ]


class StringTieNode(CommandNode):
    """Transcript assembly and quantification with StringTie."""
    NODE_ID = "stringtie"
    DISPLAY_NAME = "StringTie"
    REQUIRED_CONDA_PACKAGES = ['stringtie']
    CATEGORY = "rna_seq"
    DESCRIPTION = "Transcript assembly and quantification from RNA-seq alignments"
    SEARCH_ALIASES = ["stringtie", "assemble", "transcript", "expression"]
    RETURN_TYPES = ("GTF", "TSV")
    RETURN_NAMES = ("transcripts", "gene_abundance")
    REQUIRED_EXECUTABLES = ["stringtie"]
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/stringtie/"
    VERSION = "3.0.3"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "stringtie",
            str(inputs.get("bam", "")),
            "-G", str(inputs.get("gtf", "")),
            "-o", f"{inputs.get('output', '.')}/transcripts.gtf",
            "-A", f"{inputs.get('output', '.')}/gene_abundance.tsv",
            "-p", str(inputs.get("threads", 8)),
        ]
        if inputs.get("fr"):
            cmd.append("--fr")
        elif inputs.get("rf"):
            cmd.append("--rf")
        if inputs.get("min_isoform_fraction") is not None:
            cmd.extend(["-f", str(inputs["min_isoform_fraction"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Aligned BAM file"}),
                "gtf": ("GTF", {"description": "Reference gene annotation GTF"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "fr": ("BOOLEAN", {"default": False, "label": "Forward Strand (fr)", "advanced": True}),
                "rf": ("BOOLEAN", {"default": False, "label": "Reverse Strand (rf)", "advanced": True}),
                "min_isoform_fraction": ("FLOAT", {"default": 0.01, "min": 0.0, "max": 1.0, "step": 0.01, "label": "Min Isoform Fraction", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


# Stable Salmon/Kallisto IDs are owned by focused source-pinned modules. These
# imports preserve the historical ``bionodulo.nodes.builtin.rna_seq`` import
# path without causing duplicate registry declarations.
from bionodulo.nodes.builtin.rna_seq_family.kallisto import (  # noqa: E402,F401
    KallistoIndexNode,
    KallistoQuantNode,
)
from bionodulo.nodes.builtin.rna_seq_family.salmon import (  # noqa: E402,F401
    SalmonIndexNode,
    SalmonQuantNode,
)
