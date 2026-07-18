"""Genome assembly nodes for BioNodulo.

Provides nodes for long-read and hybrid genome assembly using Canu, Flye,
and Unicycler. Focused SPAdes, MEGAHIT, and QUAST adapters live in the
``assembly_family`` package.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.builtin.assembly_family.megahit import MEGAHITNode  # noqa: F401
from bionodulo.nodes.builtin.assembly_family.quast import QuastNode  # noqa: F401
from bionodulo.nodes.builtin.assembly_family.spades import SPAdesNode  # noqa: F401


class CanuNode(CommandNode):
    """De novo assembly with Canu (long reads)."""
    NODE_ID = "canu"
    DISPLAY_NAME = "Canu"
    REQUIRED_CONDA_PACKAGES = ['canu']
    CATEGORY = "assembly"
    DESCRIPTION = "Long-read assembler for PacBio and Oxford Nanopore"
    SEARCH_ALIASES = ["canu", "assemble", "long reads", "pacbio", "ont"]
    RETURN_TYPES = ("ASSEMBLY", "CONTIGS")
    RETURN_NAMES = ("assembly", "contigs")
    REQUIRED_EXECUTABLES = ["canu"]
    DOCUMENTATION_URL = "https://canu.readthedocs.io/"
    VERSION = "2.3"
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

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        od = Path(output_dir)
        return [
            od / cls.NODE_ID / "assembly.fasta",
            od / cls.NODE_ID / "contigs.fasta",
        ]

    async def run(self, **kwargs: Any) -> Any:
        """Run Canu and copy assembly files to planned paths."""
        result = await super().run(**kwargs)
        import shutil
        node_out = Path(kwargs["output_dir"])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        prefix = kwargs.get("prefix", "assembly")
        if outputs:
            outputs[0].parent.mkdir(parents=True, exist_ok=True)
            contigs = node_out / f"{prefix}.contigs.fasta"
            unitigs = node_out / f"{prefix}.unitigs.fasta"
            if contigs.exists() and len(outputs) > 0:
                shutil.copy2(str(contigs), str(outputs[0]))
            if unitigs.exists() and len(outputs) > 1:
                shutil.copy2(str(unitigs), str(outputs[1]))
        return result


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
    VERSION = "2.9.6"
    COMMAND = [
        "flye",
        "--{inputs.read_type}", "{inputs.reads}",
        "--out-dir", "{output}",
        "--threads", "{inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "Long reads FASTQ"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 64, "display": "slider"}),
                "read_type": ("STRING", {"default": "nano-hq"}),
            },
            "optional": {
                "genome_size": ("STRING", {"default": "5m", "description": "Estimated genome size"}),
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
        ]
        if inputs.get("genome_size"):
            cmd.extend(["--genome-size", str(inputs["genome_size"])])
        if inputs.get("iterations"):
            cmd.extend(["--iterations", str(inputs["iterations"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        od = Path(output_dir)
        return [od / cls.NODE_ID / "assembly.fasta"]

    async def run(self, **kwargs: Any) -> Any:
        """Run Flye and copy assembly to planned path."""
        result = await super().run(**kwargs)
        import shutil
        node_out = Path(kwargs["output_dir"])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        if outputs:
            outputs[0].parent.mkdir(parents=True, exist_ok=True)
            actual = node_out / "assembly.fasta"
            if actual.exists():
                shutil.copy2(str(actual), str(outputs[0]))
        return result


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
    VERSION = "0.5.1"
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
                "threads": ("INT", {"default": 16, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "reads": ("FASTQ_LIST", {"description": "Paired-end FASTQ reads [R1, R2]"}),
                "r1": ("FASTQ", {"description": "Forward Illumina reads"}),
                "r2": ("FASTQ", {"description": "Reverse Illumina reads"}),
                "long_reads": ("FASTQ", {"description": "Optional long reads for hybrid assembly"}),
                "mode": ("STRING", {"default": "normal"}),
                "unpaired": ("FASTQ", {"description": "Optional unpaired reads"}),
                "min_fasta_length": ("INT", {"default": 100, "min": 1}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for Unicycler, then copy output."""
        reads = kwargs.get("reads", [])
        if isinstance(reads, (list, tuple)) and len(reads) >= 2:
            kwargs["r1"] = reads[0]
            kwargs["r2"] = reads[1]
        result = await super().run(**kwargs)
        import shutil
        node_out = Path(kwargs["output_dir"])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        if outputs:
            outputs[0].parent.mkdir(parents=True, exist_ok=True)
            actual = node_out / "assembly.fasta"
            if actual.exists():
                shutil.copy2(str(actual), str(outputs[0]))
        return result

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
        if inputs.get("unpaired"):
            cmd.extend(["-s", str(inputs["unpaired"])])
        if inputs.get("min_fasta_length") is not None:
            cmd.extend(["--min_fasta_length", str(inputs["min_fasta_length"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        od = Path(output_dir)
        return [od / cls.NODE_ID / "assembly.fasta"]
