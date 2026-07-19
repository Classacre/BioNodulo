"""Focused fasta regex node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class FastaRegexFinderNode(CommandNode):
    """Search FASTA sequences for regular-expression matches and emit BED coordinates."""

    NODE_ID = "fasta_regex_finder"
    DISPLAY_NAME = "Fasta regular expression finder"
    REQUIRED_CONDA_PACKAGES = ["python"]
    CATEGORY = "sequence"
    DESCRIPTION = "Search FASTA sequences for regular-expression matches and report BED coordinates."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "fasta_regex_finder",
        "fastaRegexFinder",
        "FASTA regex",
        "regular expression finder",
        "motif search",
        "G-quadruplex",
        "BED coordinates",
        "reverse complement",
    ]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = FASTA_REGEX_FINDER_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [FASTA_REGEX_FINDER_CITATION_URL]
    CITATION_TEXT = FASTA_REGEX_FINDER_CITATION_TEXT
    VERSION = "0.1.0"
    SHELL = True

    ADVANCED_MODES = ["simple", "advanced"]
    DEFAULT_REGEX = r"([gG]{3,}\w{1,7}){3,}[gG]{3,}"

    @classmethod
    def _advanced(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("advanced", "simple") or "simple")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.bed"

    @classmethod
    def _maxstr(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get("maxstr", 10000)
        if value is None or str(value) == "":
            return 10000
        return int(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "fastaregexfinder.py") or "fastaregexfinder.py"),
            "--fasta",
            str(inputs.get("input", "")),
            "--regex",
            str(inputs.get("regex", cls.DEFAULT_REGEX) or cls.DEFAULT_REGEX),
        ]
        if cls._advanced(inputs) == "advanced":
            if inputs.get("matchcase"):
                cmd.append("--matchcase")
            if inputs.get("noreverse"):
                cmd.append("--noreverse")
            cmd.extend(["--maxstr", str(cls._maxstr(inputs))])
            _add_if_value(cmd, "--seqnames", inputs.get("seqnames"))
        cmd.extend(["--quiet", ">", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.bed"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not str(inputs.get("regex", cls.DEFAULT_REGEX)).strip():
            return "regex is required"
        advanced = cls._advanced(inputs)
        if advanced not in cls.ADVANCED_MODES:
            return f"advanced must be one of: {', '.join(cls.ADVANCED_MODES)}"
        if advanced == "advanced":
            try:
                maxstr = cls._maxstr(inputs)
            except (TypeError, ValueError):
                return "maxstr must be an integer"
            if maxstr < 1:
                return "maxstr must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "FASTA sequences to search"}),
            },
            "optional": {
                "regex": (
                    "STRING",
                    {"default": cls.DEFAULT_REGEX, "description": "Regular expression searched in the FASTA input"},
                ),
                "advanced": (
                    "STRING",
                    {"default": "simple", "options": cls.ADVANCED_MODES, "description": "Expose advanced search controls"},
                ),
                "matchcase": ("BOOLEAN", {"default": False, "description": "Match case instead of ignoring case"}),
                "noreverse": ("BOOLEAN", {"default": False, "description": "Do not search the reverse complement"}),
                "maxstr": ("INT", {"default": 10000, "min": 1, "description": "Maximum length of matched sequence to report"}),
                "seqnames": (
                    "STRING",
                    {"default": "", "description": "Space-separated FASTA sequence names to search in advanced mode"},
                ),
                "script_path": (
                    "FILE",
                    {"default": "fastaregexfinder.py", "advanced": True, "description": "Path to the fastaRegexFinder script"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(FastaRegexFinderNode)

__all__ = ['FastaRegexFinderNode']
