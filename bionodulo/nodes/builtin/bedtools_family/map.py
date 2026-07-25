"""BEDTools map node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsMapNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_map"
    DISPLAY_NAME = "BEDTools Map"
    DESCRIPTION = "Map summary statistics from sorted B records onto sorted A intervals"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "map", "mapbed", "overlap summary"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("mapped",)
    OUTPUT_FILENAMES = ("mapped.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/map.html"
    UPSTREAM_SOURCE = "src/mapFile/mapFile.cpp"
    REQUIRED_PATH_INPUTS = ("inputA", "inputB")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {}), "inputB": ("BED", {}),
                "columns": ("STRING", {"default": "5"}),
                "operations": ("STRING", {"default": "mean"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "reciprocal": ("BOOLEAN", {"default": False}),
                "either_fraction": ("BOOLEAN", {"default": False}),
                "split": ("BOOLEAN", {"default": False}),
                "header": ("BOOLEAN", {"default": False}),
                "genome": ("TSV", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.validate_column_operations(inputs.get("columns"), inputs.get("operations"))
        if validation is not True:
            return validation
        validation = cls.validate_choice(inputs.get("strand", ""), ("", "same", "opposite"), "strand")
        if validation is not True:
            return validation
        if inputs.get("genome") not in (None, ""):
            validation = cls.require_path(inputs, "genome")
            if validation is not True:
                return validation
        return cls.validate_overlap_options(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs, "bedtools", "map", "-a", str(inputs["inputA"]), "-b", str(inputs["inputB"]),
            "-c", ",".join(cls.csv_values(inputs["columns"])),
            "-o", ",".join(cls.csv_values(inputs["operations"])),
        )
        strand = cls.strand_flag(inputs.get("strand"))
        if strand:
            command.append(strand)
        cls.add_overlap_options(command, inputs)
        if inputs.get("split"):
            command.append("-split")
        if inputs.get("header"):
            command.append("-header")
        cls.optional_value(command, "-g", inputs.get("genome"))
        return command
