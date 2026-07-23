"""Focused owner for ``hyphy_busted``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhyBUSTEDNode(ToolsIUCCommandContract):
    """Detect gene-wide episodic diversifying selection with HyPhy BUSTED."""

    NODE_ID = "hyphy_busted"
    DISPLAY_NAME = "HyPhy-BUSTED"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Detect gene-wide episodic diversifying selection with HyPhy BUSTED."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "BUSTED",
        "Branch-site Unrestricted Statistical Test",
        "Bayesian UnresTricted Test of Episodic Diversification",
        "episodic diversifying selection",
        "gene-wide selection",
        "positive selection",
        "synonymous rate variation",
        "multiple synonymous rate classes",
        "phylogenetics",
    ]
    RETURN_TYPES = ("JSON", "TEXT", "PHYLOGENY_TREE")
    RETURN_NAMES = ("busted_output", "busted_md_report", "alternative_model")
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "http://hyphy.org/methods/selection-methods/#busted"
    CITATION_DOIS = HYPHY_BUSTED_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_BUSTED_CITATION_DOIS]
    CITATION_TEXT = HYPHY_BUSTED_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    MULTIPLE_HITS = HyPhyABSRELNode.MULTIPLE_HITS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS
    MSS_TYPES = [
        "Full",
        "SynREV",
        "SynREV2",
        "SynREV2g",
        "SynREVCodon",
        "Random",
        "Empirical",
        "File",
        "Codon-file",
    ]
    MSS_FILE_TYPES = {"Empirical", "File", "Codon-file"}
    MSS_NEUTRAL_TYPES = {"File", "Codon-file"}

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

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() in {"true", "yes", "1", "on"}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get("input_nhx", "")).strip():
            commands.append(_shell_join(["ln", "-s", str(inputs.get("input_nhx", "")), "input.nhx"]))
        commands.append(_shell_join(["ln", "-s", str(inputs.get("input_file", "")), input_name]))

        cmd = [
            "TOLERATE_NUMERICAL_ERRORS=1",
            "hyphy",
            f"CPU={inputs.get('threads', 4)}",
            "busted",
            "--alignment",
            f"./{input_name}",
        ]
        if str(inputs.get("input_nhx", "")).strip():
            cmd.extend(["--tree", "input.nhx"])
        cmd.extend(
            [
                "--code",
                str(inputs.get("gencodeid", "Universal") or "Universal"),
                "--branches",
                cls._branch_arg(inputs),
                "--output",
                f"{out}/busted_output.json",
                "--syn-rates",
                str(inputs.get("syn_rates", 3)),
                "--rates",
                str(inputs.get("rates", 3)),
                "--grid-size",
                str(inputs.get("grid_size", 250)),
                "--starting-points",
                str(inputs.get("starting_points", 1)),
            ]
        )
        multiple_hits = str(inputs.get("multiple_hits", "None") or "None")
        if multiple_hits != "None":
            cmd.extend(["--multiple-hits", multiple_hits])
        if cls._bool_value(inputs.get("error_sink", True)):
            cmd.extend(["--error-sink", "Yes"])
        if cls._bool_value(inputs.get("save_alternative_model", False)):
            cmd.extend(["--save-fit", f"{out}/alternative_model.nhx"])
        if cls._bool_value(inputs.get("mss_enabled", False)):
            mss_type = str(inputs.get("mss_type", "Full") or "Full")
            cmd.extend(["--mss", "Yes", "--mss-type", mss_type])
            if mss_type == "Random":
                cmd.extend(["--mss-classes", str(inputs.get("mss_classes", 2))])
            if mss_type in cls.MSS_FILE_TYPES:
                cmd.extend(["--mss-file", str(inputs.get("mss_file", ""))])
            if mss_type in cls.MSS_NEUTRAL_TYPES:
                cmd.extend(["--mss-neutral", str(inputs.get("mss_neutral", "neutral") or "neutral")])
        cmd.extend(
            [
                "--kill-zero-lengths",
                str(inputs.get("kill_zero_lengths", "Yes") or "Yes"),
                ">",
                f"{out}/busted_stdout.md",
            ]
        )
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "busted_output.json", out / "busted_stdout.md"]
        if cls._bool_value(inputs.get("save_alternative_model", False)):
            outputs.append(out / "alternative_model.nhx")
        return outputs

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, default: int, low: int, high: int, label: str) -> str | None:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"HyPhy-BUSTED {label} must be between {low} and {high}"
        if value < low or value > high:
            return f"HyPhy-BUSTED {label} must be between {low} and {high}"
        return None

    @staticmethod
    def _validate_positive_int(value: Any, message: str) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < 1 else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-BUSTED alignment input is required"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        branch_sel = str(inputs.get("branch_sel", "All") or "All")
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f"Unsupported HyPhy-BUSTED branch selection: {branch_sel}"
        if branch_sel == "specify" and not str(inputs.get("branch_label", "")).strip():
            return "HyPhy-BUSTED custom branch selection requires a branch label"
        for key, default, low, high, label in [
            ("syn_rates", 3, 1, 10, "synonymous rate classes"),
            ("rates", 3, 2, 10, "non-synonymous rate classes"),
            ("grid_size", 250, 1, 5000, "grid size"),
            ("starting_points", 1, 1, 1000, "starting points"),
        ]:
            message = cls._validate_int_range(inputs, key, default, low, high, label)
            if message:
                return message
        multiple_hits = str(inputs.get("multiple_hits", "None") or "None")
        if multiple_hits not in cls.MULTIPLE_HITS:
            return f"Unsupported HyPhy-BUSTED multiple-hits mode: {multiple_hits}"
        kill_zero_lengths = str(inputs.get("kill_zero_lengths", "Yes") or "Yes")
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f"Unsupported HyPhy-BUSTED zero-length branch handling: {kill_zero_lengths}"
        if cls._bool_value(inputs.get("mss_enabled", False)):
            if multiple_hits != "None":
                return "HyPhy-BUSTED MSS cannot be combined with multiple-hit correction"
            mss_type = str(inputs.get("mss_type", "Full") or "Full")
            if mss_type not in cls.MSS_TYPES:
                return f"Unsupported HyPhy-BUSTED MSS type: {mss_type}"
            if mss_type == "Random":
                message = cls._validate_positive_int(
                    inputs.get("mss_classes", 2), "HyPhy-BUSTED MSS classes must be a positive integer"
                )
                if message:
                    return message
            if mss_type in cls.MSS_FILE_TYPES and not str(inputs.get("mss_file", "")).strip():
                return f"HyPhy-BUSTED MSS file is required for {mss_type}"
            if mss_type in cls.MSS_NEUTRAL_TYPES and not str(inputs.get("mss_neutral", "neutral") or "").strip():
                return "HyPhy-BUSTED MSS neutral class is required"
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "HyPhy-BUSTED threads must be a positive integer"
        if threads < 1:
            return "HyPhy-BUSTED threads must be a positive integer"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "FASTA",
                    {"description": "Codon alignment in FASTA, compressed FASTA, or NEXUS format"},
                ),
            },
            "optional": {
                "input_nhx": ("FILE", {"default": "", "description": "Optional Newick/NHX phylogenetic tree"}),
                "input_ext": (
                    "STRING",
                    {"default": "fasta", "options": cls.INPUT_EXTENSIONS, "advanced": True},
                ),
                "gencodeid": (
                    "STRING",
                    {
                        "default": "Universal",
                        "options": cls.GENETIC_CODES,
                        "description": "HyPhy genetic code for codon interpretation",
                    },
                ),
                "branch_sel": (
                    "STRING",
                    {
                        "default": "All",
                        "options": cls.BRANCH_SELECTIONS,
                        "description": "Branches to test for episodic diversifying selection",
                    },
                ),
                "branch_label": (
                    "STRING",
                    {"default": "", "description": "Custom branch label when branch selection is specify"},
                ),
                "syn_rates": (
                    "INT",
                    {"default": 3, "min": 1, "max": 10, "description": "Synonymous rate classes"},
                ),
                "rates": (
                    "INT",
                    {"default": 3, "min": 2, "max": 10, "description": "Non-synonymous omega rate classes"},
                ),
                "grid_size": (
                    "INT",
                    {
                        "default": 250,
                        "min": 1,
                        "max": 5000,
                        "description": "Points in the initial distributional guess",
                    },
                ),
                "starting_points": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 1000,
                        "description": "Initial random guesses for rate optimization",
                    },
                ),
                "multiple_hits": (
                    "STRING",
                    {
                        "default": "None",
                        "options": cls.MULTIPLE_HITS,
                        "description": "Multiple-hit correction mode",
                        "advanced": True,
                    },
                ),
                "error_sink": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Include a rate class for misalignment artifacts",
                        "advanced": True,
                    },
                ),
                "save_alternative_model": (
                    "BOOLEAN",
                    {"default": False, "description": "Save the alternative BUSTED model fit"},
                ),
                "mss_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Enable multiple synonymous rate class substitution models",
                        "advanced": True,
                    },
                ),
                "mss_type": (
                    "STRING",
                    {
                        "default": "Full",
                        "options": cls.MSS_TYPES,
                        "description": "Multiple synonymous substitution model type",
                        "advanced": True,
                    },
                ),
                "mss_classes": (
                    "INT",
                    {"default": 2, "min": 1, "description": "Number of codon rate classes for Random MSS"},
                ),
                "mss_file": (
                    "FILE",
                    {"default": "", "description": "TSV file defining empirical rates or model partitions"},
                ),
                "mss_neutral": (
                    "STRING",
                    {"default": "neutral", "description": "Neutral class designation for file-based MSS models"},
                ),
                "kill_zero_lengths": (
                    "STRING",
                    {
                        "default": "Yes",
                        "options": cls.KILL_ZERO_LENGTHS,
                        "description": "Zero-length branch handling",
                        "advanced": True,
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }
