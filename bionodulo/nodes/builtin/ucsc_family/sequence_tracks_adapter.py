"""UCSC sequence and track conversion nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    KENT_482_GIT_COMMIT,
    KENT_GIT_URL,
    pin_contract,
)

class UcscTwoBitToFaNode(CommandNode):
    """Convert UCSC TwoBit sequence files to FASTA."""

    LEGACY_NODE_ID = "ucsc-twobittofa"
    DISPLAY_NAME = "twoBitToFa"
    REQUIRED_CONDA_PACKAGES = ["ucsc-twobittofa"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert all or part of a TwoBit sequence file to FASTA."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc-twobittofa",
        "twoBitToFa",
        "TwoBit",
        "2bit to FASTA",
        "sequence range",
        "seqList",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("fasta_output",)
    REQUIRED_EXECUTABLES = ["twoBitToFa"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenpath/help/twoBit.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/fasta_output.fa"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "twoBitToFa",
            str(inputs.get("twobit_input", "")),
            cls._output_path(inputs),
        ]
        if str(inputs.get("seq", "")) != "":
            cmd.append(f"-seq={inputs.get('seq')}")
        if str(inputs.get("start", "")) != "":
            cmd.append(f"-start={inputs.get('start')}")
        if str(inputs.get("end", "")) != "":
            cmd.append(f"-end={inputs.get('end')}")
        if str(inputs.get("seqList", "")) != "":
            cmd.append(f"-seqList={inputs.get('seqList')}")
        if inputs.get("noMask"):
            cmd.append("-noMask")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "fasta_output.fa"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("twobit_input", "")).strip():
            return "twobit_input is required"
        for name in ("start", "end"):
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < 0:
                return f"{name} must be greater than or equal to 0"
        if str(inputs.get("start", "")) != "" and str(inputs.get("end", "")) != "":
            if int(inputs.get("end")) < int(inputs.get("start")):
                return "end must be greater than or equal to start"
        if str(inputs.get("seq", "")) != "" and str(inputs.get("seqList", "")) != "":
            return "seq and seqList cannot both be set"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "twobit_input": ("FILE", {"description": "Input UCSC TwoBit sequence file"}),
            },
            "optional": {
                "seq": (
                    "STRING",
                    {"default": "", "description": "Restrict conversion to one sequence name"},
                ),
                "start": (
                    "INT",
                    {"default": "", "min": 0, "description": "Zero-based start position within the selected sequence"},
                ),
                "end": (
                    "INT",
                    {"default": "", "min": 0, "description": "Non-inclusive end position within the selected sequence"},
                ),
                "seqList": (
                    "FILE",
                    {"description": "Text file with sequence names or seqSpec:start-end ranges to extract"},
                ),
                "noMask": (
                    "BOOLEAN",
                    {"default": False, "description": "Convert masked sequence to uppercase"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscWigToBigWigNode(CommandNode):
    """Convert Wiggle or bedGraph data to bigWig."""

    LEGACY_NODE_ID = "ucsc_wigtobigwig"
    DISPLAY_NAME = "wigtobigwig"
    REQUIRED_CONDA_PACKAGES = ["ucsc-wigtobigwig", "grep"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert bedGraph or Wiggle data to an indexed bigWig track."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_wigtobigwig",
        "wigtobigwig",
        "wigToBigWig",
        "bigWig",
        "bedGraph",
        "Wiggle",
        "genome browser track",
    ]
    RETURN_TYPES = ("BIGWIG",)
    RETURN_NAMES = ("out_file1",)
    REQUIRED_EXECUTABLES = ["grep", "wigToBigWig"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/bigWig.html"
    CITATION_DOIS = [BBG_TO_BIGWIG_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BBG_TO_BIGWIG_CITATION_DOI}"]
    CITATION_TEXT = BBG_TO_BIGWIG_CITATION_TEXT
    VERSION = "482+galaxy0"

    GENOME_SOURCE_OPTIONS = ["indexed", "history"]
    SETTINGS_OPTIONS = ["preset", "full"]
    WRAPPER_ERROR_PATTERN = "needLargeMem: trying to allocate 0 bytes|^Error"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_file1.bw"

    @classmethod
    def _trackless_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/trackless"

    @classmethod
    def _genome_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("genome_type_select", "indexed") or "indexed")

    @classmethod
    def _settings_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("settingsType", "preset") or "preset")

    @classmethod
    def _chrom_sizes(cls, inputs: dict[str, Any]) -> str:
        if cls._genome_source(inputs) == "history":
            return str(inputs.get("chromfile", ""))
        return str(inputs.get("index_len_path", ""))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out_dir = _out(inputs)
        trackless = cls._trackless_path(inputs)
        setup = _shell_join(["mkdir", "-p", out_dir])
        strip = f"grep -v '^track' {shlex.quote(str(inputs.get('input1', '')))} > {shlex.quote(trackless)}"
        cmd = [
            "wigToBigWig",
            trackless,
            cls._chrom_sizes(inputs),
            cls._output_path(inputs),
        ]
        if cls._settings_type(inputs) == "full":
            cmd.append(f"-blockSize={inputs.get('blockSize', 256)}")
            cmd.append(f"-itemsPerSlot={inputs.get('itemsPerSlot', 1024)}")
            if inputs.get("clip", True):
                cmd.append("-clip")
            if inputs.get("unc"):
                cmd.append("-unc")
        else:
            cmd.append("-clip")
        log_path = f"{out_dir}/wigToBigWig.log"
        run = f"{_shell_join(cmd)} > {shlex.quote(log_path)} 2>&1"
        scan = (
            f"if grep -Eq {shlex.quote(cls.WRAPPER_ERROR_PATTERN)} {shlex.quote(log_path)}; "
            f"then cat {shlex.quote(log_path)} >&2; exit 1; fi"
        )
        cleanup = _shell_join(["rm", "-f", log_path])
        return f"{setup} && {strip} && {run} && {scan} && {cleanup}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out_file1.bw"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input1", "")).strip():
            return "input1 is required"
        genome_source = cls._genome_source(inputs)
        if genome_source not in cls.GENOME_SOURCE_OPTIONS:
            return f"genome_type_select must be one of: {', '.join(cls.GENOME_SOURCE_OPTIONS)}"
        if not cls._chrom_sizes(inputs).strip():
            return "chromfile is required" if genome_source == "history" else "index_len_path is required"
        settings_type = cls._settings_type(inputs)
        if settings_type not in cls.SETTINGS_OPTIONS:
            return f"settingsType must be one of: {', '.join(cls.SETTINGS_OPTIONS)}"
        if settings_type == "full":
            for name, default in (("blockSize", 256), ("itemsPerSlot", 1024)):
                value = inputs.get(name, default)
                if int(value) < 1:
                    return f"{name} must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input1": ("FILE", {"description": "Wiggle or bedGraph file to convert"}),
            },
            "optional": {
                "genome_type_select": (
                    "STRING",
                    {
                        "default": "indexed",
                        "options": cls.GENOME_SOURCE_OPTIONS,
                        "description": "Use built-in genome lengths or a chromosome length file from history",
                    },
                ),
                "index_len_path": (
                    "STRING",
                    {"default": "", "description": "Path to cached chromosome length file for the selected genome build"},
                ),
                "chromfile": (
                    "FILE",
                    {"description": "Chromosome length file for a history reference genome"},
                ),
                "settingsType": (
                    "STRING",
                    {
                        "default": "preset",
                        "options": cls.SETTINGS_OPTIONS,
                        "description": "Use default converter settings or expose the full parameter list",
                    },
                ),
                "blockSize": (
                    "INT",
                    {"default": 256, "min": 1, "description": "Items to bundle in the R-tree"},
                ),
                "itemsPerSlot": (
                    "INT",
                    {"default": 1024, "min": 1, "description": "Data points bundled at the lowest level"},
                ),
                "clip": (
                    "BOOLEAN",
                    {"default": True, "description": "Warn and clip items beyond chromosome ends instead of failing"},
                ),
                "unc": (
                    "BOOLEAN",
                    {"default": False, "description": "Write an uncompressed bigWig file"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
class UcscAxtToMafNode(CommandNode):
    """Convert UCSC AXT alignments to MAF."""

    LEGACY_NODE_ID = "ucsc_axtomaf"
    DISPLAY_NAME = "axtToMaf"
    REQUIRED_CONDA_PACKAGES = ["ucsc-axttomaf"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert UCSC AXT pairwise alignments to MAF format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_axtomaf",
        "axtToMaf",
        "AXT to MAF",
        "multiple alignment format",
        "pairwise alignment",
        "chrom sizes",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["axtToMaf"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/FAQ/FAQformat.html#format5"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy1"

    REFERENCE_SOURCE_OPTIONS = ["cached", "history"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.maf"

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
            "axtToMaf",
            str(inputs.get("in_axt", "")),
            cls._index_path(inputs, "target"),
            cls._index_path(inputs, "query"),
        ]
        if str(inputs.get("t_prefix", "")) != "":
            cmd.append(f"-tPrefix={inputs.get('t_prefix')}")
        if str(inputs.get("q_prefix", "")) != "":
            cmd.append(f"-qPrefix={inputs.get('q_prefix')}")
        if inputs.get("score"):
            cmd.append("-score")
        if inputs.get("scoreZero"):
            cmd.append("-scoreZero")
        cmd.append(cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.maf"]

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
        if not str(inputs.get("in_axt", "")).strip():
            return "in_axt is required"
        for prefix in ("target", "query"):
            index_validation = cls._validate_index(inputs, prefix)
            if index_validation is not True:
                return index_validation
        for name in ("t_prefix", "q_prefix"):
            if " " in str(inputs.get(name, "")):
                return f"{name} cannot contain spaces"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_axt": ("FILE", {"description": "UCSC AXT pairwise alignment file"}),
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
                "t_prefix": (
                    "STRING",
                    {"default": "", "description": "Prefix added to target sequence names in the MAF output"},
                ),
                "q_prefix": (
                    "STRING",
                    {"default": "", "description": "Prefix added to query sequence names in the MAF output"},
                ),
                "score": (
                    "BOOLEAN",
                    {"default": False, "description": "Recalculate alignment scores"},
                ),
                "scoreZero": (
                    "BOOLEAN",
                    {"default": False, "description": "Recalculate scores only when the AXT score is zero"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


_KENT_482_NODES = [UcscTwoBitToFaNode, UcscWigToBigWigNode, UcscAxtToMafNode]
pin_contract(
    _KENT_482_NODES,
    runtime_version="482",
    runtime_git_url=KENT_GIT_URL,
    runtime_git_commit=KENT_482_GIT_COMMIT,
)
for _node_class in _KENT_482_NODES:
    _node_class.PACKAGE_CONSTRAINT = "; ".join(
        f"{package}==482" if package.startswith("ucsc-") else package
        for package in _node_class.REQUIRED_CONDA_PACKAGES
    )
