"""HTSlib ``tabix`` index-building node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import HtslibTabixBase, _looks_compressed, stage_input

_PRESETS = ["vcf", "bed", "gff"]


class TabixIndexNode(HtslibTabixBase):
    """Build a colocated ``.tbi`` index for a bgzipped, coordinate-sorted file."""

    NODE_ID = "tabix_index"
    DISPLAY_NAME = "Tabix Index"
    DESCRIPTION = (
        "Create a tabix (.tbi) index for a bgzipped, coordinate-sorted VCF, BED, or GFF file"
    )
    SEARCH_ALIASES = [
        "tabix",
        "index",
        "tbi",
        "vcf index",
        "bgzf index",
        "htslib",
    ]
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("indexed_file", "tbi_index")
    OUTPUT_FILENAMES = ("indexed.vcf.gz", "indexed.vcf.gz.tbi")
    DOCUMENTATION_URL = "https://www.htslib.org/doc/tabix.html"
    UPSTREAM_MANPAGE = "tabix.1"
    UPSTREAM_SOURCE = "tabix.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bgzf": (
                    "FILE",
                    {"description": "Bgzipped, coordinate-sorted VCF, BED, or GFF file"},
                ),
            },
            "optional": {
                "preset": (
                    "STRING",
                    {
                        "default": "vcf",
                        "options": _PRESETS,
                        "description": "Tabix coordinate preset (column layout)",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        preset = inputs.get("preset", "vcf")
        if preset not in _PRESETS:
            return f"preset must be one of: {', '.join(_PRESETS)}"
        value = inputs.get("bgzf")
        if value is None:
            return "Input 'bgzf' must be a non-empty path"
        if not _looks_compressed(str(value)):
            return (
                "Input 'bgzf' must be a bgzipped file ending in .gz, .bgz, or .bgzf; "
                "tabix cannot index an uncompressed file"
            )
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return [
            "tabix",
            "-p",
            str(inputs.get("preset", "vcf")),
            "-f",
            str(inputs.get("bgzf", "")),
        ]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        staged = stage_input(inputs["bgzf"], outputs[0])
        inputs["bgzf"] = str(staged)
