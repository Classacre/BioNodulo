"""MACS2 bdgpeakcall node pinned to the 2.2.9.1 command contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import MACS2CommandNode


class MACS2BdgPeakNode(MACS2CommandNode):
    """Call narrow peaks directly from a MACS2 score bedGraph."""

    NODE_ID = "macs2_bdgpeak"
    DISPLAY_NAME = "MACS2 BdgPeak"
    DESCRIPTION = "Call peaks from bedGraph signal tracks with MACS2 bdgpeakcall"
    SEARCH_ALIASES = ["macs2", "bdgpeakcall", "bedgraph peaks", "chip-seq", "atac-seq"]
    RETURN_TYPES = ("NARROW_PEAK",)
    RETURN_NAMES = ("peaks",)
    DOCUMENTATION_URL = "https://github.com/macs3-project/MACS/blob/v2.2.9.1/README.md"
    UPSTREAM_SOURCE = "MACS2/bdgpeakcall_cmd.py"
    PREVIOUS_VERSIONS = ["2.2.9.2"]
    MIGRATIONS = [
        {
            "from_version": "2.2.9.2",
            "to_version": "2.2.9.1",
            "description": (
                "The focused node now runs bdgpeakcall only; move legacy bdgcmp "
                "work to a dedicated score-track operation before peak calling."
            ),
        }
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "treatment_bdg": (
                    "FILE",
                    {"description": "Continuous MACS2 score bedGraph input"},
                ),
            },
            "optional": {
                "cutoff": ("FLOAT", {"default": 5.0, "min": 0.0}),
                "min_length": ("INT", {"default": 200, "min": 1}),
                "max_gap": ("INT", {"default": 30, "min": 0}),
                "name": ("STRING", {"default": "macs2_bdgpeak"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.require_path(inputs, "treatment_bdg")
        if validation is not True:
            return validation
        legacy_method = str(inputs.get("method", "bdgpeakcall") or "bdgpeakcall").lower()
        if legacy_method != "bdgpeakcall":
            return (
                "legacy method=bdgcmp is not supported by the focused macs2_bdgpeak "
                "contract; compute the score bedGraph separately"
            )
        if str(inputs.get("control_bdg", "") or "").strip():
            return (
                "legacy control_bdg is not accepted by macs2 bdgpeakcall; "
                "supply a precomputed score bedGraph as treatment_bdg"
            )
        if not str(inputs.get("name", "macs2_bdgpeak") or "").strip():
            return "name must be non-empty"
        cutoff = inputs.get("cutoff", 5.0)
        if isinstance(cutoff, bool) or not isinstance(cutoff, (int, float)) or cutoff < 0:
            return "cutoff must be a non-negative number"
        min_length = inputs.get("min_length", 200)
        if isinstance(min_length, bool) or not isinstance(min_length, int) or min_length < 1:
            return "min_length must be a positive integer"
        max_gap = inputs.get("max_gap", 30)
        if isinstance(max_gap, bool) or not isinstance(max_gap, int) or max_gap < 0:
            return "max_gap must be a non-negative integer"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return [
            "macs2",
            "bdgpeakcall",
            "-i",
            str(inputs.get("treatment_bdg", "")),
            "-c",
            str(inputs.get("cutoff", 5.0)),
            "-l",
            str(inputs.get("min_length", 200)),
            "-g",
            str(inputs.get("max_gap", 30)),
            "--outdir",
            str(cls.output_dir(inputs)),
            "-o",
            cls.output_filename(inputs),
        ]

    @classmethod
    def output_filename(cls, inputs: dict[str, Any]) -> str:
        stem = cls.safe_output_stem(inputs.get("name"), "macs2_bdgpeak")
        return f"{stem}.narrowPeak"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.output_filename(inputs)]
