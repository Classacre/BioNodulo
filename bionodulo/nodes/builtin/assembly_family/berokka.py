"""Focused berokka node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_core_data_family.evidence import pin_contract

class BerokkaNode(CommandNode):
    """Trim, circularise, orient, and filter long-read bacterial assemblies."""

    NODE_ID = "berokka"
    DISPLAY_NAME = "Berokka"
    REQUIRED_CONDA_PACKAGES = ["berokka"]
    CATEGORY = "assembly"
    DESCRIPTION = "Trim, circularise, orient and filter long read bacterial genome assemblies."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "berokka",
        "Berokka",
        "trim circularise orient",
        "long read bacterial genome assemblies",
        "completed assemblies",
        "CANU",
        "HGAP",
        "Circlator",
        "PacBio control sequence",
    ]
    RETURN_TYPES = ("FASTA", "TSV")
    RETURN_NAMES = ("trimmed", "results")
    REQUIRED_EXECUTABLES = ["berokka"]
    DOCUMENTATION_URL = BEROKKA_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BEROKKA_CITATION_URL]
    CITATION_TEXT = BEROKKA_CITATION_TEXT
    VERSION = "0.2.3"
    SHELL = True

    @classmethod
    def _read_length(cls, inputs: dict[str, Any]) -> int:
        return int(inputs.get("read_length", 60000) or 60000)

    @classmethod
    def _fuzz(cls, inputs: dict[str, Any]) -> int:
        return int(inputs.get("fuzz", 5) or 5)

    @classmethod
    def _work_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/default"

    @classmethod
    def _trimmed_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/trimmed.fasta"

    @classmethod
    def _results_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/results.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "berokka",
            "--outdir",
            cls._work_dir(inputs),
            str(inputs.get("input_file", "")),
        ]
        _add_if_value(cmd, "--filter", inputs.get("filter_fasta"))
        cmd.extend(["--readlen", str(cls._read_length(inputs)), "--fuzz", str(cls._fuzz(inputs))])
        if inputs.get("anno", True) is False:
            cmd.append("--noanno")
        cmd.extend(
            [
                "&&",
                "cp",
                f"{cls._work_dir(inputs)}/02.trimmed.fa",
                cls._trimmed_path(inputs),
                "&&",
                "cp",
                f"{cls._work_dir(inputs)}/03.results.tab",
                cls._results_path(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "trimmed.fasta", out / "results.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        try:
            read_length = cls._read_length(inputs)
        except (TypeError, ValueError):
            return "read_length must be an integer"
        if read_length < 28:
            return "read_length must be at least 28"
        try:
            cls._fuzz(inputs)
        except (TypeError, ValueError):
            return "fuzz must be an integer"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "FASTA",
                    {"description": "Completed long-read assembly FASTA, such as CANU or HGAP contigs"},
                ),
            },
            "optional": {
                "filter_fasta": (
                    "FASTA",
                    {"default": "", "description": "Optional FASTA whose matching contigs are filtered out"},
                ),
                "read_length": (
                    "INT",
                    {
                        "default": 60000,
                        "min": 28,
                        "description": "Approximate maximum read length used for circularisation matching",
                    },
                ),
                "fuzz": (
                    "INT",
                    {"default": 5, "description": "Accept local alignment within this many bp of global alignment"},
                ),
                "anno": (
                    "BOOLEAN",
                    {"default": True, "description": "Annotate trimmed FASTA descriptions"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(BerokkaNode)

__all__ = ['BerokkaNode']
