"""UCSC chain and net utility nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    KENT_482_GIT_COMMIT,
    KENT_GIT_URL,
    pin_contract,
)

class _UcscSingleFileUtilityNode(CommandNode):
    """Shared behavior for single-input UCSC Genome Browser utilities."""

    CATEGORY = "genomics"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    DOCUMENTATION_URL = ""
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    TOOL_NAME = ""
    INPUT_NAME = ""
    OUTPUT_FILENAME = ""
    INPUT_DESCRIPTION = ""

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls.OUTPUT_FILENAME}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join([cls.TOOL_NAME, str(inputs.get(cls.INPUT_NAME, "")), cls._output_path(inputs)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get(cls.INPUT_NAME, "")).strip():
            return f"{cls.INPUT_NAME} is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                cls.INPUT_NAME: ("FILE", {"description": cls.INPUT_DESCRIPTION}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscChainSwapNode(_UcscSingleFileUtilityNode):
    """Swap target and query sequences in a UCSC chain file."""

    NODE_ID = "ucsc_chainswap"
    DISPLAY_NAME = "chainSwap"
    REQUIRED_CONDA_PACKAGES = ["ucsc-chainswap"]
    DESCRIPTION = "Swap target and query sequences in a UCSC chain alignment file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_chainswap",
        "chainSwap",
        "chain file",
        "UCSC chain",
        "swap target query",
    ]
    REQUIRED_EXECUTABLES = ["chainSwap"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/chain.html"
    TOOL_NAME = "chainSwap"
    INPUT_NAME = "in_chain"
    OUTPUT_FILENAME = "out.chain"
    INPUT_DESCRIPTION = "UCSC chain alignment file whose target and query coordinates should be swapped"

class UcscChainSortNode(_UcscSingleFileUtilityNode):
    """Sort records in a UCSC chain file."""

    NODE_ID = "ucsc_chainsort"
    DISPLAY_NAME = "chainSort"
    REQUIRED_CONDA_PACKAGES = ["ucsc-chainsort"]
    DESCRIPTION = "Sort UCSC chain alignment records by score, target start, or query start."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_chainsort",
        "chainSort",
        "chain file",
        "UCSC chain",
        "sort chains",
        "target start",
        "query start",
    ]
    REQUIRED_EXECUTABLES = ["chainSort"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/chain.html"
    TOOL_NAME = "chainSort"
    INPUT_NAME = "in_chain"
    OUTPUT_FILENAME = "out.chain"
    INPUT_DESCRIPTION = "UCSC chain alignment file to sort"
    SORT_MODES = ["", "-target", "-query"]

    @classmethod
    def _sort_by(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("sort_by", "") or "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [cls.TOOL_NAME, str(inputs.get(cls.INPUT_NAME, ""))]
        if sort_by := cls._sort_by(inputs):
            cmd.append(sort_by)
        cmd.append(cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        required = super().VALIDATE_INPUTS(inputs)
        if required is not True:
            return required
        sort_by = cls._sort_by(inputs)
        if sort_by not in cls.SORT_MODES:
            return f"sort_by must be one of: {', '.join(cls.SORT_MODES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                cls.INPUT_NAME: ("FILE", {"description": cls.INPUT_DESCRIPTION}),
            },
            "optional": {
                "sort_by": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.SORT_MODES,
                        "description": "Sort chains by score, target start, or query start",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscNetSyntenicNode(_UcscSingleFileUtilityNode):
    """Add synteny annotations to a UCSC net file."""

    NODE_ID = "ucsc_netsyntenic"
    DISPLAY_NAME = "netSyntenic"
    REQUIRED_CONDA_PACKAGES = ["ucsc-netsyntenic"]
    DESCRIPTION = "Add synteny information to a UCSC net alignment file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_netsyntenic",
        "netSyntenic",
        "net file",
        "UCSC net",
        "synteny info",
    ]
    REQUIRED_EXECUTABLES = ["netSyntenic"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/net.html"
    TOOL_NAME = "netSyntenic"
    INPUT_NAME = "in_net"
    OUTPUT_FILENAME = "out.ucsc.net"
    INPUT_DESCRIPTION = "UCSC net alignment file to annotate with synteny information"

class UcscNetChainSubsetNode(CommandNode):
    """Extract the subset of chains referenced by a UCSC net file."""

    NODE_ID = "ucsc_netchainsubset"
    DISPLAY_NAME = "netChainSubset"
    REQUIRED_CONDA_PACKAGES = ["ucsc-netchainsubset"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create a UCSC chain file containing only chains that appear in a net file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_netchainsubset",
        "netChainSubset",
        "UCSC net",
        "UCSC chain",
        "liftOver",
        "chain subset",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["netChainSubset"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/net.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    FLAG_INPUTS = (
        ("splitOnInsert", "-splitOnInsert"),
        ("wholeChains", "-wholeChains"),
        ("skipMissing", "-skipMissing"),
    )

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.chain"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "netChainSubset",
            str(inputs.get("in_net", "")),
            str(inputs.get("in_chain", "")),
            cls._output_path(inputs),
        ]
        for name, flag in cls.FLAG_INPUTS:
            if inputs.get(name):
                cmd.append(flag)
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.chain"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_net", "")).strip():
            return "in_net is required"
        if not str(inputs.get("in_chain", "")).strip():
            return "in_chain is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_net": ("FILE", {"description": "UCSC net file identifying chains to keep"}),
                "in_chain": ("FILE", {"description": "UCSC chain file to subset"}),
            },
            "optional": {
                "splitOnInsert": (
                    "BOOLEAN",
                    {"default": False, "description": "Split chains when an insertion of another chain is encountered"},
                ),
                "wholeChains": (
                    "BOOLEAN",
                    {"default": False, "description": "Write entire referenced chains instead of splitting high-level nets"},
                ),
                "skipMissing": (
                    "BOOLEAN",
                    {"default": False, "description": "Skip chains that are not found instead of failing"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscNetFilterNode(CommandNode):
    """Filter a UCSC net file."""

    NODE_ID = "ucsc_netfilter"
    DISPLAY_NAME = "netFilter"
    REQUIRED_CONDA_PACKAGES = ["ucsc-netfilter"]
    CATEGORY = "genomics"
    DESCRIPTION = "Filter out parts of a UCSC net alignment file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_netfilter",
        "netFilter",
        "UCSC net",
        "net file",
        "synteny filter",
        "minimum gap",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["netFilter"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/net.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    SYN_FILTERS = ["skipsyn", "filtersyn"]
    SYN_TYPES = ["-syn", "-chimpSyn", "-nonsyn"]
    NONNEGATIVE_THRESHOLDS = ("minSynSize", "minSynAli", "minGap")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.ucsc.net"

    @classmethod
    def _syn_filter(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("syn_filter", "skipsyn") or "skipsyn")

    @classmethod
    def _syn_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("syntype", "-syn") or "-syn")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["netFilter", str(inputs.get("in_net", ""))]
        if cls._syn_filter(inputs) == "filtersyn":
            cmd.append(cls._syn_type(inputs))
            for name in ("minSynScore", "minSynSize", "minSynAli"):
                if str(inputs.get(name, "")) != "":
                    cmd.append(f"-{name}={inputs.get(name)}")
        if str(inputs.get("minGap", "")) != "":
            cmd.append(f"-minGap={inputs.get('minGap')}")
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.ucsc.net"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_net", "")).strip():
            return "in_net is required"
        syn_filter = cls._syn_filter(inputs)
        if syn_filter not in cls.SYN_FILTERS:
            return f"syn_filter must be one of: {', '.join(cls.SYN_FILTERS)}"
        syntype = cls._syn_type(inputs)
        if syntype not in cls.SYN_TYPES:
            return f"syntype must be one of: {', '.join(cls.SYN_TYPES)}"
        for name in cls.NONNEGATIVE_THRESHOLDS:
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < 0:
                return f"{name} must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_net": ("FILE", {"description": "UCSC net alignment file to filter"}),
            },
            "optional": {
                "syn_filter": (
                    "STRING",
                    {
                        "default": "skipsyn",
                        "options": cls.SYN_FILTERS,
                        "description": "Enable synteny-based filtering",
                    },
                ),
                "syntype": (
                    "STRING",
                    {
                        "default": "-syn",
                        "options": cls.SYN_TYPES,
                        "description": "Synteny filter mode used when synteny filtering is enabled",
                    },
                ),
                "minSynScore": (
                    "INT",
                    {"default": "", "description": "Minimum syntenic block score"},
                ),
                "minSynSize": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum syntenic block size"},
                ),
                "minSynAli": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum syntenic alignment size"},
                ),
                "minGap": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum gap size to keep"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscChainPreNetNode(CommandNode):
    """Remove chains unlikely to be netted."""

    NODE_ID = "ucsc_chainprenet"
    DISPLAY_NAME = "chainPreNet"
    REQUIRED_CONDA_PACKAGES = ["ucsc-chainprenet"]
    CATEGORY = "genomics"
    DESCRIPTION = "Remove UCSC chains that do not have a chance of being netted."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_chainprenet",
        "chainPreNet",
        "UCSC chain",
        "UCSC net",
        "netted chains",
        "chrom sizes",
        "haplotype pseudochromosomes",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["chainPreNet"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/chain.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    REFERENCE_SOURCE_OPTIONS = ["cached", "history"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.chain"

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
            "chainPreNet",
            str(inputs.get("in_chain", "")),
            cls._index_path(inputs, "target"),
            cls._index_path(inputs, "query"),
            cls._output_path(inputs),
        ]
        if str(inputs.get("pad", "")) != "":
            cmd.append(f"-pad={inputs.get('pad')}")
        if inputs.get("inclHap"):
            cmd.append("-inclHap")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.chain"]

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
        if str(inputs.get("pad", "")) != "" and int(inputs.get("pad")) < 0:
            return "pad must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_chain": ("FILE", {"description": "UCSC chain alignment file to pre-filter before netting"}),
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
                "pad": (
                    "INT",
                    {"default": "", "min": 0, "description": "Extra bases to pad around blocks to decrease trash"},
                ),
                "inclHap": (
                    "BOOLEAN",
                    {"default": False, "description": "Include query sequences named *_hap* or *_alt*"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscNetToAxtNode(CommandNode):
    """Convert UCSC net and chain alignments to AXT."""

    NODE_ID = "ucsc_nettoaxt"
    DISPLAY_NAME = "netToAxt"
    REQUIRED_CONDA_PACKAGES = ["ucsc-nettoaxt"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert UCSC net and chain alignments to AXT format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_nettoaxt",
        "netToAxt",
        "UCSC net",
        "UCSC chain",
        "net to AXT",
        "pairwise alignment",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["netToAxt"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/axt.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.axt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "netToAxt",
            str(inputs.get("in_net", "")),
            str(inputs.get("in_chain", "")),
            str(inputs.get("in_target", "")),
            str(inputs.get("in_query", "")),
            cls._output_path(inputs),
        ]
        if inputs.get("qChain"):
            cmd.append("-qChain")
        if str(inputs.get("maxGap", "")) != "":
            cmd.append(f"-maxGap={inputs.get('maxGap')}")
        if inputs.get("noSplit"):
            cmd.append("-noSplit")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.axt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("in_net", "in_chain", "in_target", "in_query"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        if str(inputs.get("maxGap", "")) != "" and int(inputs.get("maxGap")) < 0:
            return "maxGap must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_net": ("FILE", {"description": "UCSC net alignment file"}),
                "in_chain": ("FILE", {"description": "UCSC chain alignment file"}),
                "in_target": ("FILE", {"description": "TwoBit file containing the target sequence"}),
                "in_query": ("FILE", {"description": "TwoBit file containing the query sequence"}),
            },
            "optional": {
                "qChain": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat the net as being with respect to the query side of chains"},
                ),
                "maxGap": (
                    "INT",
                    {"default": "", "min": 0, "description": "Maximum gap size before breaking alignment blocks"},
                ),
                "noSplit": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not split chains at insertions of another chain"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


_KENT_482_NODES = [
    UcscChainSwapNode,
    UcscChainSortNode,
    UcscNetSyntenicNode,
    UcscNetChainSubsetNode,
    UcscNetFilterNode,
    UcscChainPreNetNode,
    UcscNetToAxtNode,
]
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
