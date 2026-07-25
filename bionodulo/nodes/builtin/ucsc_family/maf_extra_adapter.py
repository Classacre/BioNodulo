"""UCSC MAF coverage and AXT conversion nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    KENT_482_GIT_COMMIT,
    KENT_GIT_URL,
    pin_contract,
    ucsc_db_command,
)

class UcscMafCoverageNode(CommandNode):
    """Measure genome coverage from UCSC MAF alignments."""

    LEGACY_NODE_ID = "ucsc_mafcoverage"
    DISPLAY_NAME = "mafCoverage"
    REQUIRED_CONDA_PACKAGES = ["ucsc-mafcoverage"]
    CATEGORY = "genomics"
    DESCRIPTION = "Analyse chromosome and genome-wide coverage from sorted UCSC MAF alignments."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafCoverage",
        "ucsc_mafcoverage",
        "mafCoverage",
        "MAF coverage",
        "multiple alignment format",
        "genome-wide coverage",
        "restricted coverage",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["mafCoverage"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/mouseStuff/mafCoverage/mafCoverage.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    SHELL = True

    RESTRICT_OPTIONS = ["no", "yes"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/coverage.txt"

    @classmethod
    def _restrict_select(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("restrict_select", "no") or "no")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "mafCoverage",
            str(inputs.get("genome", "")),
            str(inputs.get("maf_file", "")),
        ]
        if cls._restrict_select(inputs) == "yes":
            cmd.append(f"-restrict={inputs.get('restrict_bed', '')}")
        if str(inputs.get("count", "")) != "":
            cmd.append(f"-count={inputs.get('count')}")
        cmd.extend([">", cls._output_path(inputs)])
        return ucsc_db_command(inputs, cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "coverage.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("maf_file", "")).strip():
            return "maf_file is required"
        if not str(inputs.get("genome", "")).strip():
            return "genome is required"
        restrict_select = cls._restrict_select(inputs)
        if restrict_select not in cls.RESTRICT_OPTIONS:
            return f"restrict_select must be one of: {', '.join(cls.RESTRICT_OPTIONS)}"
        if restrict_select == "yes" and not str(inputs.get("restrict_bed", "")).strip():
            return "restrict_bed is required when restrict_select is yes"
        count = inputs.get("count", "")
        if str(count) != "":
            try:
                count_value = int(count)
            except (TypeError, ValueError):
                return "count must be an integer"
            if count_value < 1:
                return "count must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "maf_file": ("FILE", {"description": "Sorted UCSC MAF alignment file"}),
                "genome": ("STRING", {"description": "UCSC genome database name"}),
            },
            "optional": {
                "restrict_select": (
                    "STRING",
                    {
                        "default": "no",
                        "options": cls.RESTRICT_OPTIONS,
                        "description": "Restrict coverage calculation to regions in a BED file",
                    },
                ),
                "restrict_bed": (
                    "BED",
                    {"description": "BED intervals used when restricted coverage is enabled"},
                ),
                "count": (
                    "INT",
                    {"default": "", "min": 1, "description": "Threshold for bases covered by at least this many species"},
                ),
                "ucsc_db_connection": (
                    "FILE",
                    {"description": "Optional UCSC database config; defaults to the pinned public Galaxy config"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
class MafToAxtNode(CommandNode):
    """Convert UCSC MAF alignments to AXT format."""

    LEGACY_NODE_ID = "maftoaxt"
    DISPLAY_NAME = "mafToAxt"
    REQUIRED_CONDA_PACKAGES = ["ucsc-maftoaxt"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert a UCSC MAF multiple-alignment file to AXT pairwise alignment format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "maftoaxt",
        "mafToAxt",
        "MAF to AXT",
        "multiple alignment format",
        "pairwise alignment",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["mafToAxt"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/axt.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    TARGET_MODES = ["", "customTar"]

    @classmethod
    def _target_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("tarSeq", "") or "")

    @classmethod
    def _target_sequence(cls, inputs: dict[str, Any]) -> str:
        if cls._target_mode(inputs) == "customTar":
            return str(inputs.get("targetSeq", ""))
        return "first"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.axt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "mafToAxt",
            str(inputs.get("in_maf", "")),
            cls._target_sequence(inputs),
            str(inputs.get("querySeq", "")),
            cls._output_path(inputs),
        ]
        if inputs.get("stripDb"):
            cmd.append("-stripDb")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.axt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_maf", "")).strip():
            return "in_maf is required"
        if not str(inputs.get("querySeq", "")).strip():
            return "querySeq is required"
        target_mode = cls._target_mode(inputs)
        if target_mode not in cls.TARGET_MODES:
            return f"tarSeq must be one of: {', '.join(cls.TARGET_MODES)}"
        if target_mode == "customTar" and not str(inputs.get("targetSeq", "")).strip():
            return "targetSeq is required when tarSeq is customTar"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_maf": ("FILE", {"description": "UCSC MAF multiple-alignment file to convert"}),
                "querySeq": ("STRING", {"description": "Sequence name to use as the query sequence"}),
            },
            "optional": {
                "tarSeq": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.TARGET_MODES,
                        "description": "Use the first MAF block sequence or a custom target sequence name",
                    },
                ),
                "targetSeq": (
                    "STRING",
                    {"default": "", "description": "Target sequence name used when tarSeq is customTar"},
                ),
                "stripDb": (
                    "BOOLEAN",
                    {"default": False, "description": "Strip database prefixes up to the first period in sequence names"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


_KENT_482_NODES = [UcscMafCoverageNode, MafToAxtNode]
pin_contract(
    _KENT_482_NODES,
    runtime_version="482",
    runtime_git_url=KENT_GIT_URL,
    runtime_git_commit=KENT_482_GIT_COMMIT,
)
for _node_class in _KENT_482_NODES:
    _node_class.PACKAGE_CONSTRAINT = "; ".join(
        f"{package}==482" for package in _node_class.REQUIRED_CONDA_PACKAGES
    )
