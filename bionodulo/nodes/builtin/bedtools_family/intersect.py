"""Canonical BioNodulo bedtools_intersect compatibility contract."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsIntersectNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_intersect"
    DISPLAY_NAME = "BEDTools Intersect"
    CATEGORY = "chip_seq"
    DESCRIPTION = "Report overlaps between two interval files"
    SEARCH_ALIASES = ["bedtools", "intersect", "overlap", "bed"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("intersection",)
    OUTPUT_FILENAMES = ("intersection.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/intersect.html"
    UPSTREAM_SOURCE = "src/intersectFile/intersectFile.cpp"
    REQUIRED_PATH_INPUTS = ("a", "b")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "a": ("BED", {"description": "Primary BED/GFF/VCF/BAM intervals"}),
                "b": ("BED", {"description": "Comparison BED/GFF/VCF/BAM intervals"}),
            },
            "optional": {
                "wa": ("BOOLEAN", {"default": False}),
                "wb": ("BOOLEAN", {"default": False}),
                "f": ("FLOAT", {"default": 1e-9, "min": 0.0, "max": 1.0}),
                "sorted": ("BOOLEAN", {"default": False}),
                "v": ("BOOLEAN", {"default": False}),
                "s": ("BOOLEAN", {"default": False}),
                "wo": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.validate_fraction(inputs.get("f", 1e-9), "f", allow_zero=False)
        if validation is not True:
            return validation
        if inputs.get("v") and any(inputs.get(key) for key in ("wb", "wo")):
            return "v cannot be combined with wb or wo output modes"
        if inputs.get("wo") and any(inputs.get(key) for key in ("wa", "wb")):
            return "wo cannot be combined with wa or wb"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "intersect", "-a", str(inputs["a"]), "-b", str(inputs["b"]))
        for key, flag in (("wa", "-wa"), ("wb", "-wb")):
            if inputs.get(key):
                command.append(flag)
        cls.optional_value(command, "-f", inputs.get("f", 1e-9))
        for key, flag in (("sorted", "-sorted"), ("v", "-v"), ("s", "-s"), ("wo", "-wo")):
            if inputs.get(key):
                command.append(flag)
        return command


__all__ = ["BEDToolsIntersectNode"]
