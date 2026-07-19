"""CNVkit 0.9.12 antitarget contract."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CNVkitCommandNode, optional_positive_int, output_path, plan_output


class CNVkitAntitargetNode(CNVkitCommandNode):
    """Derive off-target bins from capture targets and optional access regions."""

    NODE_ID = "cnvkit_antitarget"
    DISPLAY_NAME = "CNVkit Antitarget"
    DESCRIPTION = "Derive CNVkit antitarget BED intervals from targeted resequencing regions."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "CNVkit",
        "CNVkit Antitarget",
        "cnvkit.py antitarget",
        "antitarget regions",
        "off-target bins",
    ]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("out_capture_antitarget",)
    DOCUMENTATION_URL = "https://cnvkit.readthedocs.io/en/stable/pipeline.html#antitarget"
    UPSTREAM_SOURCE = "cnvlib/commands.py P_anti and cnvlib/antitarget.py do_antitarget"
    OUTPUT_FILENAME = "capture.antitarget.bed"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "targets_file": ("BED", {"description": "Input target BED or interval file"}),
            },
            "optional": {
                "access": ("BED", {"description": "Accessible reference regions from CNVkit access"}),
                "avg_size": (
                    "INT",
                    {"default": 150000, "min": 1, "description": "Approximate average antitarget bin size"},
                ),
                "min_size": (
                    "INT",
                    {
                        "default": "",
                        "min": 1,
                        "description": "Minimum bin size; blank uses CNVkit's calculated 1/16-average default",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("targets_file", "")).strip():
            return "targets_file is required"
        for field in ("avg_size", "min_size"):
            validation = optional_positive_int(inputs, field)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ["cnvkit.py", "antitarget", str(inputs.get("targets_file", ""))]
        access = str(inputs.get("access", "") or "").strip()
        if access:
            command.extend(["--access", access])
        command.extend(["--avg-size", str(inputs.get("avg_size", 150000))])
        min_size = inputs.get("min_size")
        if min_size is not None and str(min_size).strip():
            command.extend(["--min-size", str(min_size)])
        command.extend(["--output", output_path(inputs, cls.OUTPUT_FILENAME)])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return plan_output(cls.NODE_ID, output_dir, cls.OUTPUT_FILENAME)
