"""Focused owner for ``hyphy_fade``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode
from .b_still import HyPhyBStillNode
from .bgm import HyPhyBGMNode

class HyPhyFADENode(ToolsIUCCommandContract):
    """Test protein alignments for directional selection with HyPhy FADE."""

    NODE_ID = "hyphy_fade"
    DISPLAY_NAME = "HyPhy-FADE"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Test a protein alignment for directional selection with HyPhy FADE."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "FADE",
        "FUBAR Approach to Directional Evolution",
        "directional selection",
        "protein alignment",
        "amino acid substitution bias",
        "empirical Bayes factor",
        "phylogenetics",
    ]
    RETURN_TYPES = ("JSON", "TEXT")
    RETURN_NAMES = ("fade_output", "fade_md_report")
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "http://hyphy.org/methods/selection-methods/#FADE"
    CITATION_DOIS = HYPHY_FADE_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_FADE_CITATION_DOIS]
    CITATION_TEXT = HYPHY_FADE_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    AMINO_ACID_MODELS = HyPhyBGMNode.AMINO_ACID_MODELS
    POSTERIOR_ESTIMATION_METHODS = HyPhyBStillNode.POSTERIOR_ESTIMATION_METHODS

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

        method = str(inputs.get("method", "Variational-Bayes") or "Variational-Bayes")
        cmd = [
            "hyphy",
            "fade",
            "--alignment",
            input_name,
        ]
        if str(inputs.get("input_nhx", "")).strip():
            cmd.extend(["--tree", "input.nhx"])
        cmd.extend(
            [
                "--branches",
                cls._branch_arg(inputs),
                "--model",
                str(inputs.get("model", "GTR") or "GTR"),
                "--method",
                method,
            ]
        )
        if method != "Variational-Bayes":
            cmd.extend(
                [
                    "--chains",
                    str(inputs.get("chains", 5)),
                    "--chain-length",
                    str(inputs.get("chain_length", 2000000)),
                    "--burn-in",
                    str(inputs.get("burn_in", 1000000)),
                    "--samples",
                    str(inputs.get("samples", 100)),
                ]
            )
        cmd.extend(
            [
                "--grid",
                str(inputs.get("grid", 20)),
                "--concentration_parameter",
                str(inputs.get("concentration_parameter", 0.5)),
                "--output",
                f"{out}/fade_output.json",
                ">",
                f"{out}/fade_stdout.md",
            ]
        )
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "fade_output.json", out / "fade_stdout.md"]

    @staticmethod
    def _validate_int_range(value: Any, label: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"HyPhy-FADE {label} must be between {low} and {high}"
        if parsed < low or parsed > high:
            return f"HyPhy-FADE {label} must be between {low} and {high}"
        return None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-FADE protein alignment input is required"
        input_ext = str(inputs.get("input_ext", "fasta") or "fasta").strip().lstrip(".")
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f"Unsupported HyPhy-FADE input extension: {input_ext}"
        branch_sel = str(inputs.get("branch_sel", "All") or "All")
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f"Unsupported HyPhy-FADE branch selection: {branch_sel}"
        if branch_sel == "specify" and not str(inputs.get("branch_label", "")).strip():
            return "HyPhy-FADE custom branch selection requires a branch label"
        model = str(inputs.get("model", "GTR") or "GTR")
        if model not in cls.AMINO_ACID_MODELS:
            return f"Unsupported HyPhy-FADE amino-acid substitution model: {model}"
        method = str(inputs.get("method", "Variational-Bayes") or "Variational-Bayes")
        if method not in cls.POSTERIOR_ESTIMATION_METHODS:
            return f"Unsupported HyPhy-FADE posterior estimation method: {method}"
        message = cls._validate_int_range(inputs.get("grid", 20), "grid points", 5, 50)
        if message:
            return message
        try:
            concentration = float(inputs.get("concentration_parameter", 0.5))
        except (TypeError, ValueError):
            return "HyPhy-FADE concentration parameter must be between 0.001 and 1"
        if concentration < 0.001 or concentration > 1:
            return "HyPhy-FADE concentration parameter must be between 0.001 and 1"
        if method != "Variational-Bayes":
            for key, default, label, low, high in [
                ("chains", 5, "chains", 2, 20),
                ("chain_length", 2000000, "chain length", 500000, 50000000),
                ("burn_in", 1000000, "burn-in samples", 100000, 1900000),
                ("samples", 100, "samples per chain", 50, 1000000),
            ]:
                message = cls._validate_int_range(inputs.get(key, default), label, low, high)
                if message:
                    return message
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "FASTA",
                    {"description": "Protein alignment in FASTA, compressed FASTA, or NEXUS format"},
                ),
            },
            "optional": {
                "input_nhx": ("FILE", {"default": "", "description": "Optional rooted Newick/NHX phylogenetic tree"}),
                "input_ext": (
                    "STRING",
                    {"default": "fasta", "options": cls.INPUT_EXTENSIONS, "advanced": True},
                ),
                "branch_sel": (
                    "STRING",
                    {
                        "default": "All",
                        "options": cls.BRANCH_SELECTIONS,
                        "description": "Branches to test for directional selection",
                    },
                ),
                "branch_label": (
                    "STRING",
                    {"default": "", "description": "Custom branch label when branch selection is specify"},
                ),
                "model": (
                    "STRING",
                    {
                        "default": "GTR",
                        "options": cls.AMINO_ACID_MODELS,
                        "description": "Baseline amino-acid substitution model",
                    },
                ),
                "method": (
                    "STRING",
                    {
                        "default": "Variational-Bayes",
                        "options": cls.POSTERIOR_ESTIMATION_METHODS,
                        "description": "Posterior estimation method",
                    },
                ),
                "grid": (
                    "INT",
                    {"default": 20, "min": 5, "max": 50, "description": "Grid points per dimension"},
                ),
                "concentration_parameter": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.001,
                        "max": 1,
                        "description": "Dirichlet prior concentration parameter",
                    },
                ),
                "chains": (
                    "INT",
                    {"default": 5, "min": 2, "max": 20, "description": "Number of MCMC chains", "advanced": True},
                ),
                "chain_length": (
                    "INT",
                    {
                        "default": 2000000,
                        "min": 500000,
                        "max": 50000000,
                        "description": "Length of each MCMC chain",
                        "advanced": True,
                    },
                ),
                "burn_in": (
                    "INT",
                    {
                        "default": 1000000,
                        "min": 100000,
                        "max": 1900000,
                        "description": "Samples to use for burn-in",
                        "advanced": True,
                    },
                ),
                "samples": (
                    "INT",
                    {
                        "default": 100,
                        "min": 50,
                        "max": 1000000,
                        "description": "Samples to draw from each chain",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
