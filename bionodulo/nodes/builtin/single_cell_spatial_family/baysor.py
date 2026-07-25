"""Baysor 0.7.1 molecular segmentation contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .adapter import path_value, validate_int, validate_number


class BaysorNode(CommandNode):
    """Segment imaging-based transcript coordinates with ``baysor run``."""

    NODE_ID = "baysor"
    DISPLAY_NAME = "Baysor Segmentation"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Segment MERFISH, Xenium, and related molecule-coordinate data with Baysor 0.7.1."
    SEARCH_ALIASES = ["BioNodulo builtin", "Baysor", "segmentation", "MERFISH", "Xenium"]
    RETURN_TYPES = ("CSV", "CSV", "FILE", "JSON", "JSON")
    RETURN_NAMES = ("cell_segmentation", "cell_stats", "count_matrix", "polygons_2d", "polygons_3d")
    REQUIRED_EXECUTABLES = ["baysor"]
    REQUIRED_CONDA_PACKAGES = ["baysor"]
    CONDA_PACKAGE_CONSTRAINTS = {"baysor": "0.7.1"}
    VERSION = "0.7.1"
    GIT_URL = "https://github.com/kharchenkolab/Baysor.git"
    GIT_COMMIT = "109850599ea026b7d70c7cf96bc6de14740f827d"
    SOURCE_TAG = "v0.7.1"
    DOCUMENTATION_URL = "https://kharchenkolab.github.io/Baysor/stable/segmentation/"
    UPSTREAM_SOURCE = "src/cli/main.jl; src/utils/cli.jl; src/utils/options.jl; docs/src/run.md"
    PACKAGE_CONSTRAINT = "Bioconda baysor=0.7.1"
    SHELL = False
    RUN_IN_NODE_OUTPUT_DIR = True
    EXIT_SEMANTICS = (
        "Baysor returns 0 after saving segmentation, cell statistics, the selected count matrix, and requested polygons; "
        "missing scale/prior segmentation, invalid options, non-zero exit, or missing outputs fail the node."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "transcript_data": ("FILE", {"description": "Molecule coordinates in CSV or Parquet form"}),
                "x_col": ("STRING", {"default": "x"}),
                "y_col": ("STRING", {"default": "y"}),
                "gene_col": ("STRING", {"default": "gene"}),
            },
            "optional": {
                "z_col": ("STRING", {"default": "", "description": "Optional z-coordinate column"}),
                "scale": (
                    "FLOAT",
                    {"default": None, "min": 0.0, "description": "Positive approximate cell radius"},
                ),
                "prior_segmentation": (
                    "FILE",
                    {"default": "", "description": "Prior segmentation image or MAT file"},
                ),
                "prior_segmentation_column": (
                    "STRING",
                    {"default": "", "description": "Coordinate-table column containing prior labels"},
                ),
                "min_molecules": ("INT", {"default": 30, "min": 1}),
                "n_clusters": ("INT", {"default": 4, "min": 1}),
                "iters": ("INT", {"default": 500, "min": 1}),
                "count_matrix_format": ("STRING", {"default": "loom", "options": ["loom", "tsv"]}),
                "polygon_format": (
                    "STRING",
                    {
                        "default": "FeatureCollection",
                        "options": ["FeatureCollection", "GeometryCollection", "GeometryCollectionLegacy", "none"],
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _output_paths(
        cls,
        output_dir: str | Path,
        count_matrix_format: str,
        polygon_format: str,
        z_col: str,
    ) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        outputs = [
            node_dir / "segmentation.csv",
            node_dir / "segmentation_cell_stats.csv",
            node_dir / f"segmentation_counts.{count_matrix_format}",
        ]
        if polygon_format != "none":
            outputs.append(node_dir / "segmentation_polygons_2d.json")
            if z_col.strip():
                outputs.append(node_dir / "segmentation_polygons_3d.json")
        return outputs

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._output_paths(
            output_dir,
            str(inputs.get("count_matrix_format", "loom") or "loom"),
            str(inputs.get("polygon_format", "FeatureCollection") or "FeatureCollection"),
            str(inputs.get("z_col", "") or ""),
        )

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not path_value(inputs.get("transcript_data")):
            return "Input 'transcript_data' must be a non-empty path-like value"
        for key in ("x_col", "y_col", "gene_col"):
            if not str(inputs.get(key, "") or "").strip():
                return f"Input '{key}' must not be empty"
        scale = inputs.get("scale")
        prior_file = path_value(inputs.get("prior_segmentation"))
        prior_column = str(inputs.get("prior_segmentation_column", "") or "").strip()
        if prior_file and prior_column:
            return "Provide either 'prior_segmentation' or 'prior_segmentation_column', not both"
        if scale is None and not prior_file and not prior_column:
            return "Baysor requires a positive 'scale' or prior segmentation"
        if scale is not None:
            validation = validate_number(scale, "scale", minimum=0.0)
            if validation is not True:
                return validation
            if float(scale) <= 0:
                return "Input 'scale' must be greater than 0"
        for key, default in (("min_molecules", 30), ("n_clusters", 4), ("iters", 500)):
            validation = validate_int(inputs.get(key, default), key, minimum=1)
            if validation is not True:
                return validation
        if str(inputs.get("count_matrix_format", "loom")) not in {"loom", "tsv"}:
            return "Input 'count_matrix_format' must be one of: loom, tsv"
        if str(inputs.get("polygon_format", "FeatureCollection")) not in {
            "FeatureCollection",
            "GeometryCollection",
            "GeometryCollectionLegacy",
            "none",
        }:
            return "Input 'polygon_format' is not supported by Baysor 0.7.1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output_file = Path(path_value(inputs.get("output"))) / "segmentation.csv"
        command = [
            "baysor",
            "run",
            "-x",
            str(inputs.get("x_col", "x")),
            "-y",
            str(inputs.get("y_col", "y")),
            "-g",
            str(inputs.get("gene_col", "gene")),
            "-m",
            str(inputs.get("min_molecules", 30)),
            "--n-clusters",
            str(inputs.get("n_clusters", 4)),
            f"--config.segmentation.iters={inputs.get('iters', 500)}",
            "--count-matrix-format",
            str(inputs.get("count_matrix_format", "loom")),
            "--polygon-format",
            str(inputs.get("polygon_format", "FeatureCollection")),
            "-o",
            str(output_file),
        ]
        z_col = str(inputs.get("z_col", "") or "").strip()
        if z_col:
            command.extend(["-z", z_col])
        if inputs.get("scale") is not None:
            command.extend(["-s", str(inputs["scale"])])
        command.append(path_value(inputs.get("transcript_data")))
        prior_file = path_value(inputs.get("prior_segmentation"))
        prior_column = str(inputs.get("prior_segmentation_column", "") or "").strip()
        if prior_file:
            command.append(prior_file)
        elif prior_column:
            command.append(f":{prior_column.lstrip(':')}")
        return command
