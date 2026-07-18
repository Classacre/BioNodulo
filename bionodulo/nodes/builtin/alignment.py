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

class Bowtie2BuildNode(CommandNode):
    """Build Bowtie2 index."""
    NODE_ID = "bowtie2_build"
    DISPLAY_NAME = "Bowtie2 Build"
    REQUIRED_CONDA_PACKAGES = ['bowtie2']
    CATEGORY = "alignment"
    DESCRIPTION = "Build Bowtie2 index from a reference FASTA"
    SEARCH_ALIASES = ["bowtie2", "build", "index"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("index",)
    REQUIRED_EXECUTABLES = ["bowtie2-build"]
    DOCUMENTATION_URL = "https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml"
    VERSION = "2.5.5"
    COMMAND = [
        "bowtie2-build",
        "--threads", "{inputs.threads}",
        "{inputs.reference}",
        "{output}/index",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        """Content-addressed id for this Bowtie2 index (perf §15 #3 / §40).

        Same-genome bowtie2 indexes are shared platform-wide via the reference
        cache — the first build publishes it, later runs (any user) stage it
        instead of rebuilding. Keys on the FASTA identity + bowtie2 version.
        """
        from bionodulo.execution import reference_cache as _rc

        return _rc.compute_ref_id("bowtie2", [
            _rc.file_identity(inputs.get("reference", "")),
            f"bowtie2-{cls.VERSION}",
        ])


class Bowtie2AlignNode(CommandNode):
    """Align reads with Bowtie2."""
    NODE_ID = "bowtie2_align"
    DISPLAY_NAME = "Bowtie2 Align"
    REQUIRED_CONDA_PACKAGES = ['bowtie2']
    CATEGORY = "alignment"
    DESCRIPTION = "Align paired-end reads with Bowtie2"
    SEARCH_ALIASES = ["bowtie2", "align", "mapper"]
    RETURN_TYPES = ("SAM",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["bowtie2"]
    DOCUMENTATION_URL = "https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml"
    VERSION = "2.5.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bowtie2",
            "-p", str(inputs.get("threads", 8)),
            "-x", str(inputs.get("index", "")),
        ]
        r1, r2 = _split_reads(inputs)
        if r1 and r2:
            cmd.extend(["-1", str(r1), "-2", str(r2)])
        elif r1:
            cmd.extend(["-U", str(r1)])
        if inputs.get("rg_id"):
            cmd.extend(["--rg-id", str(inputs["rg_id"])])
        if inputs.get("rg_sample"):
            cmd.extend(["--rg", f"SM:{inputs['rg_sample']}"])
        if inputs.get("very_sensitive"):
            cmd.append("--very-sensitive")
        if inputs.get("no_mixed"):
            cmd.append("--no-mixed")
        cmd.extend(["-S", f"{inputs.get('output', '.')}/alignment.sam"])
        return cmd

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for Bowtie2."""
        _inject_read_aliases(kwargs)
        return await super().run(**kwargs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "index": ("INDEX_DIR", {"description": "Bowtie2 index prefix"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "reads": ("FASTQ_LIST", {"description": "Paired-end FASTQ reads [R1, R2]"}),
                "r1": ("FASTQ", {"description": "Forward reads (R1)"}),
                "r2": ("FASTQ", {"description": "Reverse reads (R2)"}),
                "rg_id": ("STRING", {"default": "1", "label": "Read Group ID"}),
                "rg_sample": ("STRING", {"default": "sample", "label": "Sample Name"}),
                "very_sensitive": ("BOOLEAN", {"default": False, "label": "Very Sensitive", "advanced": True}),
                "no_mixed": ("BOOLEAN", {"default": False, "label": "No Mixed", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class Bowtie2IndexNode(CommandNode):
    """Inspect Bowtie2 index."""
    NODE_ID = "bowtie2_inspect"
    DISPLAY_NAME = "Bowtie2 Inspect"
    REQUIRED_CONDA_PACKAGES = ['bowtie2']
    CATEGORY = "alignment"
    DESCRIPTION = "Inspect a Bowtie2 index and extract reference sequences"
    SEARCH_ALIASES = ["bowtie2", "inspect", "index"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("reference",)
    REQUIRED_EXECUTABLES = ["bowtie2-inspect"]
    VERSION = "2.5.3"
    SHELL = True
    COMMAND = [
        "bowtie2-inspect",
        "{inputs.index}",
        ">", "{output}/reference.fasta",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "index": ("INDEX_DIR", {"description": "Bowtie2 index prefix"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


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

class HISAT2BuildNode(CommandNode):
    """Build HISAT2 index."""
    NODE_ID = "hisat2_build"
    DISPLAY_NAME = "HISAT2 Build"
    CATEGORY = "alignment"
    DESCRIPTION = "Build HISAT2 spliced alignment index"
    SEARCH_ALIASES = ["hisat2", "index", "spliced", "rna"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("index",)
    REQUIRED_EXECUTABLES = ["hisat2-build"]
    REQUIRED_CONDA_PACKAGES = ['hisat2']
    DOCUMENTATION_URL = "https://daehwankimlab.github.io/hisat2/"
    VERSION = "2.2.2"
    COMMAND = [
        "hisat2-build",
        "-p", "{inputs.threads}",
        "{inputs.reference}",
        "{output}/index",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        """Content-addressed id for this HISAT2 index (perf §15 #3 / §40) —
        shared platform-wide; keys on the FASTA identity + hisat2 version."""
        from bionodulo.execution import reference_cache as _rc

        return _rc.compute_ref_id("hisat2", [
            _rc.file_identity(inputs.get("reference", "")),
            f"hisat2-{cls.VERSION}",
        ])


class HISAT2AlignNode(CommandNode):
    """Align RNA-seq reads with HISAT2."""
    NODE_ID = "hisat2_align"
    DISPLAY_NAME = "HISAT2 Align"
    REQUIRED_CONDA_PACKAGES = ['hisat2']
    CATEGORY = "alignment"
    DESCRIPTION = "Align RNA-seq reads with splice-aware HISAT2"
    SEARCH_ALIASES = ["hisat2", "align", "rna-seq", "spliced"]
    RETURN_TYPES = ("SAM",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["hisat2"]
    DOCUMENTATION_URL = "https://daehwankimlab.github.io/hisat2/"
    VERSION = "2.2.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "hisat2",
            "-p", str(inputs.get("threads", 8)),
            "-x", str(inputs.get("index", "")),
        ]
        r1, r2 = _split_reads(inputs)
        if r1 and r2:
            cmd.extend(["-1", str(r1), "-2", str(r2)])
        elif r1:
            cmd.extend(["-U", str(r1)])
        if inputs.get("rg_id"):
            cmd.extend(["--rg-id", str(inputs["rg_id"])])
        if inputs.get("rg_sample"):
            cmd.extend(["--rg", f"SM:{inputs['rg_sample']}"])
        if inputs.get("dta"):
            cmd.append("--dta")
        if inputs.get("no_softclip"):
            cmd.append("--no-softclip")
        cmd.extend(["-S", f"{inputs.get('output', '.')}/alignment.sam"])
        return cmd

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for HISAT2."""
        _inject_read_aliases(kwargs)
        return await super().run(**kwargs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "index": ("INDEX_DIR", {"description": "HISAT2 index prefix"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "reads": ("FASTQ_LIST", {"description": "Paired-end FASTQ reads [R1, R2]"}),
                "r1": ("FASTQ", {"description": "Forward reads (R1)"}),
                "r2": ("FASTQ", {"description": "Reverse reads (R2)"}),
                "rg_id": ("STRING", {"default": "1", "label": "Read Group ID"}),
                "rg_sample": ("STRING", {"default": "sample", "label": "Sample Name"}),
                "dta": ("BOOLEAN", {"default": True, "description": "Report alignments for StringTie", "advanced": True}),
                "no_softclip": ("BOOLEAN", {"default": False, "label": "No Softclip", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


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
