"""Focused owner for ``mash_screen``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from ..contracts import ToolsIUCCommandContract

class MashScreenNode(ToolsIUCCommandContract):
    """Estimate how well Mash sketch queries are contained in a read pool."""

    NODE_ID = "mash_screen"
    DISPLAY_NAME = "Mash Screen"
    REQUIRED_CONDA_PACKAGES = ["mash"]
    CATEGORY = "genomics"
    DESCRIPTION = "Screen reads against a Mash sketch database to estimate sequence containment."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mash",
        "mash screen",
        "containment",
        "metagenome screen",
        "genome discovery",
        "read screening",
        "minhash",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("screen",)
    REQUIRED_EXECUTABLES = ["mash"]
    DOCUMENTATION_URL = "https://mash.readthedocs.io/en/latest/tutorials.html#screening-a-read-set-for-containment-of-refseq-genomes"
    CITATION_DOIS = ["10.1186/s13059-019-1841-x", "10.1186/s13059-016-0997-x"]
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = (
        "Mash Screen: high-throughput sequence containment estimation for genome discovery; "
        "Mash: fast genome and metagenome distance estimation using MinHash."
    )
    VERSION = "2.3"
    SHELL = True

    @classmethod
    def _pool_files(cls, inputs: dict[str, Any]) -> list[str]:
        mode = str(inputs.get("pool_input_selector", inputs.get("reads_input_selector", "single")))
        if mode == "paired":
            return [str(inputs.get("pool_1", inputs.get("reads_1", ""))), str(inputs.get("pool_2", inputs.get("reads_2", "")))]
        if mode == "paired_collection":
            pool = inputs.get("pool", inputs.get("reads", {}))
            if isinstance(pool, dict):
                return [str(pool.get("forward", pool.get("reads_1", ""))), str(pool.get("reverse", pool.get("reads_2", "")))]
            paired = _as_list(pool)
            return paired[:2]
        return [str(inputs.get("pool", inputs.get("reads", "")))]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        queries = str(inputs.get("queries", inputs.get("query_sketch", "")))
        cmd = ["mash", "screen"]
        if inputs.get("winner_takes_all", True):
            cmd.append("-w")
        cmd.extend(
            [
                "-i",
                str(inputs.get("minimum_identity_to_report", inputs.get("minimum_identity", 0.0))),
                "-v",
                str(inputs.get("maximum_p_value_to_report", inputs.get("maximum_p_value", 1.0))),
                "queries.msh",
                *cls._pool_files(inputs),
            ]
        )
        return f"ln -sf {shlex.quote(queries)} queries.msh && {shlex.join(cmd)} > {shlex.quote(f'{out}/screen.tsv')}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "screen.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("queries", inputs.get("query_sketch", ""))).strip():
            return "Mash screen query sketch is required"
        mode = str(inputs.get("pool_input_selector", inputs.get("reads_input_selector", "single")))
        if mode not in {"single", "paired", "paired_collection"}:
            return "Mash screen pool layout must be single, paired, or paired_collection"
        pool_files = cls._pool_files(inputs)
        if len(pool_files) != (2 if mode != "single" else 1) or any(not path.strip() for path in pool_files):
            return f"Mash screen {mode} mode requires all read inputs"
        try:
            identity = float(inputs.get("minimum_identity_to_report", inputs.get("minimum_identity", 0.0)))
            pvalue = float(inputs.get("maximum_p_value_to_report", inputs.get("maximum_p_value", 1.0)))
        except (TypeError, ValueError):
            return "Mash screen thresholds must be numeric"
        if not -1 <= identity <= 1:
            return "Mash screen minimum identity must be between -1 and 1"
        if not 0 <= pvalue <= 1:
            return "Mash screen maximum p-value must be between 0 and 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "queries": ("FILE", {"description": "Mash sketch database containing query genomes or sequences"}),
                "pool_input_selector": ("STRING", {"default": "single", "options": ["paired", "single", "paired_collection"], "description": "Read input layout"}),
                "pool": ("FASTQ", {"description": "Single-end reads or paired collection to screen"}),
                "pool_1": ("FASTQ", {"description": "Forward reads for paired mode"}),
                "pool_2": ("FASTQ", {"description": "Reverse reads for paired mode"}),
            },
            "optional": {
                "winner_takes_all": ("BOOLEAN", {"default": True, "description": "Use winner-takes-all mode to reduce redundant matches"}),
                "minimum_identity_to_report": ("FLOAT", {"default": 0.0, "min": -1.0, "max": 1.0, "description": "Minimum identity to report"}),
                "maximum_p_value_to_report": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "description": "Maximum p-value to report"}),
            },
            "hidden": {"output": ("STRING", {})},
        }
