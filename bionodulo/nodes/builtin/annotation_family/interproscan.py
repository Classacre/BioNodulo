"""Focused InterProScan owner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .evidence import attach_evidence


@attach_evidence
class InterProScanNode(CommandNode):
    """Scan protein sequences for domains and functional annotations."""

    NODE_ID = "interproscan"
    DISPLAY_NAME = "InterProScan"
    CATEGORY = "annotation"
    DESCRIPTION = "Scan proteins for domains, families, functional sites (Pfam, InterPro, GO, KEGG)."
    SEARCH_ALIASES = ["interproscan", "protein domain", "pfam", "go annotation", "interpro"]
    RETURN_TYPES = ("TSV", "JSON", "GFF")
    RETURN_NAMES = ("ipr_matches", "ipr_json", "ipr_gff")
    REQUIRED_EXECUTABLES = ["interproscan.sh"]
    REQUIRED_CONDA_PACKAGES = ["interproscan"]
    DOCUMENTATION_URL = "https://www.ebi.ac.uk/interpro/"
    SHELL = False
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta": ("FASTA", {"description": "Protein FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "optional": {
                "applications": ("STRING", {"default": "", "description": "e.g., Pfam,Gene3D,PANTHER"}),
                "goterms": ("BOOLEAN", {"default": True}),
                "iprlookup": ("BOOLEAN", {"default": True}),
                "pathways": ("BOOLEAN", {"default": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("fasta", "")).strip():
            return "fasta is required"
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be at least 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        command = [
            "interproscan.sh",
            "-i",
            str(inputs.get("fasta", "")),
            "-b",
            f"{out_dir}/ipr",
            "-f",
            "TSV,JSON,GFF3",
            "-cpu",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("applications"):
            command.extend(["-appl", str(inputs["applications"])])
        if inputs.get("goterms", True):
            command.append("-goterms")
        if inputs.get("iprlookup", True):
            command.append("-iprlookup")
        if inputs.get("pathways", True):
            command.append("-pa")
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "ipr.tsv", node_out / "ipr.json", node_out / "ipr.gff3"]
