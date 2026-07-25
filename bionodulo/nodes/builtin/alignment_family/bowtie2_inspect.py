"""Recover reference FASTA records from a complete Bowtie2 index bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .bowtie2_adapter import BOWTIE2_SUFFIX_FAMILIES, Bowtie2CommandNode, bowtie2_source_urls
from .fm_index_bundle import find_index_bundle, path_value, planned_or_complete_prefix


class Bowtie2IndexNode(Bowtie2CommandNode):
    """Run Bowtie2 inspect's default FASTA mode against a validated bundle."""

    NODE_ID = "bowtie2_inspect"
    DISPLAY_NAME = "Bowtie2 Inspect"
    DESCRIPTION = "Extract the indexed reference sequences as FASTA"
    SEARCH_ALIASES = ["bowtie2", "inspect", "index", "reference fasta"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("reference",)
    REQUIRED_EXECUTABLES = ["bowtie2-inspect"]
    STDOUT_OUTPUT_INDEX = 0
    UPSTREAM_WRAPPER = "bowtie2-inspect"
    UPSTREAM_SOURCE = "bt2_inspect.cpp"
    SOURCE_PATHS = ("MANUAL.markdown", "bowtie2-inspect", "bt2_inspect.cpp")
    SOURCE_URLS = bowtie2_source_urls(*SOURCE_PATHS)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "index": (
                    "INDEX_DIR",
                    {"description": "Directory containing one complete Bowtie2 index prefix"},
                ),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation

        index = path_value(inputs.get("index"))
        if index is None:
            return "Input 'index' must be a non-empty path-like value"
        try:
            find_index_bundle(
                index,
                label="Bowtie2",
                suffix_families=BOWTIE2_SUFFIX_FAMILIES,
            )
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            return str(exc)
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prefix = planned_or_complete_prefix(
            str(inputs.get("index", "")),
            label="Bowtie2",
            suffix_families=BOWTIE2_SUFFIX_FAMILIES,
        )
        return ["bowtie2-inspect", str(prefix)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "reference.fasta"]
