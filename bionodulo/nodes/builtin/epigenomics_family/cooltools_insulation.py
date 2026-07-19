"""Cooltools 0.7.0 insulation contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import EpigenomicsCommandNode, path_value, split_values


class CooltoolsInsulationNode(EpigenomicsCommandNode):
    """Calculate diamond insulation scores and call boundaries."""

    NODE_ID = "cooltools_insulation"
    DISPLAY_NAME = "cooltools Insulation"
    DESCRIPTION = "Calculate diamond insulation scores and boundary strengths with cooltools."
    SEARCH_ALIASES = ["cooltools", "hic", "insulation", "boundaries", "tad", "domains"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("insulation",)
    REQUIRED_EXECUTABLES = ["cooltools"]
    REQUIRED_CONDA_PACKAGES = ["cooltools"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cooler_uri": ("FILE", {"description": "Balanced .cool/.mcool URI, optionally with ::resolutions/bin"}),
                "window_sizes": ("STRING", {"default": "100000", "description": "Comma/space-separated windows"}),
            },
            "optional": {
                "view_file": ("BED", {"description": "Sorted genomic view BED"}),
                "nproc": ("INT", {"default": 1, "min": 1, "max": 64}),
                "clr_weight_name": ("STRING", {"default": "weight", "description": "Empty string requests raw data"}),
                "ignore_diags": ("INT", {"min": 0, "description": "Omit to reuse balancing metadata"}),
                "min_frac_valid_pixels": ("FLOAT", {"default": 0.66, "min": 0.0, "max": 1.0}),
                "min_dist_bad_bin": ("INT", {"default": 0, "min": 0}),
                "threshold": ("STRING", {"default": "0", "description": "Li, Otsu, or a numeric threshold"}),
                "window_pixels": ("BOOLEAN", {"default": False}),
                "append_raw_scores": ("BOOLEAN", {"default": False}),
                "chunksize": ("INT", {"default": 20000000, "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if path_value(str(inputs.get("cooler_uri", "")).partition("::")[0]) is None:
            return "cooler_uri is required"
        windows = split_values(inputs.get("window_sizes"))
        if not windows:
            return "At least one window size is required."
        try:
            if any(int(window) <= 0 for window in windows):
                return "window sizes must be positive integers."
        except ValueError:
            return "window sizes must be positive integers."
        if int(inputs.get("nproc", 1)) < 1:
            return "nproc must be at least 1."
        ignore_diags = inputs.get("ignore_diags")
        if ignore_diags is not None and int(ignore_diags) < 0:
            return "ignore_diags must be zero or greater."
        fraction = float(inputs.get("min_frac_valid_pixels", 0.66))
        if not 0 <= fraction <= 1:
            return "min_frac_valid_pixels must be between 0 and 1."
        if int(inputs.get("min_dist_bad_bin", 0)) < 0:
            return "min_dist_bad_bin must be zero or greater."
        chunksize = inputs.get("chunksize", 20000000)
        if chunksize is not None and int(chunksize) < 1:
            return "chunksize must be at least 1."
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output = Path(str(inputs.get("output", "."))) / "insulation.tsv"
        cmd = ["cooltools", "insulation", "--nproc", str(inputs.get("nproc", 1)), "--output", str(output)]
        if inputs.get("view_file"):
            cmd.extend(["--view", str(inputs["view_file"])])
        if "clr_weight_name" in inputs and inputs.get("clr_weight_name") is not None:
            cmd.extend(["--clr-weight-name", str(inputs["clr_weight_name"])])
        if inputs.get("ignore_diags") is not None:
            cmd.extend(["--ignore-diags", str(inputs["ignore_diags"])])
        if inputs.get("min_frac_valid_pixels") is not None:
            cmd.extend(["--min-frac-valid-pixels", str(inputs["min_frac_valid_pixels"])])
        if inputs.get("min_dist_bad_bin") is not None:
            cmd.extend(["--min-dist-bad-bin", str(inputs["min_dist_bad_bin"])])
        if inputs.get("threshold") not in (None, ""):
            cmd.extend(["--threshold", str(inputs["threshold"])])
        if inputs.get("window_pixels"):
            cmd.append("--window-pixels")
        if inputs.get("append_raw_scores"):
            cmd.append("--append-raw-scores")
        if inputs.get("chunksize") is not None:
            cmd.extend(["--chunksize", str(inputs["chunksize"])])
        cmd.append(str(inputs["cooler_uri"]))
        cmd.extend(split_values(inputs.get("window_sizes")))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "insulation.tsv"]
