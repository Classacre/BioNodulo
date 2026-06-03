"""CRISPR and genome-editing workflow nodes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class CRISPRESSONode(CommandNode):
    """Analyze CRISPR amplicon editing outcomes with CRISPResso2."""
    NODE_ID = "crispresso2"
    DISPLAY_NAME = "CRISPRESSO2"
    CATEGORY = "crispr"
    DESCRIPTION = "Analyze CRISPR editing from amplicon sequencing. Quantifies indels, frameshifts, allele-specific outcomes."
    SEARCH_ALIASES = ["crispresso", "crispresso2", "crispr", "amplicon", "indel", "editing analysis"]
    RETURN_TYPES = ("HTML_REPORT", "DIRECTORY")
    RETURN_NAMES = ("report", "results_dir")
    REQUIRED_EXECUTABLES = ["CRISPResso"]
    REQUIRED_CONDA_PACKAGES = ["crispresso2"]
    DOCUMENTATION_URL = "https://github.com/pinellolab/CRISPResso2"
    VERSION = "2.3.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "CRISPResso",
            "-r1",
            str(inputs.get("r1", "")),
            "-a",
            str(inputs.get("amplicon_seq", "")),
            "-o",
            str(out_dir),
            "--name",
            str(inputs.get("name", "crispresso_run")),
        ]
        if inputs.get("r2"):
            cmd.extend(["-r2", str(inputs["r2"])])
        if inputs.get("guide_seq"):
            cmd.extend(["-g", str(inputs["guide_seq"])])
        if inputs.get("quant_window_center"):
            cmd.extend(["-qc", str(inputs["quant_window_center"])])
        if inputs.get("quant_window_size"):
            cmd.extend(["-w", str(inputs["quant_window_size"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        name = str(inputs.get("name", "crispresso_run"))
        run_name = f"CRISPResso_on_{name}"
        return [node_out / f"{run_name}.html", node_out / run_name]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Forward FASTQ"}),
                "amplicon_seq": ("STRING", {"description": "Reference amplicon sequence"}),
                "name": ("STRING", {"default": "crispresso_run"}),
            },
            "optional": {
                "r2": ("FASTQ", {"description": "Reverse FASTQ (paired)"}),
                "guide_seq": ("STRING", {"default": "", "description": "gRNA sequence (20bp)"}),
                "quant_window_center": ("INT", {"default": -3, "min": -20, "max": 20}),
                "quant_window_size": ("INT", {"default": 1, "min": 0, "max": 100}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
