"""deepTools computeMatrix node pinned to 3.5.6."""

from __future__ import annotations

from typing import Any

from .adapter import DeepToolsCommandNode


class DeepToolsComputeMatrixNode(DeepToolsCommandNode):
    """Prepare a gzipped signal matrix for deepTools plotting commands."""

    NODE_ID = "deeptools_compute_matrix"
    DISPLAY_NAME = "deepTools computeMatrix"
    DESCRIPTION = "Prepare signal matrices around genomic regions for deepTools plots"
    SEARCH_ALIASES = ["deeptools", "computematrix", "heatmap matrix", "signal profile"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("matrix",)
    REQUIRED_EXECUTABLES = ["computeMatrix"]
    OUTPUT_FILENAMES = ("matrix.gz",)
    DOCUMENTATION_URL = "https://deeptools.readthedocs.io/en/3.5.6/content/tools/computeMatrix.html"
    UPSTREAM_SOURCE = "deeptools/computeMatrix.py"

    MODES = ("reference-point", "scale-regions")
    REFERENCE_POINTS = ("TSS", "TES", "center")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bigwig": ("BIGWIG", {"description": "Input bigWig signal track"}),
                "regions": ("BED", {"description": "BED or GTF regions"}),
                "mode": ("STRING", {"default": "reference-point", "options": list(cls.MODES)}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "optional": {
                "reference_point": (
                    "STRING",
                    {"default": "TSS", "options": list(cls.REFERENCE_POINTS)},
                ),
                "before_region": ("INT", {"default": 500, "min": 0}),
                "after_region": ("INT", {"default": 1500, "min": 0}),
                "region_body_length": ("INT", {"default": 1000, "min": 1}),
                "bin_size": ("INT", {"default": 10, "min": 1}),
                "skip_zeros": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("bigwig", "regions"):
            validation = cls.require_path(inputs, key)
            if validation is not True:
                return validation
        mode = str(inputs.get("mode", "reference-point"))
        if mode not in cls.MODES:
            return f"Unsupported computeMatrix mode: {mode}"
        reference_point = str(inputs.get("reference_point", "TSS"))
        if reference_point not in cls.REFERENCE_POINTS:
            return f"Unsupported computeMatrix reference point: {reference_point}"
        for key, default, minimum in (
            ("threads", 1, 1),
            ("before_region", 500, 0),
            ("after_region", 1500, 0),
            ("region_body_length", 1000, 1),
            ("bin_size", 10, 1),
        ):
            value = inputs.get(key, default)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                qualifier = "positive" if minimum == 1 else "non-negative"
                return f"{key} must be a {qualifier} integer"
        if mode == "reference-point" and inputs.get("before_region", 500) == 0 and inputs.get("after_region", 1500) == 0:
            return "reference-point mode requires before_region or after_region to be positive"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        mode = str(inputs.get("mode", "reference-point"))
        command = [
            "computeMatrix",
            mode,
            "-S",
            str(inputs.get("bigwig", "")),
            "-R",
            str(inputs.get("regions", "")),
            "-o",
            str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0]),
            "-p",
            str(inputs.get("threads", 1)),
            "--binSize",
            str(inputs.get("bin_size", 10)),
        ]
        if mode == "reference-point":
            command.extend([
                "--referencePoint",
                str(inputs.get("reference_point", "TSS")),
                "-b",
                str(inputs.get("before_region", 500)),
                "-a",
                str(inputs.get("after_region", 1500)),
            ])
        else:
            command.extend([
                "-b",
                str(inputs.get("before_region", 0)),
                "-a",
                str(inputs.get("after_region", 0)),
                "--regionBodyLength",
                str(inputs.get("region_body_length", 1000)),
            ])
        if inputs.get("skip_zeros"):
            command.append("--skipZeros")
        return command
