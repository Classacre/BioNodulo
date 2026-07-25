"""CNVkit 0.9.12 access contract."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CNVkitCommandNode, output_path, plan_output


def _exclude_paths(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    values = list(value) if isinstance(value, (list, tuple)) else [value]
    paths: list[str] = []
    for item in values:
        if isinstance(item, dict):
            path = next(
                (
                    str(item[key]).strip()
                    for key in ("path", "file", "input", "location")
                    if item.get(key) is not None and str(item[key]).strip()
                ),
                "",
            )
        else:
            path = str(item).strip()
        paths.append(path)
    return paths


class CNVkitAccessNode(CNVkitCommandNode):
    """List accessible reference regions after masking long N gaps."""

    NODE_ID = "cnvkit_access"
    DISPLAY_NAME = "CNVkit Access"
    DESCRIPTION = "Calculate sequence-accessible reference genome coordinates for CNVkit."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "CNVkit",
        "CNVkit Access",
        "cnvkit.py access",
        "sequence-accessible coordinates",
        "masked N regions",
    ]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("out_sample_access",)
    DOCUMENTATION_URL = "https://cnvkit.readthedocs.io/en/stable/pipeline.html#access"
    UPSTREAM_SOURCE = "cnvlib/commands.py P_access and cnvlib/access.py do_access"
    SOURCE_PATHS = ("cnvlib/commands.py", "cnvlib/access.py", "doc/pipeline.rst")
    OUTPUT_FILENAME = "access-excludes.bed"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fa_fname": ("FASTA", {"description": "Reference genome FASTA file"}),
            },
            "optional": {
                "min_gap_size": (
                    "INT",
                    {
                        "default": 5000,
                        "min": 0,
                        "description": "Join accessible regions separated by gaps smaller than this size",
                    },
                ),
                "exclude": (
                    "BED",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Additional BED regions to subtract; rendered once per --exclude",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("fa_fname", "")).strip():
            return "fa_fname is required"
        try:
            min_gap_size = int(inputs.get("min_gap_size", 5000))
        except (TypeError, ValueError):
            return "min_gap_size must be an integer"
        if min_gap_size < 0:
            return "min_gap_size must be greater than or equal to 0"
        if any(not path for path in _exclude_paths(inputs.get("exclude"))):
            return "each exclude BED requires a path"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ["cnvkit.py", "access", str(inputs.get("fa_fname", ""))]
        for path in _exclude_paths(inputs.get("exclude")):
            command.extend(["--exclude", path])
        command.extend(
            [
                "--min-gap-size",
                str(inputs.get("min_gap_size", 5000)),
                "--output",
                output_path(inputs, cls.OUTPUT_FILENAME),
            ]
        )
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return plan_output(cls.NODE_ID, output_dir, cls.OUTPUT_FILENAME)
