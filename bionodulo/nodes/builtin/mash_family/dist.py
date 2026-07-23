"""Focused owner for ``mash_dist``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract

class MashDistNode(ToolsIUCCommandContract):
    """Estimate Mash distances between reference and query sequences."""

    NODE_ID = "mash_dist"
    DISPLAY_NAME = "Mash Dist"
    REQUIRED_CONDA_PACKAGES = ["mash"]
    CATEGORY = "genomics"
    DESCRIPTION = "Estimate genome or metagenome distances from FASTA/FASTQ files or Mash sketches."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "mash", "mash dist", "minhash", "genome distance", "metagenome distance"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("distances",)
    REQUIRED_EXECUTABLES = ["mash"]
    DOCUMENTATION_URL = "https://mash.readthedocs.io/en/latest/distances.html"
    CITATION_DOIS = ["10.1186/s13059-016-0997-x"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s13059-016-0997-x"]
    CITATION_TEXT = "Mash: fast genome and metagenome distance estimation using MinHash."
    VERSION = "2.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["mash", "dist"]
        if inputs.get("table_output", True):
            cmd.append("-t")
        cmd.extend(["-p", str(inputs.get("threads", 1))])
        _add_if_value(cmd, "-v", inputs.get("pvalue", 1.0))
        _add_if_value(cmd, "-d", inputs.get("distance", 1.0))
        cmd.extend([str(inputs.get("reference", "")), str(inputs.get("query", ""))])
        _add_shell_redirect(cmd, f"{out}/distances.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "distances.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("reference", "")).strip():
            return "Mash reference input is required"
        if not str(inputs.get("query", "")).strip():
            return "Mash query input is required"
        try:
            threads = int(inputs.get("threads", 1))
            pvalue = float(inputs.get("pvalue", 1.0))
            distance = float(inputs.get("distance", 1.0))
        except (TypeError, ValueError):
            return "Mash dist numeric options are invalid"
        if threads < 1:
            return "Mash dist threads must be a positive integer"
        if not 0 <= pvalue <= 1:
            return "Mash dist p-value threshold must be between 0 and 1"
        if not 0 <= distance <= 1:
            return "Mash dist distance threshold must be between 0 and 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference FASTA/FASTQ or Mash sketch"}),
                "query": ("FASTA", {"description": "Query FASTA/FASTQ or Mash sketch"}),
            },
            "optional": {
                "table_output": ("BOOLEAN", {"default": True, "description": "Use Mash table output (-t)"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "pvalue": ("FLOAT", {"default": 1.0, "min": 0, "max": 1}),
                "distance": ("FLOAT", {"default": 1.0, "min": 0, "max": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }
