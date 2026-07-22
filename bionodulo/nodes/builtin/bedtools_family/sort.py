"""BEDTools sort node pinned to 2.31.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsSortNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_sortbed"
    DISPLAY_NAME = "BEDTools Sort"
    DESCRIPTION = "Sort interval records by coordinates, size, score, or genome order"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "sort", "sortbed", "coordinate sort"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("sorted_intervals",)
    CONDA_PACKAGE_CONSTRAINTS = {"bedtools": "2.31.1"}
    PACKAGE_CONSTRAINTS = ("bedtools==2.31.1",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    DOCUMENTATION_URL = (
        "https://github.com/arq5x/bedtools2/blob/"
        "705ccfdf2c9a77d71560c8adcece0663c2f5e18e/docs/content/tools/sort.rst"
    )
    SOURCE_URL = DOCUMENTATION_URL
    SOURCE_SHA256 = "d69117e1b2d24caae92fe6e84034a1f7e6f16877e94eaca6466528f8b4e0ee02"
    UPSTREAM_SOURCE = "src/sortBed/sortBed.cpp"
    UPSTREAM_SOURCE_SHA256 = "c72bb170d3397693c2ceae5d7556c451f32c9edb427e5db586a7da0af32ba7ef"
    EXIT_SEMANTICS = (
        "Malformed interval records, missing genome-order chromosomes, and score sorting of records below BED5 "
        "exit non-zero; every non-zero exit is fatal. Standard output is captured as the planned artifact, which "
        "must exist after a zero exit."
    )
    REQUIRED_PATH_INPUTS = ("input",)
    SORT_MODES = ("", "-sizeA", "-sizeD", "-chrThenSizeA", "-chrThenSizeD", "-chrThenScoreA", "-chrThenScoreD")

    @staticmethod
    def output_name(value: Any) -> str:
        path = Path(str(value))
        if path.suffix.lower() in (".gz", ".bgz", ".bz2", ".xz"):
            path = path.with_suffix("")
        extension = path.suffix.lstrip(".") or "bed"
        return f"sorted.{extension}"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("FILE", {})},
            "optional": {
                "sort_by": ("STRING", {"default": "", "options": list(cls.SORT_MODES)}),
                "genome": ("TSV", {"default": ""}),
                "header": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.output_name(inputs.get("input"))]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.validate_choice(inputs.get("sort_by", ""), cls.SORT_MODES, "sort_by")
        if validation is not True:
            return validation
        if inputs.get("sort_by") and inputs.get("genome"):
            return "sort_by and genome ordering are mutually exclusive"
        if inputs.get("genome"):
            return cls.require_path(inputs, "genome")
        if "option" in inputs:
            return "option is stale; use sort_by"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "sort", "-i", str(inputs["input"]))
        if inputs.get("sort_by"):
            command.append(str(inputs["sort_by"]))
        elif inputs.get("genome"):
            command.extend(["-g", str(inputs["genome"])])
        if inputs.get("header"):
            command.append("-header")
        return command
