"""CNVkit 0.9.12 target contract."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CNVkitCommandNode, optional_positive_int, output_path, plan_output


class CNVkitTargetNode(CNVkitCommandNode):
    """Transform bait intervals into CNVkit target bins."""

    NODE_ID = "cnvkit_target"
    DISPLAY_NAME = "CNVkit Target"
    DESCRIPTION = "Prepare CNVkit target BED intervals from capture bait regions."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "CNVkit",
        "CNVkit Target",
        "cnvkit.py target",
        "baited regions",
        "capture targets",
        "split target bins",
    ]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("out_capture_target",)
    DOCUMENTATION_URL = "https://cnvkit.readthedocs.io/en/stable/pipeline.html#target"
    UPSTREAM_SOURCE = "cnvlib/commands.py P_target and cnvlib/target.py do_target"
    OUTPUT_FILENAME = "capture.split.bed"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("BED", {"description": "Capture or target BED file"}),
            },
            "optional": {
                "annotate": (
                    "FILE",
                    {"description": "refFlat, ensFlat, BED, interval, or GFF gene annotation file"},
                ),
                "short_names": (
                    "BOOLEAN",
                    {"default": False, "description": "Reduce multi-accession bait labels"},
                ),
                "split": (
                    "BOOLEAN",
                    {"default": False, "description": "Split large tiled intervals"},
                ),
                "avg_size": (
                    "INT",
                    {
                        "default": "",
                        "min": 1,
                        "description": "Average split-bin size; blank uses CNVkit 0.9.12's upstream default",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        return optional_positive_int(inputs, "avg_size")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = [
            "cnvkit.py",
            "target",
            str(inputs.get("input_file", "")),
            "--output",
            output_path(inputs, cls.OUTPUT_FILENAME),
        ]
        annotate = str(inputs.get("annotate", "") or "").strip()
        if annotate:
            command.extend(["--annotate", annotate])
        if inputs.get("short_names"):
            command.append("--short-names")
        if inputs.get("split"):
            command.append("--split")
        avg_size = inputs.get("avg_size")
        if avg_size is not None and str(avg_size).strip():
            command.extend(["--avg-size", str(avg_size)])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return plan_output(cls.NODE_ID, output_dir, cls.OUTPUT_FILENAME)
