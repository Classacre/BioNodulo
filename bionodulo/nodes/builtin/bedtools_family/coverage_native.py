"""Canonical BioNodulo bedtools_coverage compatibility contract."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsCoverageNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_coverage"
    DISPLAY_NAME = "BEDTools Coverage"
    CATEGORY = "chip_seq"
    DESCRIPTION = "Compute alignment coverage over primary BED intervals"
    SEARCH_ALIASES = ["bedtools", "coverage", "depth", "intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("coverage",)
    OUTPUT_FILENAMES = ("coverage.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/coverage.html"
    UPSTREAM_SOURCE = "src/coverageFile/coverageFile.cpp"
    REQUIRED_PATH_INPUTS = ("a", "b")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "a": ("BED", {"description": "Intervals whose coverage is reported"}),
                "b": ("BAM", {"description": "Alignments contributing coverage"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(
            inputs,
            "bedtools",
            "coverage",
            "-a",
            str(inputs["a"]),
            "-b",
            str(inputs["b"]),
        )


__all__ = ["BEDToolsCoverageNode"]
