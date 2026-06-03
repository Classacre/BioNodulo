"""Phylogenetic analysis nodes for BioNodulo.

Provides nodes for multiple sequence alignment (MAFFT, Clustal-Omega)
and tree inference (IQ-TREE, FastTree, RAxML).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class MAFFTNode(CommandNode):
    """Multiple sequence alignment with MAFFT."""
    NODE_ID = "mafft"
    DISPLAY_NAME = "MAFFT"
    REQUIRED_CONDA_PACKAGES = ['mafft']
    CATEGORY = "phylogeny"
    DESCRIPTION = "Multiple sequence alignment with MAFFT (fast FFT-based)"
    SEARCH_ALIASES = ["mafft", "align", "msa", "multiple alignment"]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["mafft"]
    DOCUMENTATION_URL = "https://mafft.cbrc.jp/alignment/software/"
    VERSION = "7.520"
    COMMAND = [
        "mafft",
        "--thread", "{inputs.threads}",
        "{inputs.input}",
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
        flag = f"--{strategy}" if not strategy.startswith("--") else strategy
        cmd.append(flag)
        cmd.append(str(inputs.get("input", "")))
        return cmd

    async def run(self, **kwargs: Any) -> Any:
        """Run MAFFT and capture stdout to the output file."""
        import shutil
        from pathlib import Path

        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")

        # Run the command (stdout is captured to stdout.log by subprocess_runner)
        result = await super().run(**kwargs)

        # Copy stdout.log to the expected output path
        if output_dir:
            stdout_log = Path(output_dir) / "stdout.log"
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if stdout_log.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(stdout_log), str(target))

        return result


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
    REQUIRED_CONDA_PACKAGES = ['clustal-omega']
    DOCUMENTATION_URL = "http://www.clustal.org/omega/"
    VERSION = "1.2.4"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "clustalo",
            "-i", str(inputs.get("input", "")),
            "-o", f"{inputs.get('output', '.')}/alignment.fasta",
            "--threads", str(inputs.get("threads", 4)),
            "--force",
        ]
        if inputs.get("outfmt"):
            cmd.extend(["--outfmt", str(inputs["outfmt"])])
        return cmd

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


class MUSCLENode(CommandNode):
    """Multiple sequence alignment with MUSCLE."""

    NODE_ID = "muscle"
    DISPLAY_NAME = "MUSCLE"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Multiple sequence alignment with MUSCLE, especially for protein sequences."
    SEARCH_ALIASES = ["muscle", "align", "msa", "multiple alignment", "protein alignment"]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["muscle"]
    REQUIRED_CONDA_PACKAGES = ["muscle"]
    DOCUMENTATION_URL = "https://drive5.com/muscle/"
    VERSION = "5.3"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequences": ("FASTA", {"description": "Input sequences FASTA"}),
            },
            "optional": {
                "maxiters": ("INT", {"default": 0, "min": 0, "description": "Maximum refinement iterations; 0 uses MUSCLE default"}),
                "diags": ("BOOLEAN", {"default": False, "description": "Use diagonal optimization for similar sequences"}),
                "stable": ("BOOLEAN", {"default": False, "description": "Preserve input sequence order in output"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "muscle",
            "-align",
            str(inputs.get("sequences", "")),
            "-output",
            f"{inputs.get('output', '.')}/alignment.aln.fasta",
        ]
        if inputs.get("maxiters"):
            cmd.extend(["-maxiters", str(inputs["maxiters"])])
        if inputs.get("diags"):
            cmd.append("-diags")
        if inputs.get("stable"):
            cmd.append("-stable")
        return cmd


class TrimAlNode(CommandNode):
    """Automated multiple sequence alignment trimming with trimAl."""

    NODE_ID = "trimal"
    DISPLAY_NAME = "trimAl"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Automated trimming of multiple sequence alignments before tree inference."
    SEARCH_ALIASES = ["trimal", "trimAl", "alignment trimming", "msa trim", "phylogeny"]
    RETURN_TYPES = ("FASTA", "STATS_FILE")
    RETURN_NAMES = ("trimmed", "stats")
    REQUIRED_EXECUTABLES = ["trimal"]
    REQUIRED_CONDA_PACKAGES = ["trimal"]
    DOCUMENTATION_URL = "http://trimal.cgenomics.org/"
    VERSION = "1.4.1"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("ALIGNMENT", {"description": "Input multiple sequence alignment"}),
            },
            "optional": {
                "automated": (
                    "STRING",
                    {
                        "default": "automated1",
                        "options": ["automated1", "strict", "strictplus", "gappyout"],
                        "description": "trimAl automated trimming strategy",
                    },
                ),
                "fasta_output": ("BOOLEAN", {"default": True, "description": "Write FASTA-formatted trimmed alignment"}),
                "htmlout": ("BOOLEAN", {"default": False, "description": "Also write an HTML trimming report"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        automated = str(inputs.get("automated", "automated1") or "automated1")
        if automated not in {"automated1", "strict", "strictplus", "gappyout"}:
            raise ValueError(f"Unsupported trimAl automated mode: {automated}")

        cmd = [
            "trimal",
            "-in",
            str(inputs.get("alignment", "")),
            "-out",
            f"{out_dir}/trimmed.fasta",
            f"-{automated}",
        ]
        if inputs.get("fasta_output", True):
            cmd.append("-fasta")
        if inputs.get("htmlout"):
            cmd.extend(["-htmlout", f"{out_dir}/stats.html"])
        return cmd


class IQTREENode(CommandNode):
    """Phylogenetic tree inference with IQ-TREE."""
    NODE_ID = "iqtree"
    DISPLAY_NAME = "IQ-TREE"
    REQUIRED_CONDA_PACKAGES = ['iqtree']
    CATEGORY = "phylogeny"
    DESCRIPTION = "Efficient phylogenomic inference with maximum likelihood"
    SEARCH_ALIASES = ["iqtree", "maximum likelihood", "tree", "phylogeny"]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("tree",)
    REQUIRED_EXECUTABLES = ["iqtree"]
    DOCUMENTATION_URL = "http://www.iqtree.org/"
    VERSION = "2.3.4"
    COMMAND = [
        "iqtree",
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
            "iqtree",
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
    REQUIRED_CONDA_PACKAGES = ['fasttree']
    DOCUMENTATION_URL = "http://www.microbesonline.org/fasttree/"
    VERSION = "2.1.11"
    COMMAND = [
        "FastTree",
        "-gamma",
        "-boot", "100",
        "{inputs.alignment}",
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
        cmd.append(str(inputs.get("alignment", "")))
        return cmd

    async def run(self, **kwargs: Any) -> Any:
        """Run FastTree and capture stdout to the output file."""
        import shutil
        from pathlib import Path

        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")

        result = await super().run(**kwargs)

        if output_dir:
            stdout_log = Path(output_dir) / "stdout.log"
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if stdout_log.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(stdout_log), str(target))

        return result


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
    REQUIRED_CONDA_PACKAGES = ['raxml']
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
            "-w", os.path.abspath(str(inputs.get("output", "."))),
        ]
        if inputs.get("bootstrap"):
            cmd.extend(["-b", "12345", "-#", "100"])
        return cmd


class RAxMLNGNode(CommandNode):
    """Phylogenetic tree inference with RAxML-NG."""

    NODE_ID = "raxml_ng"
    DISPLAY_NAME = "RAxML-NG"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Maximum likelihood phylogenetic tree inference with RAxML-NG."
    SEARCH_ALIASES = ["raxml-ng", "raxml", "maximum likelihood", "phylogeny", "bootstrap"]
    RETURN_TYPES = ("NEWICK", "FILE")
    RETURN_NAMES = ("tree", "bootstrap")
    REQUIRED_EXECUTABLES = ["raxml-ng"]
    REQUIRED_CONDA_PACKAGES = ["raxml-ng"]
    DOCUMENTATION_URL = "https://github.com/amkozlov/raxml-ng"
    VERSION = "1.2.2"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("FASTA", {"description": "Multiple sequence alignment"}),
                "model": ("STRING", {"default": "GTR+G", "description": "Substitution model, e.g. GTR+G or LG+G"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "seed": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "bootstrap_replicates": ("INT", {"default": 100, "min": 0, "max": 10000, "step": 100}),
                "outgroup": ("STRING", {"default": "", "description": "Comma-separated outgroup taxa", "advanced": True}),
                "tree_search": ("BOOLEAN", {"default": True, "description": "Run ML tree search; disable for evaluation only"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prefix = f"{inputs.get('output', '.')}/raxml_ng"
        cmd = [
            "raxml-ng",
            "--msa",
            str(inputs.get("alignment", "")),
            "--model",
            str(inputs.get("model", "GTR+G")),
            "--prefix",
            prefix,
            "--threads",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("seed"):
            cmd.extend(["--seed", str(inputs["seed"])])
        if inputs.get("tree_search", True):
            cmd.append("--all")
            if inputs.get("bootstrap_replicates"):
                cmd.extend(["--bs-trees", str(inputs["bootstrap_replicates"])])
        else:
            cmd.append("--evaluate")
        if inputs.get("outgroup"):
            cmd.extend(["--outgroup", str(inputs["outgroup"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        prefix = Path(output_dir) / cls.NODE_ID / "raxml_ng"
        prefix.parent.mkdir(parents=True, exist_ok=True)
        return [
            Path(f"{prefix}.raxml.bestTree"),
            Path(f"{prefix}.raxml.bootstraps"),
        ]
