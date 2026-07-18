"""Sequence alignment nodes for BioNodulo.

Provides nodes for BWA, Bowtie2, Minimap2, HISAT2, and STAR alignment
tools including index building and read mapping.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Optional

from bionodulo.nodes.command_node import CommandNode


def _split_reads(inputs: dict[str, Any]) -> tuple[Any, Any]:
    """Return R1/R2 from a FASTQ list or explicit r1/r2 aliases."""
    reads = inputs.get("reads", [])
    if isinstance(reads, str):
        reads = [reads]
    r1 = reads[0] if len(reads) > 0 else inputs.get("r1", "")
    r2 = reads[1] if len(reads) > 1 else inputs.get("r2", "")
    return r1, r2


def _inject_read_aliases(inputs: dict[str, Any]) -> None:
    """Populate r1/r2 aliases from reads when callers use FASTQ_LIST inputs."""
    r1, r2 = _split_reads(inputs)
    if r1:
        inputs["r1"] = r1
    if r2:
        inputs["r2"] = r2


# ── BWA ────────────────────────────────────────────────────────────
# The three stable BWA IDs live in alignment_family/*.py. Keep aliases here
# for callers that imported the old monolithic module; the registry indexes the
# focused modules by each class's own ``__module__``.
from bionodulo.nodes.builtin.alignment_family.index import BWAIndexNode  # noqa: E402,F401
from bionodulo.nodes.builtin.alignment_family.index_dir import BWAIndexDirNode  # noqa: E402,F401
from bionodulo.nodes.builtin.alignment_family.mem import BWAMemNode  # noqa: E402,F401


# ── Bowtie2 ────────────────────────────────────────────────────────

# Stable Bowtie2 IDs live in focused modules. Keep aliases here for callers
# that imported the old monolithic module.
from bionodulo.nodes.builtin.alignment_family.bowtie2_align import Bowtie2AlignNode  # noqa: E402,F401
from bionodulo.nodes.builtin.alignment_family.bowtie2_build import Bowtie2BuildNode  # noqa: E402,F401
from bionodulo.nodes.builtin.alignment_family.bowtie2_inspect import Bowtie2IndexNode  # noqa: E402,F401


# ── Minimap2 ───────────────────────────────────────────────────────

class Minimap2IndexNode(CommandNode):
    """Build Minimap2 index."""
    NODE_ID = "minimap2_index"
    DISPLAY_NAME = "Minimap2 Index"
    REQUIRED_CONDA_PACKAGES = ['minimap2']
    CATEGORY = "alignment"
    DESCRIPTION = "Build Minimap2 index for long-read alignment"
    SEARCH_ALIASES = ["minimap2", "index", "long reads"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("index",)
    REQUIRED_EXECUTABLES = ["minimap2"]
    DOCUMENTATION_URL = "https://lh3.github.io/minimap2/"
    VERSION = "2.30"
    COMMAND = [
        "minimap2",
        "-d", "{output}/index.mmi",
        "{inputs.reference}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference FASTA"}),
            },
            "optional": {
                "preset": ("STRING", {"default": "map-ont"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class Minimap2AlignNode(CommandNode):
    """Align reads with Minimap2."""
    NODE_ID = "minimap2_align"
    DISPLAY_NAME = "Minimap2 Align"
    REQUIRED_CONDA_PACKAGES = ['minimap2']
    CATEGORY = "alignment"
    DESCRIPTION = "Align reads to a reference with Minimap2 (long or short reads)"
    SEARCH_ALIASES = ["minimap2", "align", "long read", "pacbio", "ont"]
    RETURN_TYPES = ("SAM",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["minimap2"]
    DOCUMENTATION_URL = "https://lh3.github.io/minimap2/"
    VERSION = "2.30"
    SHELL = True
    COMMAND = [
        "minimap2",
        "-ax", "{inputs.preset}",
        "-t", "{inputs.threads}",
        "{inputs.reference}",
        "{inputs.reads}",
        ">", "{output}/alignment.sam",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "FASTQ reads (single-end or long reads)"}),
                "reference": ("FASTA", {"description": "Reference FASTA or Minimap2 index"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "preset": ("STRING", {"default": "sr"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


# ── HISAT2 ─────────────────────────────────────────────────────────

from bionodulo.nodes.builtin.alignment_family.hisat2_align import HISAT2AlignNode  # noqa: E402,F401
from bionodulo.nodes.builtin.alignment_family.hisat2_build import HISAT2BuildNode  # noqa: E402,F401


# ── STAR ───────────────────────────────────────────────────────────

class STARIndexNode(CommandNode):
    """Build STAR genome index."""
    NODE_ID = "star_index"
    DISPLAY_NAME = "STAR Index"
    REQUIRED_CONDA_PACKAGES = ['star']
    CATEGORY = "alignment"
    DESCRIPTION = "Build STAR splice-aware genome index for RNA-seq"
    SEARCH_ALIASES = ["star", "index", "genome", "rna-seq"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("index",)
    REQUIRED_EXECUTABLES = ["STAR"]
    DOCUMENTATION_URL = "https://github.com/alexdobin/STAR"
    VERSION = "2.7.11b"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "STAR",
            "--runMode", "genomeGenerate",
            "--genomeDir", str(inputs.get("output", ".")),
            "--genomeFastaFiles", str(inputs.get("reference", "")),
            "--sjdbGTFfile", str(inputs.get("gtf", "")),
            "--runThreadN", str(inputs.get("threads", 8)),
        ]
        if inputs.get("genome_sa_index_nbases"):
            cmd.extend(["--genomeSAindexNbases", str(inputs["genome_sa_index_nbases"])])
        if inputs.get("sjdb_overhang"):
            cmd.extend(["--sjdbOverhang", str(inputs["sjdb_overhang"])])
        return cmd

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        """Content-addressed id for this STAR index (perf §15 #3).

        Building a human STAR index is ~33 min / 35 GB RAM (measured §16.2).
        When REFERENCE_CACHE_BUCKET is set, CommandNode.run stages a pre-built
        index from the shared cache (~5 min download) instead of rebuilding, and
        publishes a freshly-built one for every later run (any user). The id
        keys on the FASTA + GTF identity, STAR version, and index params — so the
        same genome+annotation shares one cached index platform-wide.
        """
        from bionodulo.execution import reference_cache as _rc

        return _rc.compute_ref_id("star", [
            _rc.file_identity(inputs.get("reference", "")),
            _rc.file_identity(inputs.get("gtf", "")),
            f"STAR{cls.VERSION}",
            f"sa{inputs.get('genome_sa_index_nbases', 14)}",
            f"oh{inputs.get('sjdb_overhang', 100)}",
        ])

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference genome FASTA"}),
                "gtf": ("GTF", {"description": "Gene annotation GTF"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "genome_sa_index_nbases": ("INT", {"default": 14}),
                "sjdb_overhang": ("INT", {"default": 100, "min": 1, "label": "SJDB Overhang", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class STARAlignNode(CommandNode):
    """Align RNA-seq reads with STAR."""
    NODE_ID = "star_align"
    DISPLAY_NAME = "STAR Align"
    REQUIRED_CONDA_PACKAGES = ['star']
    CATEGORY = "alignment"
    DESCRIPTION = "Align RNA-seq reads with 2-pass STAR"
    SEARCH_ALIASES = ["star", "align", "rna-seq"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["STAR"]
    DOCUMENTATION_URL = "https://github.com/alexdobin/STAR"
    VERSION = "2.7.11b"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        r1, r2 = _split_reads(inputs)
        cmd = [
            "STAR",
            "--genomeDir", str(inputs.get("index", "")),
            "--readFilesIn", str(r1),
        ]
        if r2:
            cmd.append(str(r2))
        # Compression detection for readFilesCommand
        if str(r1).endswith(".gz"):
            cmd.extend(["--readFilesCommand", "zcat"])
        elif str(r1).endswith(".bz2"):
            cmd.extend(["--readFilesCommand", "bzcat"])
        cmd.extend([
            "--outFileNamePrefix", f"{inputs.get('output', '.')}/",
            "--outSAMtype", "BAM", "SortedByCoordinate",
            "--runThreadN", str(inputs.get("threads", 8)),
        ])
        if inputs.get("two_pass"):
            cmd.extend(["--twopassMode", "Basic"])
        if inputs.get("chim_segment_min"):
            cmd.extend(["--chimSegmentMin", str(inputs["chim_segment_min"])])
        return cmd

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        if result and isinstance(result, tuple):
            planned = Path(str(result[0]))
            actual = planned.parent / "Aligned.sortedByCoord.out.bam"
            if actual.exists():
                shutil.copy2(str(actual), str(planned))
        return result

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "Paired-end FASTQ reads [R1, R2]"}),
                "index": ("INDEX_DIR", {"description": "STAR genome index directory"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "two_pass": ("BOOLEAN", {"default": True, "description": "Enable 2-pass mode", "advanced": True}),
                "chim_segment_min": ("INT", {"default": 0, "min": 0, "label": "Chimera Min Segment", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
