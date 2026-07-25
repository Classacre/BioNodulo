"""Stable owner for ``minigraph``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import _path_value, _positive_int, _split_path_list
from .evidence import PangenomicsCommandContract


class MinigraphNode(PangenomicsCommandContract):
    """Construct or align pangenome graphs with minigraph."""
    NODE_ID = "minigraph"
    OUTPUT_NAME_BY_BASENAME = {
        "output_gfa.gfa": "output_gfa",
        "alignment_gaf.gaf": "alignment_gaf",
    }
    DISPLAY_NAME = "Minigraph"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Fast sequence-to-graph aligner and pangenome constructor for large genomes."
    SEARCH_ALIASES = ["minigraph", "graph align", "pangenome", "sv graph", "sequence to graph"]
    RETURN_TYPES = ("GFA", "FILE")
    RETURN_NAMES = ("output_gfa", "alignment_gaf")
    REQUIRED_EXECUTABLES = ["minigraph"]
    REQUIRED_CONDA_PACKAGES = ["minigraph"]
    DOCUMENTATION_URL = "https://github.com/lh3/minigraph"
    VERSION = "0.21"
    SHELL = True
    MODE_PRESET_POLICY = (
        "Minigraph has no single preset for both operations: construct requires ggs, "
        "while align accepts asm or lr. Validation rejects mode/preset mismatches."
    )

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        mode = str(inputs.get("mode", "construct") or "construct")
        if mode not in {"construct", "align"}:
            return "mode must be one of: align, construct"
        validation = _positive_int(inputs.get("threads", 8), "threads", 8)
        if isinstance(validation, str):
            return validation
        preset = str(inputs.get("preset", "ggs" if mode == "construct" else "asm") or "")
        if mode == "construct":
            if preset != "ggs":
                return "construct mode requires the documented ggs preset"
            if len(_split_path_list(inputs.get("assemblies"))) < 2:
                return "construct mode requires a reference plus at least one assembly"
        else:
            if preset not in {"asm", "lr"}:
                return "align mode preset must be one of: asm, lr"
            for name in ("graph_gfa", "query_fasta"):
                if not _path_value(inputs.get(name)):
                    return f"{name} is required for align mode"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get("output", ".")))
        mode = str(inputs.get("mode", "construct") or "construct")
        threads = str(inputs.get("threads", 8))

        if mode == "construct":
            output = out_dir / "output_gfa.gfa"
            cmd = ["minigraph", "-c", "-x", "ggs", "-t", threads]
            cmd.extend(_split_path_list(inputs.get("assemblies")))
        else:
            output = out_dir / "alignment_gaf.gaf"
            cmd = [
                "minigraph",
                "-c",
                "-x",
                str(inputs.get("preset", "asm") or "asm"),
                "-t",
                threads,
                str(inputs.get("graph_gfa", "")),
                str(inputs.get("query_fasta", "")),
            ]
        cmd.extend([">", str(output), "&&", "test", "-s", str(output)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        if str(inputs.get("mode", "construct") or "construct") == "align":
            return [node_out / "alignment_gaf.gaf"]
        return [node_out / "output_gfa.gfa"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mode": ("STRING", {"default": "construct", "options": ["construct", "align"]}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64}),
            },
            "optional": {
                "assemblies": (
                    "FASTA",
                    {"multiple": True, "description": "Reference first, followed by assembly FASTAs"},
                ),
                "graph_gfa": ("GFA", {"description": "Graph GFA (for align mode)"}),
                "query_fasta": ("FASTA", {"description": "Query FASTA (for align mode)"}),
                "preset": (
                    "STRING",
                    {"default": "ggs", "options": ["ggs", "asm", "lr"], "description": "ggs for construction; asm/lr for mapping"},
                ),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
