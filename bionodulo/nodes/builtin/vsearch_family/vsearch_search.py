"""Focused VSEARCH database-search node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_amplicon_trimming_family.evidence import pin_contract

from .adapter import VSEARCH_USERFIELDS, VSearchNodeBase


class VSearchSearchNode(VSearchNodeBase):
    """Search query sequences against a FASTA database with VSEARCH."""

    NODE_ID = "vsearch_search"
    DISPLAY_NAME = "VSEARCH Search"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Search amplicon or nucleotide sequences against a reference database with VSEARCH."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "vsearch", "usearch_global", "search", "amplicon", "otu"]
    RETURN_TYPES = (
        "TSV",
        "STATS_FILE",
        "FASTA",
        "FASTA",
        "FASTA",
        "FASTA",
        "FASTA",
        "TSV",
        "TSV",
        "TSV",
        "STATS_FILE",
        "FASTA",
    )
    RETURN_NAMES = (
        "blast6out",
        "alnout",
        "notmatched",
        "dbmatched",
        "dbnotmatched",
        "matched",
        "fastapairs",
        "uc",
        "userout",
        "matches",
        "alignments",
        "unmatched",
    )
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3.1"
    USERFIELD_OPTIONS = VSEARCH_USERFIELDS

    OUTPUT_FILES = {
        "alnout": "alignments.txt",
        "blast6out": "matches.tsv",
        "dbmatched": "database_matched.fasta",
        "dbnotmatched": "database_notmatched.fasta",
        "fastapairs": "query_target_pairs.fasta",
        "notmatched": "unmatched.fasta",
        "matched": "matched.fasta",
        "uc": "matches.uc",
        "userout": "userfields.tsv",
    }
    OUTPUT_FLAGS = {
        "alnout": "--alnout",
        "blast6out": "--blast6out",
        "dbmatched": "--dbmatched",
        "dbnotmatched": "--dbnotmatched",
        "fastapairs": "--fastapairs",
        "notmatched": "--notmatched",
        "matched": "--matched",
    }
    ADVANCED_VALUE_FLAGS = {
        "target_cov": "--target_cov",
        "query_cov": "--query_cov",
        "maxid": "--maxid",
        "maxqt": "--maxqt",
        "maxsizeratio": "--maxsizeratio",
        "maxsl": "--maxsl",
        "mid": "--mid",
        "minqt": "--minqt",
        "minsizeratio": "--minsizeratio",
        "minsl": "--minsl",
        "mintsize": "--mintsize",
        "mismatch": "--mismatch",
        "maxqsize": "--maxqsize",
        "mincols": "--mincols",
        "maxsubs": "--maxsubs",
        "maxrejects": "--maxrejects",
        "maxaccepts": "--maxaccepts",
        "maxdiffs": "--maxdiffs",
        "maxgaps": "--maxgaps",
        "maxhits": "--maxhits",
        "match": "--match",
        "idprefix": "--idprefix",
        "idsuffix": "--idsuffix",
        "wordlength": "--wordlength",
    }
    ADVANCED_DEFAULTS = {
        "maxrejects": 32,
        "maxaccepts": 1,
        "match": 2,
        "mismatch": -4,
        "wordlength": 8,
    }

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = [value.removeprefix("--") for value in _as_list(inputs.get("outputs"))]
        return selected or ["blast6out"]

    @classmethod
    def _advanced_enabled(cls, inputs: dict[str, Any]) -> bool:
        advanced = inputs.get("advanced")
        if advanced is True or str(advanced).lower() in {"advanced", "true", "yes", "1"}:
            return True
        selector = inputs.get("adv_opts_selector")
        if selector is not None:
            return str(selector) == "advanced"
        if "advanced" in inputs:
            return False
        keys = set(cls.ADVANCED_VALUE_FLAGS) | {
            "top_hits_only",
            "rightjust",
            "leftjust",
            "output_no_hits",
            "uc",
            "userfields_output_select",
        }
        return any(inputs.get(key) not in {None, "", False, "no"} for key in keys)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = cls._general_command(inputs)
        cmd.extend(["--db", str(inputs.get("database", inputs.get("dbfile", "")))])
        dbmask = str(inputs.get("dbmask", "none") or "none")
        if dbmask:
            cmd.extend(["--dbmask", dbmask])
        if inputs.get("hardmask"):
            cmd.append("--hardmask")
        _add_if_value(cmd, "--id", inputs.get("identity", inputs.get("id", 0.97)))
        cmd.extend(["--iddef", str(inputs.get("iddef", "2"))])
        cmd.extend(["--qmask", str(inputs.get("qmask", "dust") or "dust")])
        if inputs.get("self_param"):
            cmd.append("--self")
        if inputs.get("selfid_param"):
            cmd.append("--selfid")
        if inputs.get("sizeout"):
            cmd.append("--sizeout")
        cmd.extend(["--strand", str(inputs.get("strand", "plus") or "plus")])
        cmd.extend(["--usearch_global", str(inputs.get("query", inputs.get("queryfile", "")))])

        out = _out(inputs)
        for name in cls._selected_outputs(inputs):
            flag = cls.OUTPUT_FLAGS.get(name)
            if flag:
                cmd.extend([flag, f"{out}/{cls.OUTPUT_FILES[name]}"])

        if cls._advanced_enabled(inputs):
            for key in ("top_hits_only", "rightjust", "leftjust"):
                if inputs.get(key):
                    cmd.append(f"--{key}")
            for key, flag in cls.ADVANCED_VALUE_FLAGS.items():
                _add_if_value(cmd, flag, inputs.get(key, cls.ADVANCED_DEFAULTS.get(key)))
            if inputs.get("uc"):
                cmd.extend(["--uc", f"{out}/{cls.OUTPUT_FILES['uc']}"])
                if inputs.get("uc_allhits"):
                    cmd.append("--uc_allhits")
            if str(inputs.get("userfields_output_select", "no")) == "yes":
                fields = _as_list(inputs.get("userfields")) or ["evalue", "query", "target"]
                cmd.extend(["--userfields", "+".join(fields), "--userout", f"{out}/{cls.OUTPUT_FILES['userout']}"])
            if inputs.get("output_no_hits"):
                cmd.append("--output_no_hits")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        names = cls._selected_outputs(inputs)
        if cls._advanced_enabled(inputs) and inputs.get("uc"):
            names.append("uc")
        if cls._advanced_enabled(inputs) and str(inputs.get("userfields_output_select", "no")) == "yes":
            names.append("userout")
        return [out / cls.OUTPUT_FILES[name] for name in dict.fromkeys(names)]

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        reverse = {filename: name for name, filename in cls.OUTPUT_FILES.items()}
        mapped = {reverse[path.name]: path for path in planned_paths}
        aliases = {"blast6out": "matches", "alnout": "alignments", "notmatched": "unmatched"}
        for source, alias in aliases.items():
            if source in mapped:
                mapped[alias] = mapped[source]
        return mapped

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("query", inputs.get("queryfile", ""))).strip():
            return "query is required"
        if not str(inputs.get("database", inputs.get("dbfile", ""))).strip():
            return "database is required"
        if str(inputs.get("search_mode", "usearch_global")) != "usearch_global":
            return "search_mode must be usearch_global for the pinned Galaxy wrapper"
        selected = cls._selected_outputs(inputs)
        unsupported = [name for name in selected if name not in cls.OUTPUT_FLAGS]
        if unsupported:
            return f"outputs contains unsupported values: {', '.join(unsupported)}"
        for name in ("qmask", "dbmask"):
            value = str(inputs.get(name, "dust" if name == "qmask" else "none"))
            if value not in {"none", "dust", "soft"}:
                return f"{name} must be one of: none, dust, soft"
        if str(inputs.get("strand", "plus")) not in {"plus", "both"}:
            return "strand must be one of: plus, both"
        try:
            identity = float(inputs.get("identity", inputs.get("id", 0.97)))
        except (TypeError, ValueError):
            return "identity must be a number"
        if not 0 <= identity <= 1:
            return "identity must be between 0 and 1"
        for name in ("query_cov", "target_cov"):
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if not 0 <= value <= 1:
                return f"{name} must be between 0 and 1"
        for name in (
            "maxid",
            "maxqt",
            "maxsizeratio",
            "maxsl",
            "mid",
            "minqt",
            "minsizeratio",
            "minsl",
        ):
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
        integer_fields = (
            "mintsize",
            "maxqsize",
            "mincols",
            "maxsubs",
            "maxrejects",
            "maxaccepts",
            "maxdiffs",
            "maxgaps",
            "maxhits",
            "match",
            "mismatch",
            "idprefix",
            "idsuffix",
            "wordlength",
        )
        for name in integer_fields:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if name == "wordlength" and not 3 <= value <= 15:
                return "wordlength must be between 3 and 15"
            if name not in {"match", "mismatch"} and value < 0:
                return f"{name} must be >= 0"
        userfields_select = str(inputs.get("userfields_output_select", "no"))
        if userfields_select not in {"no", "yes"}:
            return "userfields_output_select must be one of: no, yes"
        fields = _as_list(inputs.get("userfields"))
        unsupported_fields = [field for field in fields if field not in cls.USERFIELD_OPTIONS]
        if unsupported_fields:
            return f"userfields contains unsupported values: {', '.join(unsupported_fields)}"
        return cls._validate_common(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FASTA", {"description": "Query sequences for --usearch_global"}),
                "database": ("FASTA", {"description": "Reference database FASTA"}),
            },
            "optional": {
                "search_mode": ("STRING", {"default": "usearch_global", "options": ["usearch_global"]}),
                "outputs": (
                    "STRING_LIST",
                    {
                        "default": ["blast6out"],
                        "multiple": True,
                        "options": list(cls.OUTPUT_FLAGS),
                        "description": "Galaxy output files to emit",
                    },
                ),
                "identity": ("FLOAT", {"default": 0.97, "min": 0, "max": 1}),
                "iddef": ("STRING", {"default": "2", "options": ["0", "1", "2", "3", "4"]}),
                "strand": ("STRING", {"default": "plus", "options": ["plus", "both"]}),
                "qmask": ("STRING", {"default": "dust", "options": ["none", "dust", "soft"]}),
                "dbmask": ("STRING", {"default": "none", "options": ["none", "dust", "soft"]}),
                "hardmask": ("BOOLEAN", {"default": False}),
                "self_param": ("BOOLEAN", {"default": False}),
                "selfid_param": ("BOOLEAN", {"default": False}),
                "sizeout": ("BOOLEAN", {"default": False}),
                "advanced": ("BOOLEAN", {"default": False, "advanced": True}),
                "adv_opts_selector": (
                    "STRING",
                    {
                        "default": "basic",
                        "options": ["basic", "advanced"],
                        "advanced": True,
                        "description": "Galaxy advanced-options selector compatibility alias",
                    },
                ),
                "top_hits_only": ("BOOLEAN", {"default": False, "advanced": True}),
                "rightjust": ("BOOLEAN", {"default": False, "advanced": True}),
                "leftjust": ("BOOLEAN", {"default": False, "advanced": True}),
                "query_cov": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "target_cov": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "maxid": ("FLOAT", {"default": "", "advanced": True}),
                "maxqt": ("FLOAT", {"default": "", "advanced": True}),
                "maxsizeratio": ("FLOAT", {"default": "", "advanced": True}),
                "maxsl": ("FLOAT", {"default": "", "advanced": True}),
                "mid": ("FLOAT", {"default": "", "advanced": True}),
                "minqt": ("FLOAT", {"default": "", "advanced": True}),
                "minsizeratio": ("FLOAT", {"default": "", "advanced": True}),
                "minsl": ("FLOAT", {"default": "", "advanced": True}),
                "mintsize": ("INT", {"default": "", "min": 0, "advanced": True}),
                "maxqsize": ("INT", {"default": "", "min": 0, "advanced": True}),
                "mincols": ("INT", {"default": "", "min": 0, "advanced": True}),
                "maxsubs": ("INT", {"default": "", "min": 0, "advanced": True}),
                "maxaccepts": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "maxrejects": ("INT", {"default": 32, "min": 0, "advanced": True}),
                "maxdiffs": ("INT", {"default": "", "min": 0, "advanced": True}),
                "maxgaps": ("INT", {"default": "", "min": 0, "advanced": True}),
                "maxhits": ("INT", {"default": "", "min": 0, "advanced": True}),
                "match": ("INT", {"default": 2, "advanced": True}),
                "mismatch": ("INT", {"default": -4, "advanced": True}),
                "idprefix": ("INT", {"default": "", "min": 0, "advanced": True}),
                "idsuffix": ("INT", {"default": "", "min": 0, "advanced": True}),
                "wordlength": ("INT", {"default": 8, "min": 3, "max": 15, "advanced": True}),
                "uc": ("BOOLEAN", {"default": False, "advanced": True}),
                "uc_allhits": ("BOOLEAN", {"default": False, "advanced": True}),
                "userfields_output_select": (
                    "STRING",
                    {"default": "no", "options": ["no", "yes"], "advanced": True},
                ),
                "userfields": (
                    "STRING_LIST",
                    {
                        "default": ["evalue", "query", "target"],
                        "multiple": True,
                        "options": list(cls.USERFIELD_OPTIONS),
                        "advanced": True,
                    },
                ),
                "output_no_hits": ("BOOLEAN", {"default": False, "advanced": True}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(VSearchSearchNode)
