"""Focused owner for ``hyphy_infer_stasis_clusters``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract

class HyPhyInferStasisClustersNode(ToolsIUCCommandContract):
    """Identify regional footprints of extreme purifying selection from B-STILL results."""

    NODE_ID = "hyphy_infer_stasis_clusters"
    DISPLAY_NAME = "HyPhy-Infer Stasis Clusters"
    REQUIRED_CONDA_PACKAGES = ["python", "numpy", "scipy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Identify regional footprints of extreme purifying selection from B-STILL results."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "B-STILL",
        "Infer Stasis Clusters",
        "stasis clusters",
        "purifying selection",
        "Empirical Bayes Factor",
        "hypergeometric scan statistic",
        "family-wise error rate",
        "protein domains",
    ]
    RETURN_TYPES = ("JSON", "TEXT")
    RETURN_NAMES = ("output_json", "output_log")
    REQUIRED_EXECUTABLES = ["python3"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/hyphy"
    CITATION_DOIS = [HYPHY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{HYPHY_CITATION_DOI}"]
    CITATION_TEXT = HYPHY_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True

    @staticmethod
    def _default_script_path() -> str:
        return str(Path(__file__).resolve().parents[1] / "scripts" / "infer_stasis_clusters.py")

    @classmethod
    def _script_path(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("script_path") or cls._default_script_path())

    @staticmethod
    def _validate_float_range(value: Any, message: str, low: float, high: float) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "python3",
            cls._script_path(inputs),
            str(inputs.get("input_json", "")),
            "--ebf",
            str(inputs.get("ebf", 10.0)),
            "--permutations",
            str(inputs.get("permutations", 10000)),
            "--alpha",
            str(inputs.get("alpha", 0.05)),
            "--max-cluster",
            str(inputs.get("max_cluster", 30)),
            "--merge",
            str(inputs.get("merge", 15)),
            "--output",
            f"{out}/output_json.json",
            ">",
            f"{out}/output_log.txt",
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output_json.json", out / "output_log.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_json", "")).strip():
            return "HyPhy-Infer Stasis Clusters B-STILL JSON input is required"
        message = cls._validate_float_range(
            inputs.get("ebf", 10.0), "HyPhy-Infer Stasis Clusters EBF threshold must be between 0 and 10000", 0, 10000
        )
        if message:
            return message
        message = cls._validate_int_range(
            inputs.get("permutations", 10000),
            "HyPhy-Infer Stasis Clusters permutations must be between 100 and 100000",
            100,
            100000,
        )
        if message:
            return message
        message = cls._validate_float_range(
            inputs.get("alpha", 0.05), "HyPhy-Infer Stasis Clusters alpha must be between 0.001 and 0.5", 0.001, 0.5
        )
        if message:
            return message
        message = cls._validate_int_range(
            inputs.get("max_cluster", 30),
            "HyPhy-Infer Stasis Clusters maximum cluster size must be between 3 and 100",
            3,
            100,
        )
        if message:
            return message
        message = cls._validate_int_range(
            inputs.get("merge", 15),
            "HyPhy-Infer Stasis Clusters merge distance must be between 0 and 100",
            0,
            100,
        )
        if message:
            return message
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_json": (
                    "JSON",
                    {"description": "JSON output file from HyPhy B-STILL analysis"},
                ),
            },
            "optional": {
                "ebf": (
                    "FLOAT",
                    {
                        "default": 10.0,
                        "min": 0,
                        "max": 10000,
                        "description": "Empirical Bayes Factor threshold for identifying stasis sites",
                    },
                ),
                "permutations": (
                    "INT",
                    {
                        "default": 10000,
                        "min": 100,
                        "max": 100000,
                        "description": "Permutations for family-wise error rate control",
                    },
                ),
                "alpha": (
                    "FLOAT",
                    {
                        "default": 0.05,
                        "min": 0.001,
                        "max": 0.5,
                        "description": "Family-wise error rate threshold",
                    },
                ),
                "max_cluster": (
                    "INT",
                    {
                        "default": 30,
                        "min": 3,
                        "max": 100,
                        "description": "Maximum number of stasis sites per interval scan",
                        "advanced": True,
                    },
                ),
                "merge": (
                    "INT",
                    {
                        "default": 15,
                        "min": 0,
                        "max": 100,
                        "description": "Distance in codons to merge adjacent clusters",
                        "advanced": True,
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": cls._default_script_path(),
                        "description": "Path to the Galaxy infer_stasis_clusters.py helper script",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
