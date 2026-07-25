"""Focused owner for ``hyphy_slac``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhySLACNode(ToolsIUCCommandContract):
    """Detect pervasive site-level selection with HyPhy SLAC."""

    NODE_ID = "hyphy_slac"
    DISPLAY_NAME = "HyPhy-SLAC"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Detect pervasive site-level selection with HyPhy SLAC."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "SLAC",
        "Single Likelihood Ancestor Counting",
        "pervasive selection",
        "site-level selection",
        "ancestral state reconstruction",
        "synonymous substitutions",
        "nonsynonymous substitutions",
        "positive selection",
        "purifying selection",
        "phylogenetics",
    ]
    RETURN_TYPES = ("TEXT", "JSON")
    RETURN_NAMES = ("slac_md_report", "slac_output")
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "http://hyphy.org/methods/selection-methods/#SLAC"
    CITATION_DOIS = HYPHY_SLAC_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_SLAC_CITATION_DOIS]
    CITATION_TEXT = HYPHY_SLAC_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS

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
        cmd = [
            "hyphy",
            f"CPU={inputs.get('threads', 4)}",
            "slac",
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
                "--samples",
                str(inputs.get("number_of_samples", 0)),
                "--pvalue",
                str(inputs.get("p_value", 0.1)),
                "--output",
                f"{out}/slac_output.json",
                "--kill-zero-lengths",
                str(inputs.get("kill_zero_lengths", "Yes") or "Yes"),
                ">",
                f"{out}/slac_stdout.md",
            ]
        )
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "slac_stdout.md", out / "slac_output.json"]

    @staticmethod
    def _validate_unit_float(value: Any, message: str) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < 0 or parsed > 1 else None

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-SLAC alignment input is required"
        input_ext = str(inputs.get("input_ext", "fasta") or "fasta").strip().lstrip(".")
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f"Unsupported HyPhy-SLAC input extension: {input_ext}"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        branch_sel = str(inputs.get("branch_sel", "All") or "All")
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f"Unsupported HyPhy-SLAC branch selection: {branch_sel}"
        if branch_sel == "specify" and not str(inputs.get("branch_label", "")).strip():
            return "HyPhy-SLAC custom branch selection requires a branch label"
        message = cls._validate_unit_float(
            inputs.get("p_value", 0.1), "HyPhy-SLAC p-value threshold must be between 0 and 1"
        )
        if message:
            return message
        message = cls._validate_int_range(
            inputs.get("number_of_samples", 0),
            "HyPhy-SLAC ancestral reconstruction samples must be between 0 and 10000",
            0,
            10000,
        )
        if message:
            return message
        kill_zero_lengths = str(inputs.get("kill_zero_lengths", "Yes") or "Yes")
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f"Unsupported HyPhy-SLAC zero-length branch handling: {kill_zero_lengths}"
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "HyPhy-SLAC threads must be a positive integer"
        if threads < 1:
            return "HyPhy-SLAC threads must be a positive integer"
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
                        "description": "Branches to include in SLAC calculations",
                    },
                ),
                "branch_label": (
                    "STRING",
                    {"default": "", "description": "Custom branch label when branch selection is specify"},
                ),
                "p_value": (
                    "FLOAT",
                    {"default": 0.1, "min": 0, "max": 1, "description": "P-value threshold"},
                ),
                "number_of_samples": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 10000,
                        "description": "Alternative ancestral reconstructions to sample for uncertainty",
                    },
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
