"""UCSC alignment and chain construction nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    KENT_482_GIT_COMMIT,
    KENT_GIT_URL,
    pin_contract,
)

class UcscAxtChainNode(CommandNode):
    """Chain UCSC AXT or PSL pairwise alignments."""

    LEGACY_NODE_ID = "ucsc_axtchain"
    DISPLAY_NAME = "axtChain"
    REQUIRED_CONDA_PACKAGES = ["ucsc-axtchain"]
    CATEGORY = "genomics"
    DESCRIPTION = "Chain together UCSC AXT or PSL pairwise alignments into chain format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_axtchain",
        "axtChain",
        "chain together axt",
        "AXT chain",
        "PSL chain",
        "linear gap costs",
    ]
    RETURN_TYPES = ("FILE", "TXT")
    RETURN_NAMES = ("out", "out_details")
    REQUIRED_EXECUTABLES = ["axtChain", "gzip"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/mouseStuff/axtChain/axtChain.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy2"
    SHELL = True

    ALIGNMENT_FORMATS = ["axt", "psl"]
    LINEAR_GAP_OPTIONS = ["loose", "medium", "linear_gap_file"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.chain"

    @classmethod
    def _details_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_details.txt"

    @classmethod
    def _alignment_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("alignment_format", "") or "")

    @classmethod
    def _linear_gap(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("linear_gap", "loose") or "loose")

    @classmethod
    def _linear_gap_value(cls, inputs: dict[str, Any]) -> str:
        if cls._linear_gap(inputs) == "linear_gap_file":
            return str(inputs.get("lineargap_input", ""))
        return cls._linear_gap(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["axtChain", "-faQ", "-faT"]
        if cls._alignment_format(inputs) == "psl":
            cmd.append("-psl")
        if str(inputs.get("minScore", "")) != "":
            cmd.append(f"-minScore={inputs.get('minScore')}")
        if str(inputs.get("scoreScheme", "")) != "":
            cmd.append(f"-scoreScheme={inputs.get('scoreScheme')}")
        if inputs.get("details_output"):
            cmd.append(f"-details={cls._details_path(inputs)}")
        cmd.append(f"-linearGap={cls._linear_gap_value(inputs)}")
        command = _shell_join(cmd)
        aln = shlex.quote(str(inputs.get("in_aln", "")))
        tail = _shell_join(
            [
                str(inputs.get("in_target", "")),
                str(inputs.get("in_query", "")),
                cls._output_path(inputs),
            ]
        )
        return f"{command} <(gzip -cdfq {aln}) {tail}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "out.chain"]
        if inputs.get("details_output", False):
            outputs.append(out / "out_details.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("in_aln", "in_target", "in_query"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        selected_format = str(inputs.get("alignment_format", "") or "")
        if not selected_format:
            return "alignment_format is required because staged paths do not preserve AXT/PSL suffix semantics"
        if selected_format not in cls.ALIGNMENT_FORMATS:
            return f"alignment_format must be one of: {', '.join(cls.ALIGNMENT_FORMATS)}"
        linear_gap = cls._linear_gap(inputs)
        if linear_gap not in cls.LINEAR_GAP_OPTIONS:
            return f"linear_gap must be one of: {', '.join(cls.LINEAR_GAP_OPTIONS)}"
        if linear_gap == "linear_gap_file" and not str(inputs.get("lineargap_input", "")).strip():
            return "lineargap_input is required when linear_gap is linear_gap_file"
        if str(inputs.get("minScore", "")) != "" and int(inputs.get("minScore")) < 0:
            return "minScore must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_aln": (
                    "FILE",
                    {"description": "Pairwise AXT or PSL alignments, optionally gzip-compressed"},
                ),
                "in_target": ("FASTA", {"description": "Target FASTA sequence file matching alignment target names"}),
                "in_query": ("FASTA", {"description": "Query FASTA sequence file matching alignment query names"}),
                "alignment_format": (
                    "STRING",
                    {
                        "options": cls.ALIGNMENT_FORMATS,
                        "description": "Logical AXT or PSL input format; required independently of the physical staged suffix",
                    },
                ),
            },
            "optional": {
                "linear_gap": (
                    "STRING",
                    {
                        "default": "loose",
                        "options": cls.LINEAR_GAP_OPTIONS,
                        "description": "Use UCSC loose/medium linear gap costs or a custom cost file",
                    },
                ),
                "lineargap_input": (
                    "FILE",
                    {"description": "Custom tabular linear gap cost file used when linear_gap is linear_gap_file"},
                ),
                "minScore": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum chain score to report"},
                ),
                "scoreScheme": (
                    "FILE",
                    {"description": "Optional BLASTZ-format scoring matrix"},
                ),
                "details_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Write per-chain gap and scoring details"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
class UcscChainNetNode(CommandNode):
    """Create UCSC alignment net files from chains."""

    LEGACY_NODE_ID = "ucsc_chainnet"
    DISPLAY_NAME = "chainNet"
    REQUIRED_CONDA_PACKAGES = ["ucsc-chainnet"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create target and query UCSC net alignment files from chain alignments."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_chainnet",
        "chainNet",
        "UCSC chain",
        "UCSC net",
        "alignment nets",
        "target net",
        "query net",
    ]
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("targetNet", "queryNet")
    REQUIRED_EXECUTABLES = ["chainNet"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/net.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    REFERENCE_SOURCE_OPTIONS = ["cached", "history"]
    NONNEGATIVE_OPTIONS = ("minSpace", "minFill", "verbose")

    @classmethod
    def _target_net_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/target.net"

    @classmethod
    def _query_net_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/query.net"

    @classmethod
    def _source(cls, inputs: dict[str, Any], prefix: str) -> str:
        return str(inputs.get(f"{prefix}_reference_index_source_selector", "history") or "history")

    @classmethod
    def _index_path(cls, inputs: dict[str, Any], prefix: str) -> str:
        source = cls._source(inputs, prefix)
        if prefix == "target":
            return str(inputs.get("tar_ref_index_path" if source == "cached" else "in_tar_ref_index", ""))
        return str(inputs.get("que_ref_index_path" if source == "cached" else "in_que_ref_index", ""))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "chainNet",
            str(inputs.get("in_chain", "")),
            cls._index_path(inputs, "target"),
            cls._index_path(inputs, "query"),
            cls._target_net_path(inputs),
            cls._query_net_path(inputs),
        ]
        for name in ("minSpace", "minFill", "minScore"):
            if str(inputs.get(name, "")) != "":
                cmd.append(f"-{name}={inputs.get(name)}")
        if inputs.get("inclHap"):
            cmd.append("-inclHap")
        if str(inputs.get("verbose", "")) != "":
            cmd.append(f"-verbose={inputs.get('verbose')}")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "target.net", out / "query.net"]

    @classmethod
    def _validate_index(cls, inputs: dict[str, Any], prefix: str) -> bool | str:
        selector_name = f"{prefix}_reference_index_source_selector"
        source = cls._source(inputs, prefix)
        if source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"{selector_name} must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if prefix == "target":
            required_name = "tar_ref_index_path" if source == "cached" else "in_tar_ref_index"
        else:
            required_name = "que_ref_index_path" if source == "cached" else "in_que_ref_index"
        if not cls._index_path(inputs, prefix).strip():
            return f"{required_name} is required"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_chain", "")).strip():
            return "in_chain is required"
        for prefix in ("target", "query"):
            index_validation = cls._validate_index(inputs, prefix)
            if index_validation is not True:
                return index_validation
        for name in cls.NONNEGATIVE_OPTIONS:
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < 0:
                return f"{name} must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_chain": ("FILE", {"description": "UCSC chain alignment file to net"}),
            },
            "optional": {
                "target_reference_index_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a cached or history target genome index",
                    },
                ),
                "in_tar_ref_index": (
                    "FILE",
                    {"description": "History target chrom sizes or FASTA index file"},
                ),
                "tar_ref_index_path": (
                    "STRING",
                    {"default": "", "description": "Path to cached target chrom sizes or FASTA index file"},
                ),
                "query_reference_index_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a cached or history query genome index",
                    },
                ),
                "in_que_ref_index": (
                    "FILE",
                    {"description": "History query chrom sizes or FASTA index file"},
                ),
                "que_ref_index_path": (
                    "STRING",
                    {"default": "", "description": "Path to cached query chrom sizes or FASTA index file"},
                ),
                "minSpace": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum gap size to fill"},
                ),
                "minFill": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum fill size to record"},
                ),
                "minScore": (
                    "INT",
                    {"default": "", "description": "Minimum chain score to consider"},
                ),
                "inclHap": (
                    "BOOLEAN",
                    {"default": False, "description": "Include query sequences named *_hap* or *_alt*"},
                ),
                "verbose": (
                    "INT",
                    {"default": "", "min": 0, "description": "Verbosity level"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


_KENT_482_NODES = [UcscAxtChainNode, UcscChainNetNode]
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
