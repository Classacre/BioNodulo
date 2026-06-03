"""Long-read sequencing nodes."""
from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


class ModkitPileupNode(CommandNode):
    """Generate bedMethyl pileups from modified-base BAM files."""
    NODE_ID = "modkit_pileup"
    DISPLAY_NAME = "Modkit Pileup"
    CATEGORY = "long_read"
    DESCRIPTION = (
        "Generate bedMethyl pileup from ONT BAM with MM/ML modified base tags. "
        "Single-base methylation resolution."
    )
    SEARCH_ALIASES = ["modkit", "methylation", "modified bases", "pileup", "bedmethyl", "5mc", "6ma"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("bedmethyl",)
    REQUIRED_EXECUTABLES = ["modkit"]
    REQUIRED_CONDA_PACKAGES = ["modkit"]
    DOCUMENTATION_URL = "https://github.com/nanoporetech/modkit"
    VERSION = "0.4.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "modkit",
            "pileup",
            str(inputs.get("bam", "")),
            f"{out_dir}/bedmethyl.bed",
            "--ref",
            str(inputs.get("reference", "")),
            "--threads",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("combine_strands"):
            cmd.append("--combine-strands")
        if inputs.get("region"):
            cmd.extend(["--region", str(inputs["region"])])
        if inputs.get("bedgraph"):
            cmd.append("--bedgraph")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "BAM with MM/ML modified base tags"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "combine_strands": ("BOOLEAN", {"default": True, "description": "Combine methylation from both strands"}),
                "region": ("STRING", {"default": "", "description": "Region (e.g., chr1:1-1000000)"}),
                "bedgraph": ("BOOLEAN", {"default": False, "description": "Also output bedGraph"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
