"""RNA-seq analysis nodes for BioNodulo.

Provides nodes for transcript quantification (Salmon, Kallisto, featureCounts,
StringTie) used in RNA-seq differential expression workflows.
"""
from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


class SalmonIndexNode(CommandNode):
    """Build Salmon transcriptome index."""
    NODE_ID = "salmon_index"
    DISPLAY_NAME = "Salmon Index"
    REQUIRED_CONDA_PACKAGES = ['salmon']
    CATEGORY = "rna_seq"
    DESCRIPTION = "Build Salmon quasi-mapping index for transcripts"
    SEARCH_ALIASES = ["salmon", "index", "transcriptome", "quant"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("index",)
    REQUIRED_EXECUTABLES = ["salmon"]
    DOCUMENTATION_URL = "https://salmon.readthedocs.io/"
    VERSION = "1.10.0"
    COMMAND = [
        "salmon", "index",
        "-t", "{inputs.transcripts}",
        "-i", "{output}/salmon_index",
        "-p", "{inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "transcripts": ("FASTA", {"description": "Transcriptome FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "kmer": ("INT", {"default": 31, "min": 5, "max": 32}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SalmonQuantNode(CommandNode):
    """Quantify transcripts with Salmon."""
    NODE_ID = "salmon_quant"
    DISPLAY_NAME = "Salmon Quant"
    REQUIRED_CONDA_PACKAGES = ['salmon']
    CATEGORY = "rna_seq"
    DESCRIPTION = "Transcript-level quantification with Salmon"
    SEARCH_ALIASES = ["salmon", "quant", "expression", "tpm", "counts"]
    RETURN_TYPES = ("ABUNDANCE",)
    RETURN_NAMES = ("quant",)
    REQUIRED_EXECUTABLES = ["salmon"]
    DOCUMENTATION_URL = "https://salmon.readthedocs.io/"
    VERSION = "1.10.0"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reads = inputs.get("reads", [])
        if isinstance(reads, str):
            reads = [reads]
        r1 = reads[0] if len(reads) > 0 else inputs.get("r1", "")
        r2 = reads[1] if len(reads) > 1 else inputs.get("r2", "")
        lib_type = inputs.get("lib_type", "A")
        cmd = [
            "salmon", "quant",
            "-i", str(inputs.get("index", "")),
            "-l", str(lib_type),
            "-o", str(inputs.get("output", inputs.get("output_dir", "."))),
            "-p", str(inputs.get("threads", 8)),
        ]
        if r1 and r2:
            cmd.extend(["-1", str(r1), "-2", str(r2)])
        elif r1:
            cmd.extend(["-r", str(r1)])
        if inputs.get("gc_bias"):
            cmd.append("--gcBias")
        if inputs.get("seq_bias"):
            cmd.append("--seqBias")
        if inputs.get("validate_mappings") is not False:
            cmd.append("--validateMappings")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Forward reads (R1)"}),
                "r2": ("FASTQ", {"description": "Reverse reads (R2)"}),
                "index": ("INDEX_DIR", {"description": "Salmon index directory"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "lib_type": ("STRING", {"default": "A", "options": ["A", "IS", "ISR", "IU", "U", "SF", "SR"], "label": "Library Type", "advanced": True}),
                "gc_bias": ("BOOLEAN", {"default": True, "label": "GC Bias Correction", "advanced": True}),
                "seq_bias": ("BOOLEAN", {"default": True, "label": "Seq Bias Correction", "advanced": True}),
                "validate_mappings": ("BOOLEAN", {"default": True, "label": "Validate Mappings", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str) -> list:
        from pathlib import Path
        od = Path(output_dir)
        return [od / "quant.sf"]


class KallistoIndexNode(CommandNode):
    """Build Kallisto transcriptome index."""
    NODE_ID = "kallisto_index"
    DISPLAY_NAME = "Kallisto Index"
    REQUIRED_CONDA_PACKAGES = ['kallisto']
    CATEGORY = "rna_seq"
    DESCRIPTION = "Build Kallisto k-mer index for transcriptome"
    SEARCH_ALIASES = ["kallisto", "index", "transcriptome", "pseudoalign"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("index",)
    REQUIRED_EXECUTABLES = ["kallisto"]
    DOCUMENTATION_URL = "https://pachterlab.github.io/kallisto/"
    VERSION = "0.50.1"
    COMMAND = [
        "kallisto", "index",
        "-i", "{output}/kallisto.idx",
        "-k", "{inputs.kmer}",
        "{inputs.transcripts}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "transcripts": ("FASTA", {"description": "Transcriptome FASTA"}),
                "kmer": ("INT", {"default": 31, "min": 5, "max": 64}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class KallistoQuantNode(CommandNode):
    """Quantify transcripts with Kallisto."""
    NODE_ID = "kallisto_quant"
    DISPLAY_NAME = "Kallisto Quant"
    REQUIRED_CONDA_PACKAGES = ['kallisto']
    CATEGORY = "rna_seq"
    DESCRIPTION = "Pseudoalignment-based transcript quantification"
    SEARCH_ALIASES = ["kallisto", "quant", "expression", "pseudoalign"]
    RETURN_TYPES = ("ABUNDANCE",)
    RETURN_NAMES = ("abundance",)
    REQUIRED_EXECUTABLES = ["kallisto"]
    DOCUMENTATION_URL = "https://pachterlab.github.io/kallisto/"
    VERSION = "0.50.1"
    COMMAND = [
        "kallisto", "quant",
        "-i", "{inputs.index}",
        "-o", "{output}",
        "-t", "{inputs.threads}",
        "{inputs.r1}",
        "{inputs.r2}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Forward reads (R1)"}),
                "r2": ("FASTQ", {"description": "Reverse reads (R2)"}),
                "index": ("FILE", {"description": "Kallisto index file (.idx)"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "bootstrap": ("INT", {"default": 100, "min": 0, "max": 1000, "step": 10, "display": "slider"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for Kallisto."""
        reads = kwargs.get("reads", [])
        if isinstance(reads, (list, tuple)) and len(reads) >= 2:
            kwargs["r1"] = reads[0]
            kwargs["r2"] = reads[1]
        return await super().run(**kwargs)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str) -> list:
        from pathlib import Path
        od = Path(output_dir)
        return [od / "abundance.tsv"]


class FeatureCountsNode(CommandNode):
    """Count reads per gene with featureCounts."""
    NODE_ID = "featurecounts"
    DISPLAY_NAME = "featureCounts"
    REQUIRED_CONDA_PACKAGES = ['subread']
    CATEGORY = "rna_seq"
    DESCRIPTION = "Count reads mapped to genomic features"
    SEARCH_ALIASES = ["featurecounts", "counts", "gene counts", "subread"]
    RETURN_TYPES = ("COUNTS",)
    RETURN_NAMES = ("counts",)
    REQUIRED_EXECUTABLES = ["featureCounts"]
    DOCUMENTATION_URL = "https://subread.sourceforge.net/"
    VERSION = "2.0.6"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        # Templates may connect annotation via "annotation" or "gtf"
        gtf = inputs.get("gtf") or inputs.get("annotation", "")
        cmd = [
            "featureCounts",
            "-a", str(gtf),
            "-o", f"{inputs.get('output', '.')}/counts.txt",
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


class StringTieNode(CommandNode):
    """Transcript assembly and quantification with StringTie."""
    NODE_ID = "stringtie"
    DISPLAY_NAME = "StringTie"
    REQUIRED_CONDA_PACKAGES = ['stringtie']
    CATEGORY = "rna_seq"
    DESCRIPTION = "Transcript assembly and quantification from RNA-seq alignments"
    SEARCH_ALIASES = ["stringtie", "assemble", "transcript", "expression"]
    RETURN_TYPES = ("GTF", "ABUNDANCE")
    RETURN_NAMES = ("transcripts_gtf", "gene_abundance")
    REQUIRED_EXECUTABLES = ["stringtie"]
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/stringtie/"
    VERSION = "2.2.3"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "stringtie",
            str(inputs.get("bam", "")),
            "-G", str(inputs.get("gtf", "")),
            "-o", f"{inputs.get('output', '.')}/transcripts.gtf",
            "-A", f"{inputs.get('output', '.')}/gene_abundance.tab",
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
                "fr": ("BOOLEAN", {"default": True, "label": "Forward Strand (fr)", "advanced": True}),
                "rf": ("BOOLEAN", {"default": False, "label": "Reverse Strand (rf)", "advanced": True}),
                "min_isoform_fraction": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.01, "label": "Min Isoform Fraction", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
