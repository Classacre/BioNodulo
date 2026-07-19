"""Focused owner for ``hyphy_bgm``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from ..contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhyBGMNode(ToolsIUCCommandContract):
    """Detect coevolving sites with HyPhy Bayesian graphical models."""

    NODE_ID = "hyphy_bgm"
    DISPLAY_NAME = "HyPhy-BGM"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Detect coevolving sites in sequence alignments with HyPhy Bayesian graphical models."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "BGM",
        "Bayesian graphical model",
        "Spidermonkey",
        "coevolving sites",
        "correlated substitutions",
        "phylogenetics",
    ]
    RETURN_TYPES = ("JSON", "TEXT")
    RETURN_NAMES = ("bgm_output", "bgm_md_report")
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "http://hyphy.org/methods/selection-methods/#BGM"
    CITATION_DOIS = HYPHY_BGM_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_BGM_CITATION_DOIS]
    CITATION_TEXT = HYPHY_BGM_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    DATATYPES = ["nucleotide", "amino-acid", "codon"]
    AMINO_ACID_MODELS = ["LG", "WAG", "JTT", "JC69", "mtMet", "mtVer", "mtInv", "gcpREV", "HIVBm", "HIVWm", "GTR"]

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("input_ext", "fasta")).strip().lstrip(".") or "fasta"
        return f"input.{ext}"

    @classmethod
    def _branch_arg(cls, inputs: dict[str, Any]) -> str:
        branch_sel = str(inputs.get("branch_sel", "All") or "All")
        if branch_sel == "specify":
            return str(inputs.get("branch_label", "")).strip()
        return branch_sel

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get("input_nhx", "")).strip():
            commands.append(_shell_join(["ln", "-s", str(inputs.get("input_nhx", "")), "input.nhx"]))
        commands.append(_shell_join(["ln", "-s", str(inputs.get("input_file", "")), input_name]))

        datatype = str(inputs.get("datatype", "codon") or "codon")
        cmd = [
            "TOLERATE_NUMERICAL_ERRORS=1",
            "hyphy",
            f"CPU={inputs.get('threads', 4)}",
            "bgm",
            "--alignment",
            f"./{input_name}",
        ]
        if str(inputs.get("input_nhx", "")).strip():
            cmd.extend(["--tree", "input.nhx"])
        cmd.extend(["--type", datatype])
        if datatype == "codon":
            cmd.extend(["--code", str(inputs.get("gencodeid", "Universal") or "Universal")])
        if datatype == "amino-acid":
            cmd.extend(["--baseline_model", str(inputs.get("baseline_model", "LG") or "LG")])
        cmd.extend(
            [
                "--branches",
                cls._branch_arg(inputs),
                "--steps",
                str(inputs.get("chain_length", 100000)),
                "--burn-in",
                str(inputs.get("burn_in", 10000)),
                "--samples",
                str(inputs.get("samples", 100)),
                "--max-parents",
                str(inputs.get("parents", 1)),
                "--min-subs",
                str(inputs.get("min_subs", 1)),
                "--output",
                f"{out}/bgm_output.json",
                ">",
                f"{out}/bgm_stdout.md",
            ]
        )
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "bgm_output.json", out / "bgm_stdout.md"]

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, default: int, low: int, high: int, label: str) -> str | None:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"HyPhy-BGM {label} must be between {low} and {high}"
        if value < low or value > high:
            return f"HyPhy-BGM {label} must be between {low} and {high}"
        return None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-BGM alignment input is required"
        datatype = str(inputs.get("datatype", "codon") or "codon")
        if datatype not in cls.DATATYPES:
            return f"Unsupported HyPhy-BGM data type: {datatype}"
        if datatype == "codon":
            gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
            if gencodeid not in cls.GENETIC_CODES:
                return f"Unsupported HyPhy genetic code: {gencodeid}"
        if datatype == "amino-acid":
            baseline_model = str(inputs.get("baseline_model", "LG") or "LG")
            if baseline_model not in cls.AMINO_ACID_MODELS:
                return f"Unsupported HyPhy-BGM amino-acid substitution model: {baseline_model}"
        branch_sel = str(inputs.get("branch_sel", "All") or "All")
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f"Unsupported HyPhy-BGM branch selection: {branch_sel}"
        if branch_sel == "specify" and not str(inputs.get("branch_label", "")).strip():
            return "HyPhy-BGM custom branch selection requires a branch label"
        for key, default, low, high, label in [
            ("chain_length", 100000, 0, 1000000000, "chain length"),
            ("burn_in", 10000, 0, 1000000000, "burn-in"),
            ("samples", 100, 1, 100000, "samples"),
            ("parents", 1, 1, 3, "maximum parents"),
            ("min_subs", 1, 1, 1000, "minimum substitutions"),
        ]:
            message = cls._validate_int_range(inputs, key, default, low, high, label)
            if message:
                return message
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "HyPhy-BGM threads must be a positive integer"
        if threads < 1:
            return "HyPhy-BGM threads must be a positive integer"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "FASTA",
                    {"description": "Sequence alignment in FASTA, compressed FASTA, or NEXUS format"},
                ),
            },
            "optional": {
                "input_nhx": ("FILE", {"default": "", "description": "Optional Newick/NHX phylogenetic tree"}),
                "input_ext": (
                    "STRING",
                    {"default": "fasta", "options": cls.INPUT_EXTENSIONS, "advanced": True},
                ),
                "datatype": (
                    "STRING",
                    {"default": "codon", "options": cls.DATATYPES, "description": "Alignment data type"},
                ),
                "gencodeid": (
                    "STRING",
                    {
                        "default": "Universal",
                        "options": cls.GENETIC_CODES,
                        "description": "HyPhy genetic code used for codon alignments",
                    },
                ),
                "baseline_model": (
                    "STRING",
                    {
                        "default": "LG",
                        "options": cls.AMINO_ACID_MODELS,
                        "description": "Amino-acid substitution model",
                    },
                ),
                "branch_sel": (
                    "STRING",
                    {
                        "default": "All",
                        "options": cls.BRANCH_SELECTIONS,
                        "description": "Branches to include in the coevolution analysis",
                    },
                ),
                "branch_label": (
                    "STRING",
                    {"default": "", "description": "Custom branch label when branch selection is specify"},
                ),
                "chain_length": (
                    "INT",
                    {"default": 100000, "min": 0, "max": 1000000000, "description": "Length of MCMC chain"},
                ),
                "burn_in": (
                    "INT",
                    {"default": 10000, "min": 0, "max": 1000000000, "description": "MCMC burn-in steps"},
                ),
                "samples": (
                    "INT",
                    {"default": 100, "min": 1, "max": 100000, "description": "Samples to extract from the chain"},
                ),
                "parents": (
                    "INT",
                    {"default": 1, "min": 1, "max": 3, "description": "Maximum parents allowed per graph node"},
                ),
                "min_subs": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 1000,
                        "description": "Minimum substitutions per site included in the analysis",
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }
