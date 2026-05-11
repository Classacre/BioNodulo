"""Phylogenetic analysis nodes for BioNodulo.

Provides nodes for multiple sequence alignment (MAFFT, Clustal-Omega)
and tree inference (IQ-TREE, FastTree, RAxML).
"""
from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


class MAFFTNode(CommandNode):
    """Multiple sequence alignment with MAFFT."""
    NODE_ID = "mafft"
    DISPLAY_NAME = "MAFFT"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Multiple sequence alignment with MAFFT (fast FFT-based)"
    SEARCH_ALIASES = ["mafft", "align", "msa", "multiple alignment"]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["mafft"]
    DOCUMENTATION_URL = "https://mafft.cbrc.jp/alignment/software/"
    VERSION = "7.520"
    SHELL = True
    COMMAND = [
        "mafft",
        "--thread", "{inputs.threads}",
        "{inputs.input}",
        ">", "{output}/alignment.fasta",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Input sequences FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "strategy": ("STRING", {"default": "auto", "description": "Alignment strategy: auto, linsi, ginsi, einsi"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        strategy = inputs.get("strategy", "auto")
        cmd = ["mafft", "--thread", str(inputs.get("threads", 4))]
        if strategy != "auto":
            flag = f"--{strategy}" if not strategy.startswith("--") else strategy
            cmd.append(flag)
        cmd.extend([str(inputs.get("input", "")), ">", f"{inputs.get('output', '.')}/alignment.fasta"])
        return cmd


class ClustalONode(CommandNode):
    """Multiple sequence alignment with Clustal Omega."""
    NODE_ID = "clustalo"
    DISPLAY_NAME = "Clustal Omega"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Scalable multiple protein sequence alignment"
    SEARCH_ALIASES = ["clustal", "clustalo", "clustal omega", "msa"]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["clustalo"]
    DOCUMENTATION_URL = "http://www.clustal.org/omega/"
    VERSION = "1.2.4"
    COMMAND = [
        "clustalo",
        "-i", "{inputs.input}",
        "-o", "{output}/alignment.fasta",
        "--threads={inputs.threads}",
        "--force",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Input sequences FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "outfmt": ("STRING", {"default": "fasta"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class IQTREENode(CommandNode):
    """Phylogenetic tree inference with IQ-TREE."""
    NODE_ID = "iqtree"
    DISPLAY_NAME = "IQ-TREE"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Efficient phylogenomic inference with maximum likelihood"
    SEARCH_ALIASES = ["iqtree", "maximum likelihood", "tree", "phylogeny"]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("tree",)
    REQUIRED_EXECUTABLES = ["iqtree"]
    DOCUMENTATION_URL = "http://www.iqtree.org/"
    VERSION = "2.3.4"
    COMMAND = [
        "iqtree2" if False else "iqtree",
        "-s", "{inputs.alignment}",
        "-nt", "{inputs.threads}",
        "-pre", "{output}/tree",
        "-m", "{inputs.model}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("ALIGNMENT", {"description": "Multiple sequence alignment"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "model": ("STRING", {"default": "MFP", "description": "Substitution model: MFP, GTR+I+G, LG+I+G, etc."}),
                "bootstrap": ("INT", {"default": 1000, "min": 0, "max": 10000, "step": 100, "display": "slider"}),
                "alrt": ("INT", {"default": 1000, "min": 0}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "iqtree2" if False else "iqtree",
            "-s", str(inputs.get("alignment", "")),
            "-nt", str(inputs.get("threads", 4)),
            "-pre", f"{inputs.get('output', '.')}/tree",
            "-m", str(inputs.get("model", "MFP")),
        ]
        if inputs.get("bootstrap"):
            cmd.extend(["-bb", str(inputs["bootstrap"])])
        if inputs.get("alrt"):
            cmd.extend(["-alrt", str(inputs["alrt"])])
        return cmd


class FastTreeNode(CommandNode):
    """Fast phylogenetic tree inference with FastTree."""
    NODE_ID = "fasttree"
    DISPLAY_NAME = "FastTree"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Approximately maximum-likelihood phylogenetic tree inference"
    SEARCH_ALIASES = ["fasttree", "quick tree", "approximate ml"]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("tree",)
    REQUIRED_EXECUTABLES = ["FastTree"]
    DOCUMENTATION_URL = "http://www.microbesonline.org/fasttree/"
    VERSION = "2.1.11"
    SHELL = True
    COMMAND = [
        "FastTree",
        "-gamma",
        "-boot", "100",
        "{inputs.alignment}",
        ">", "{output}/tree.nwk",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("ALIGNMENT", {"description": "Multiple sequence alignment (protein or nucleotide)"}),
            },
            "optional": {
                "nucleotide": ("BOOLEAN", {"default": False, "description": "Use nucleotide model instead of protein"}),
                "gtr": ("BOOLEAN", {"default": False, "description": "Use GTR model for nucleotides"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["FastTree"]
        if inputs.get("nucleotide"):
            cmd.append("-nt")
        if inputs.get("gtr"):
            cmd.append("-gtr")
        cmd.extend(["-gamma", "-boot", "100"])
        cmd.extend([str(inputs.get("alignment", "")), ">", f"{inputs.get('output', '.')}/tree.nwk"])
        return cmd


class RAxMLNode(CommandNode):
    """Phylogenetic tree inference with RAxML."""
    NODE_ID = "raxml"
    DISPLAY_NAME = "RAxML"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Maximum likelihood phylogenetic inference with RAxML"
    SEARCH_ALIASES = ["raxml", "maximum likelihood", "tree", "evolution"]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("tree",)
    REQUIRED_EXECUTABLES = ["raxmlHPC"]
    DOCUMENTATION_URL = "https://github.com/stamatak/standard-RAxML"
    VERSION = "8.2.12"
    COMMAND = [
        "raxmlHPC",
        "-s", "{inputs.alignment}",
        "-n", "{inputs.prefix}",
        "-m", "{inputs.model}",
        "-p", "12345",
        "-T", "{inputs.threads}",
        "-w", "{output}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("ALIGNMENT", {"description": "Phylip-formatted alignment"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
                "model": ("STRING", {"default": "GTRGAMMA", "description": "Substitution model"}),
                "prefix": ("STRING", {"default": "tree"}),
            },
            "optional": {
                "bootstrap": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "raxmlHPC",
            "-s", str(inputs.get("alignment", "")),
            "-n", str(inputs.get("prefix", "tree")),
            "-m", str(inputs.get("model", "GTRGAMMA")),
            "-p", "12345",
            "-T", str(inputs.get("threads", 4)),
            "-w", str(inputs.get("output", ".")),
        ]
        if inputs.get("bootstrap"):
            cmd.extend(["-b", "12345", "-N", "100"])
        return cmd
