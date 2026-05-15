"""Genome assembly nodes for BioNodulo.

Provides nodes for de novo genome assembly using SPAdes, MEGAHIT,
Canu, Flye, Unicycler, and assembly quality assessment with QUAST.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class SPAdesNode(CommandNode):
    """De novo genome assembly with SPAdes."""
    NODE_ID = "spades"
    DISPLAY_NAME = "SPAdes"
    REQUIRED_CONDA_PACKAGES = ['spades']
    CATEGORY = "assembly"
    DESCRIPTION = "De novo genome assembler for single-cell and isolate data"
    SEARCH_ALIASES = ["spades", "assemble", "de novo", "genome"]
    RETURN_TYPES = ("ASSEMBLY", "CONTIGS")
    RETURN_NAMES = ("assembly", "contigs")
    REQUIRED_EXECUTABLES = ["spades.py"]
    DOCUMENTATION_URL = "https://cab.spbu.ru/software/spades/"
    VERSION = "3.15.5"
    COMMAND = [
        "spades.py",
        "-1", "{inputs.r1}",
        "-2", "{inputs.r2}",
        "-o", "{output}",
        "-t", "{inputs.threads}",
        "--memory", "{inputs.memory}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Forward reads (R1)"}),
                "r2": ("FASTQ", {"description": "Reverse reads (R2)"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "memory": ("INT", {"default": 128, "min": 1, "description": "Memory limit in GB"}),
                "careful": ("BOOLEAN", {"default": True, "description": "Reduce mismatch correction errors"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for SPAdes."""
        reads = kwargs.get("reads", [])
        if isinstance(reads, (list, tuple)) and len(reads) >= 2:
            kwargs["r1"] = reads[0]
            kwargs["r2"] = reads[1]
        return await super().run(**kwargs)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str) -> list:
        from pathlib import Path
        od = Path(output_dir)
        return [
            od / "scaffolds.fasta",
            od / "contigs.fasta",
        ]


class MEGAHITNode(CommandNode):
    """De novo assembly with MEGAHIT (metagenomics)."""
    NODE_ID = "megahit"
    DISPLAY_NAME = "MEGAHIT"
    REQUIRED_CONDA_PACKAGES = ['megahit']
    CATEGORY = "assembly"
    DESCRIPTION = "Ultra-fast metagenome assembler via succinct de Bruijn graph"
    SEARCH_ALIASES = ["megahit", "assemble", "metagenome", "macro"]
    RETURN_TYPES = ("CONTIGS",)
    RETURN_NAMES = ("contigs",)
    REQUIRED_EXECUTABLES = ["megahit"]
    DOCUMENTATION_URL = "https://github.com/voutcn/megahit"
    VERSION = "1.2.9"
    COMMAND = [
        "megahit",
        "-1", "{inputs.r1}",
        "-2", "{inputs.r2}",
        "-o", "{output}",
        "-t", "{inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Forward reads (R1)"}),
                "r2": ("FASTQ", {"description": "Reverse reads (R2)"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "min_contig_len": ("INT", {"default": 200, "min": 1}),
                "k_list": ("STRING", {"default": "21,29,39,59,79,99,119,141"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for MEGAHIT."""
        reads = kwargs.get("reads", [])
        if isinstance(reads, (list, tuple)) and len(reads) >= 2:
            kwargs["r1"] = reads[0]
            kwargs["r2"] = reads[1]
        return await super().run(**kwargs)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str) -> list:
        from pathlib import Path
        od = Path(output_dir)
        return [od / "final.contigs.fa"]


class CanuNode(CommandNode):
    """De novo assembly with Canu (long reads)."""
    NODE_ID = "canu"
    DISPLAY_NAME = "Canu"
    REQUIRED_CONDA_PACKAGES = ['canu']
    CATEGORY = "assembly"
    DESCRIPTION = "Long-read assembler for PacBio and Oxford Nanopore"
    SEARCH_ALIASES = ["canu", "assemble", "long reads", "pacbio", "ont"]
    RETURN_TYPES = ("ASSEMBLY", "CONTIGS")
    RETURN_NAMES = ("assembly", "unitigs")
    REQUIRED_EXECUTABLES = ["canu"]
    DOCUMENTATION_URL = "https://canu.readthedocs.io/"
    VERSION = "2.2"
    COMMAND = [
        "canu",
        "-p", "{inputs.prefix}",
        "-d", "{output}",
        "genomeSize={inputs.genome_size}",
        "-pacbio-hifi", "{inputs.reads}",
        "useGrid=false",
        "maxThreads={inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "PacBio HiFi or ONT reads"}),
                "genome_size": ("STRING", {"default": "5m", "description": "Estimated genome size (e.g., 5m, 3.2g)"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 64, "display": "slider"}),
                "prefix": ("STRING", {"default": "assembly"}),
            },
            "optional": {
                "read_type": ("STRING", {"default": "pacbio-hifi"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        read_type = inputs.get("read_type", "pacbio-hifi")
        return [
            "canu",
            "-p", str(inputs.get("prefix", "assembly")),
            "-d", str(inputs.get("output", ".")),
            f"genomeSize={inputs.get('genome_size', '5m')}",
            f"-{read_type}", str(inputs.get("reads", "")),
            "useGrid=false",
            f"maxThreads={inputs.get('threads', 16)}",
        ]


class FlyeNode(CommandNode):
    """De novo assembly with Flye (long reads)."""
    NODE_ID = "flye"
    DISPLAY_NAME = "Flye"
    REQUIRED_CONDA_PACKAGES = ['flye']
    CATEGORY = "assembly"
    DESCRIPTION = "De novo assembly for single-molecule sequencing reads"
    SEARCH_ALIASES = ["flye", "assemble", "long reads", "nanopore", "repeat graph"]
    RETURN_TYPES = ("ASSEMBLY",)
    RETURN_NAMES = ("assembly",)
    REQUIRED_EXECUTABLES = ["flye"]
    DOCUMENTATION_URL = "https://github.com/fenderglass/Flye"
    VERSION = "2.9.3"
    COMMAND = [
        "flye",
        "--{inputs.read_type}", "{inputs.reads}",
        "--out-dir", "{output}",
        "--threads", "{inputs.threads}",
        "--genome-size", "{inputs.genome_size}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "Long reads FASTQ"}),
                "genome_size": ("STRING", {"default": "5m", "description": "Estimated genome size"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 64, "display": "slider"}),
                "read_type": ("STRING", {"default": "nano-hq"}),
            },
            "optional": {
                "iterations": ("INT", {"default": 1, "min": 0, "max": 5}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "flye",
            f"--{inputs.get('read_type', 'nano-hq')}", str(inputs.get("reads", "")),
            "--out-dir", str(inputs.get("output", ".")),
            "--threads", str(inputs.get("threads", 16)),
            "--genome-size", str(inputs.get("genome_size", "5m")),
        ]
        if inputs.get("iterations"):
            cmd.extend(["--iterations", str(inputs["iterations"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str) -> list:
        from pathlib import Path
        od = Path(output_dir)
        return [od / "assembly.fasta"]


class UnicyclerNode(CommandNode):
    """Bacterial genome assembly with Unicycler."""
    NODE_ID = "unicycler"
    DISPLAY_NAME = "Unicycler"
    REQUIRED_CONDA_PACKAGES = ['unicycler']
    CATEGORY = "assembly"
    DESCRIPTION = "Bacterial genome assembly from Illumina reads with optional long reads"
    SEARCH_ALIASES = ["unicycler", "assemble", "bacteria", "hybrid"]
    RETURN_TYPES = ("ASSEMBLY",)
    RETURN_NAMES = ("assembly",)
    REQUIRED_EXECUTABLES = ["unicycler"]
    DOCUMENTATION_URL = "https://github.com/rrwick/Unicycler"
    VERSION = "0.5.0"
    COMMAND = [
        "unicycler",
        "-1", "{inputs.r1}",
        "-2", "{inputs.r2}",
        "-o", "{output}",
        "-t", "{inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Forward Illumina reads"}),
                "r2": ("FASTQ", {"description": "Reverse Illumina reads"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "long_reads": ("FASTQ", {"description": "Optional long reads for hybrid assembly"}),
                "mode": ("STRING", {"default": "normal"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for Unicycler."""
        reads = kwargs.get("reads", [])
        if isinstance(reads, (list, tuple)) and len(reads) >= 2:
            kwargs["r1"] = reads[0]
            kwargs["r2"] = reads[1]
        return await super().run(**kwargs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "unicycler",
            "-1", str(inputs.get("r1", "")),
            "-2", str(inputs.get("r2", "")),
            "-o", str(inputs.get("output", ".")),
            "-t", str(inputs.get("threads", 16)),
            "--mode", str(inputs.get("mode", "normal")),
        ]
        if inputs.get("long_reads"):
            cmd.extend(["-l", str(inputs["long_reads"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str) -> list:
        from pathlib import Path
        od = Path(output_dir)
        return [od / "assembly.fasta"]


class QuastNode(CommandNode):
    """Assess assembly quality with QUAST."""
    NODE_ID = "quast"
    DISPLAY_NAME = "QUAST"
    REQUIRED_CONDA_PACKAGES = ['quast']
    CATEGORY = "assembly"
    DESCRIPTION = "Quality Assessment Tool for Genome Assemblies"
    SEARCH_ALIASES = ["quast", "quality", "assembly qc", "assess"]
    RETURN_TYPES = ("HTML_REPORT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["quast"]
    DOCUMENTATION_URL = "https://quast.sourceforge.net/"
    VERSION = "5.2.0"
    COMMAND = [
        "quast",
        "{inputs.assembly}",
        "-o", "{output}",
        "-t", "{inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly": ("ASSEMBLY", {"description": "Assembly FASTA file(s)"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "reference": ("FASTA", {"description": "Optional reference for comparison"}),
                "gff": ("GFF", {"description": "Optional gene annotations"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
