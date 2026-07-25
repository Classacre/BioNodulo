"""deepTools computeMatrix node pinned to 3.5.6."""

from __future__ import annotations

from typing import Any

from .adapter import DeepToolsCommandNode, deeptools_source_urls


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
    SOURCE_PATHS = (
        "deeptools/computeMatrix.py",
        "deeptools/parserCommon.py",
        "deeptools/heatmapper.py",
        "docs/content/tools/computeMatrix.rst",
        "pyproject.toml",
    )
    SOURCE_URLS = deeptools_source_urls(*SOURCE_PATHS)
    SOURCE_URL = SOURCE_URLS[0]
    UPSTREAM_SOURCE = "; ".join(SOURCE_PATHS[:3])

    MODES = ("reference-point", "scale-regions")
    REFERENCE_POINTS = ("TSS", "TES", "center")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bigwig": (
                    "BIGWIG",
                    {"multiple": True, "description": "One or more input bigWig signal tracks"},
                ),
                "regions": (
                    "FILE",
                    {"multiple": True, "description": "One or more BED or GTF region files"},
                ),
                "mode": ("STRING", {"default": "reference-point", "options": list(cls.MODES)}),
                "threads": ("INT", {"default": 1, "min": 1}),
            },
            "optional": {
                "reference_point": (
                    "STRING",
                    {"default": "TSS", "options": list(cls.REFERENCE_POINTS)},
                ),
                "before_region": (
                    "INT",
                    {
                        "default": None,
                        "min": 0,
                        "description": "Defaults to 500 in reference-point mode and 0 in scale-regions mode",
                    },
                ),
                "after_region": (
                    "INT",
                    {
                        "default": None,
                        "min": 0,
                        "description": "Defaults to 1500 in reference-point mode and 0 in scale-regions mode",
                    },
                ),
                "region_body_length": ("INT", {"default": 1000, "min": 1}),
                "bin_size": ("INT", {"default": 10, "min": 1}),
                "skip_zeros": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @staticmethod
    def _mode_distance(inputs: dict[str, Any], key: str, mode: str) -> Any:
        value = inputs.get(key)
        if value is not None:
            return value
        if mode == "scale-regions":
            return 0
        return 500 if key == "before_region" else 1500

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("bigwig", "regions"):
            validation = cls.require_paths(inputs, key)
            if validation is not True:
                return validation
        mode = str(inputs.get("mode", "reference-point"))
        if mode not in cls.MODES:
            return f"Unsupported computeMatrix mode: {mode}"
        if mode == "reference-point":
            reference_point = str(inputs.get("reference_point", "TSS"))
            if reference_point not in cls.REFERENCE_POINTS:
                return f"Unsupported computeMatrix reference point: {reference_point}"
        for key, default, minimum in (("threads", 1, 1), ("bin_size", 10, 1)):
            value = inputs.get(key, default)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                qualifier = "positive" if minimum == 1 else "non-negative"
                return f"{key} must be a {qualifier} integer"
        for key in ("before_region", "after_region"):
            value = cls._mode_distance(inputs, key, mode)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return f"{key} must be a non-negative integer"
        if mode == "scale-regions":
            body_length = inputs.get("region_body_length", 1000)
            if isinstance(body_length, bool) or not isinstance(body_length, int) or body_length < 1:
                return "region_body_length must be a positive integer"
        if (
            mode == "reference-point"
            and cls._mode_distance(inputs, "before_region", mode) == 0
            and cls._mode_distance(inputs, "after_region", mode) == 0
        ):
            return "reference-point mode requires before_region or after_region to be positive"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        mode = str(inputs.get("mode", "reference-point"))
        bigwigs = cls.path_values(inputs.get("bigwig"))
        regions = cls.path_values(inputs.get("regions"))
        command = [
            "computeMatrix",
            mode,
            "-S",
            *bigwigs,
            "-R",
            *regions,
            "-o",
            str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0]),
            "-p",
            str(inputs.get("threads", 1)),
            "--binSize",
            str(inputs.get("bin_size", 10)),
        ]
        if mode == "reference-point":
            command.extend(
                [
                    "--referencePoint",
                    str(inputs.get("reference_point", "TSS")),
                    "-b",
                    str(cls._mode_distance(inputs, "before_region", mode)),
                    "-a",
                    str(cls._mode_distance(inputs, "after_region", mode)),
                ]
            )
        else:
            command.extend(
                [
                    "-b",
                    str(cls._mode_distance(inputs, "before_region", mode)),
                    "-a",
                    str(cls._mode_distance(inputs, "after_region", mode)),
                    "--regionBodyLength",
                    str(inputs.get("region_body_length", 1000)),
                ]
            )
        if inputs.get("skip_zeros"):
            command.append("--skipZeros")
        return command
