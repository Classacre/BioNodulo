"""BEDTools merge node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsMergeNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_mergebed"
    DISPLAY_NAME = "BEDTools Merge"
    DESCRIPTION = "Merge sorted overlapping or nearby intervals"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "merge", "mergebed", "flatten intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("merged",)
    OUTPUT_FILENAMES = ("merged.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/merge.html"
    UPSTREAM_SOURCE = "src/mergeFile/mergeFile.cpp"
    REQUIRED_PATH_INPUTS = ("input",)
    STRANDS = ("", "same", "forward", "reverse")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("FILE", {"description": "Chromosome/start-sorted intervals"}), "distance": ("INT", {"default": 0})},
            "optional": {
                "strand": ("STRING", {"default": "", "options": list(cls.STRANDS)}),
                "header": ("BOOLEAN", {"default": False}),
                "columns": ("STRING", {"default": ""}),
                "operations": ("STRING", {"default": ""}),
                "delimiter": ("STRING", {"default": ";"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.validate_choice(inputs.get("strand", ""), cls.STRANDS, "strand")
        if validation is not True:
            return validation
        validation = cls.validate_int(inputs.get("distance", 0), "distance")
        if validation is not True:
            return validation
        columns = inputs.get("columns")
        operations = inputs.get("operations")
        if bool(cls.csv_values(columns)) != bool(cls.csv_values(operations)):
            return "columns and operations must be provided together"
        if cls.csv_values(columns):
            validation = cls.validate_column_operations(columns, operations)
            if validation is not True:
                return validation
        if not str(inputs.get("delimiter", ";")):
            return "delimiter must be non-empty"
        if not cls.csv_values(columns) and inputs.get("delimiter", ";") != ";":
            return "delimiter is only valid with columns and operations"
        if "cols" in inputs or "operation" in inputs:
            return "legacy cols/operation inputs are stale; use columns/operations"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "merge", "-i", str(inputs["input"]), "-d", str(inputs.get("distance", 0)))
        strand = str(inputs.get("strand", ""))
        if strand == "same":
            command.append("-s")
        elif strand in ("forward", "reverse"):
            command.extend(["-S", "+" if strand == "forward" else "-"])
        if inputs.get("header"):
            command.append("-header")
        if cls.csv_values(inputs.get("columns")):
            command.extend([
                "-c", ",".join(cls.csv_values(inputs["columns"])),
                "-o", ",".join(cls.csv_values(inputs["operations"])),
                "-delim", str(inputs.get("delimiter", ";")),
            ])
        return command
