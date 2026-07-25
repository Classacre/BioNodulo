"""RSeQC ``junction_saturation.py`` node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCJunctionSaturationNode(RSeQCCommandNode):
    """Assess splice-junction discovery saturation across sequencing depth."""

    NODE_ID = "rseqc_junction_saturation"
    DISPLAY_NAME = "RSeQC Junction Saturation"
    DESCRIPTION = "Resample alignments to measure known and novel junction discovery saturation."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "junction_saturation.py",
        "junction saturation",
        "splice-junction discovery",
    ]
    RETURN_TYPES = ("TEXT", "IMAGE")
    RETURN_NAMES = ("r_script", "junction_saturation_plot")
    REQUIRED_EXECUTABLES = ["junction_saturation.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#junction-saturation-py"
    UPSTREAM_SCRIPT = "scripts/junction_saturation.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_OUTPUT_SOURCE = "lib/qcmodule/SAM.py:saturation_junction"
    OUTPUT_FILENAMES = (
        "output.junctionSaturation_plot.r",
        "output.junctionSaturation_plot.pdf",
    )
    REQUIRED_PATH_INPUTS = ("input", "refgene")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    ("BAM", "SAM"),
                    {"description": "BAM or SAM alignment file"},
                ),
                "refgene": (
                    "BED",
                    {"description": "Reference gene model in BED format"},
                ),
            },
            "optional": {
                "percentile_floor": (
                    "INT",
                    {"default": 5, "min": 0, "max": 100, "description": "Sampling floor percentile"},
                ),
                "percentile_ceiling": (
                    "INT",
                    {"default": 100, "min": 0, "max": 100, "description": "Sampling ceiling percentile"},
                ),
                "percentile_step": (
                    "INT",
                    {"default": 5, "min": 1, "max": 100, "description": "Sampling percentile step"},
                ),
                "min_intron": (
                    "INT",
                    {"default": 50, "min": 1, "description": "Minimum intron length in bp"},
                ),
                "min_coverage": (
                    "INT",
                    {"default": 1, "min": 1, "description": "Minimum supporting reads"},
                ),
                "mapq": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 255,
                        "description": "Minimum mapping quality",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        stale = sorted({key for key in ("percentiles_mode", "rscript_output") if key in inputs})
        if stale:
            return f"Legacy RSeQC controls are unsupported: {', '.join(stale)}"
        for key, default, minimum, maximum in (
            ("percentile_floor", 5, 0, 100),
            ("percentile_ceiling", 100, 0, 100),
            ("percentile_step", 5, 1, 100),
            ("min_intron", 50, 1, None),
            ("min_coverage", 1, 1, None),
            ("mapq", 30, 0, 255),
        ):
            validation = cls.validate_int(inputs.get(key, default), key, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        floor = inputs.get("percentile_floor", 5)
        ceiling = inputs.get("percentile_ceiling", 100)
        step = inputs.get("percentile_step", 5)
        if floor > ceiling:
            return "percentile_floor must be at most percentile_ceiling"
        if step > ceiling:
            return "percentile_step must be at most percentile_ceiling"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "junction_saturation.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs.get("input")),
                "-o",
                str(cls.output_prefix(inputs)),
                "-r",
                cls.path_value(inputs.get("refgene")),
                "-l",
                str(inputs.get("percentile_floor", 5)),
                "-u",
                str(inputs.get("percentile_ceiling", 100)),
                "-s",
                str(inputs.get("percentile_step", 5)),
                "-m",
                str(inputs.get("min_intron", 50)),
                "-v",
                str(inputs.get("min_coverage", 1)),
                "-q",
                str(inputs.get("mapq", 30)),
            ]
        )
        return command
