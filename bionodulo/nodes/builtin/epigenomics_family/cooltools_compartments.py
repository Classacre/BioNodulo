"""Cooltools 0.7.0 eigs-cis contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import EpigenomicsCommandNode, path_value, safe_output_stem


def _uri_path(value: Any) -> str:
    return str(value).partition("::")[0]


class CooltoolsCompartmentsNode(EpigenomicsCommandNode):
    """Calculate cis eigenvectors and eigenvalues from a balanced cooler."""

    NODE_ID = "cooltools_compartments"
    DISPLAY_NAME = "cooltools Compartments"
    DESCRIPTION = "Call A/B compartments with cooltools eigs-cis from a balanced Hi-C matrix."
    SEARCH_ALIASES = ["cooltools", "hic", "compartments", "eigs-cis", "eigenvector", "a/b compartments"]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("compartment_track", "eigenvalues")
    REQUIRED_EXECUTABLES = ["cooltools"]
    REQUIRED_CONDA_PACKAGES = ["cooltools"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cooler_uri": ("FILE", {"description": "Balanced .cool/.mcool URI, optionally with ::resolutions/bin"}),
            },
            "optional": {
                "phasing_track": ("TSV", {"description": "BedGraph-like track, optionally path::value_column"}),
                "view_file": ("BED", {"description": "Sorted genomic view BED"}),
                "n_eigs": ("INT", {"default": 3, "min": 1, "max": 10}),
                "clr_weight_name": ("STRING", {"default": "weight"}),
                "ignore_diags": ("INT", {"min": 0, "description": "Omit to reuse the balancing metadata"}),
                "output_prefix": ("STRING", {"default": "compartments"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if path_value(_uri_path(inputs.get("cooler_uri", ""))) is None:
            return "cooler_uri is required"
        if int(inputs.get("n_eigs", 3)) < 1:
            return "n_eigs must be at least 1."
        ignore_diags = inputs.get("ignore_diags")
        if ignore_diags is not None and int(ignore_diags) < 0:
            return "ignore_diags must be zero or greater."
        return True

    @classmethod
    def _out_prefix(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        return Path(output_dir) / safe_output_stem(inputs.get("output_prefix"), "compartments")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        cmd = ["cooltools", "eigs-cis"]
        if inputs.get("phasing_track"):
            cmd.extend(["--phasing-track", str(inputs["phasing_track"])])
        if inputs.get("view_file"):
            cmd.extend(["--view", str(inputs["view_file"])])
        cmd.extend(["--n-eigs", str(inputs.get("n_eigs", 3))])
        if inputs.get("clr_weight_name"):
            cmd.extend(["--clr-weight-name", str(inputs["clr_weight_name"])])
        if inputs.get("ignore_diags") is not None:
            cmd.extend(["--ignore-diags", str(inputs["ignore_diags"])])
        cmd.extend([
            "--out-prefix",
            str(cls._out_prefix(inputs, inputs.get("output", "."))),
            str(inputs["cooler_uri"]),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = cls._out_prefix(inputs, node_out)
        return [Path(f"{prefix}.cis.vecs.tsv"), Path(f"{prefix}.cis.lam.txt")]
