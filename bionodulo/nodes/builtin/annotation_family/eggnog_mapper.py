"""Focused eggNOG-mapper contract with an explicit offline data directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .evidence import attach_evidence


@attach_evidence
class EggNOGMapperNode(CommandNode):
    """Annotate proteins with an explicitly staged eggNOG data directory."""

    NODE_ID = "eggnog_mapper"
    DISPLAY_NAME = "eggNOG-mapper"
    CATEGORY = "annotation"
    DESCRIPTION = "Fast genome-wide functional annotation via orthology"
    SEARCH_ALIASES = ["eggnog", "emapper", "functional", "cog", "go"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("annotations",)
    REQUIRED_EXECUTABLES = ["emapper.py"]
    REQUIRED_CONDA_PACKAGES = ["eggnog-mapper"]
    DOCUMENTATION_URL = "https://github.com/eggnogdb/eggnog-mapper"
    COMMAND = [
        "emapper.py",
        "-i",
        "{inputs.proteins}",
        "--output",
        "{inputs.prefix}",
        "--output_dir",
        "{output}",
        "-m",
        "{inputs.mode}",
        "--cpu",
        "{inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "proteins": ("FASTA", {"description": "Protein FASTA file (.faa)"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "prefix": ("STRING", {"default": "annotations"}),
                "data_dir": (
                    "DIRECTORY",
                    {"description": "Pre-downloaded eggNOG-mapper data directory"},
                ),
            },
            "optional": {
                "mode": (
                    "STRING",
                    {
                        "default": "diamond",
                        "options": ["diamond", "mmseqs"],
                        "description": "Search backend",
                    },
                ),
                "itype": (
                    "STRING",
                    {
                        "default": "proteins",
                        "options": ["proteins", "CDS", "genome", "metagenome"],
                        "label": "Input Type",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for key in ("proteins", "data_dir"):
            if not str(inputs.get(key, "")).strip():
                return f"{key} is required"
        prefix = str(inputs.get("prefix", "annotations"))
        if not prefix or Path(prefix).name != prefix or prefix in {".", ".."}:
            return "prefix must be a filename without directory components"
        mode = str(inputs.get("mode", "diamond"))
        if mode not in {"diamond", "mmseqs"}:
            return "mode must be one of: diamond, mmseqs"
        itype = str(inputs.get("itype", "proteins"))
        if itype not in {"proteins", "CDS", "genome", "metagenome"}:
            return "itype must be one of: proteins, CDS, genome, metagenome"
        try:
            threads = int(inputs.get("threads", 8))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be at least 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return [
            "emapper.py",
            "-i",
            str(inputs["proteins"]),
            "--output",
            str(inputs.get("prefix", "annotations")),
            "--output_dir",
            str(inputs.get("output", inputs.get("output_dir", "."))),
            "-m",
            str(inputs.get("mode", "diamond")),
            "--cpu",
            str(inputs.get("threads", 8)),
            "--data_dir",
            str(inputs["data_dir"]),
            "--itype",
            str(inputs.get("itype", "proteins")),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = str(inputs.get("prefix", "annotations"))
        return [node_out / f"{prefix}.emapper.annotations"]

    async def run(self, **kwargs: Any) -> Any:
        # Skip the legacy post-run copy, which targets a filename eggNOG-mapper never creates.
        return await CommandNode.run(self, **kwargs)
