"""Focused owner for ``hyphy_fubar``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode
from .b_still import HyPhyBStillNode

class HyPhyFUBARNode(ToolsIUCCommandContract):
    """Detect pervasive site-level selection with HyPhy FUBAR."""

    NODE_ID = "hyphy_fubar"
    DISPLAY_NAME = "HyPhy-FUBAR"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Detect pervasive site-level selection with HyPhy FUBAR."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "FUBAR",
        "Fast Unconstrained Bayesian AppRoximation",
        "pervasive selection",
        "site-level selection",
        "diversifying selection",
        "purifying selection",
        "posterior probability",
        "empirical Bayes factor",
        "phylogenetics",
    ]
    RETURN_TYPES = ("JSON", "TEXT")
    RETURN_NAMES = ("fubar_output", "fubar_md_report")
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "http://hyphy.org/methods/selection-methods/#FUBAR"
    CITATION_DOIS = HYPHY_FUBAR_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_FUBAR_CITATION_DOIS]
    CITATION_TEXT = HYPHY_FUBAR_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    POSTERIOR_ESTIMATION_METHODS = HyPhyBStillNode.POSTERIOR_ESTIMATION_METHODS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("input_ext", "fasta")).strip().lstrip(".") or "fasta"
        return f"input.{ext}"

    @staticmethod
    def _yes_no(value: Any) -> str:
        if isinstance(value, str):
            return "Yes" if value.lower() in {"true", "yes", "1", "on", "yes"} else "No"
        return "Yes" if bool(value) else "No"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get("input_nhx", "")).strip():
            commands.append(_shell_join(["ln", "-s", str(inputs.get("input_nhx", "")), "input.nhx"]))
        commands.append(_shell_join(["ln", "-s", str(inputs.get("input_file", "")), input_name]))
        commands.append(_shell_join(["ln", "-s", f"{out}/fubar_output.json", f"{input_name}.FUBAR.json"]))

        method = str(inputs.get("method", "Variational-Bayes") or "Variational-Bayes")
        cmd = [
            "hyphy",
            "fubar",
            "--alignment",
            f"./{input_name}",
        ]
        if str(inputs.get("input_nhx", "")).strip():
            cmd.extend(["--tree", "input.nhx"])
        cmd.extend(
            [
                "--code",
                str(inputs.get("gencodeid", "Universal") or "Universal"),
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
                "--non-zero",
                cls._yes_no(inputs.get("non_zero", False)),
                "--kill-zero-lengths",
                str(inputs.get("kill_zero_lengths", "Yes") or "Yes"),
                ">",
                f"{out}/fubar_stdout.md",
            ]
        )
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "fubar_output.json", out / "fubar_stdout.md"]

    @staticmethod
    def _validate_int_range(value: Any, label: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"HyPhy-FUBAR {label} must be between {low} and {high}"
        if parsed < low or parsed > high:
            return f"HyPhy-FUBAR {label} must be between {low} and {high}"
        return None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-FUBAR alignment input is required"
        input_ext = str(inputs.get("input_ext", "fasta") or "fasta").strip().lstrip(".")
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f"Unsupported HyPhy-FUBAR input extension: {input_ext}"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        method = str(inputs.get("method", "Variational-Bayes") or "Variational-Bayes")
        if method not in cls.POSTERIOR_ESTIMATION_METHODS:
            return f"Unsupported HyPhy-FUBAR posterior estimation method: {method}"
        message = cls._validate_int_range(inputs.get("grid", 20), "grid points", 5, 50)
        if message:
            return message
        try:
            concentration = float(inputs.get("concentration_parameter", 0.5))
        except (TypeError, ValueError):
            return "HyPhy-FUBAR concentration parameter must be between 0.001 and 1"
        if concentration < 0.001 or concentration > 1:
            return "HyPhy-FUBAR concentration parameter must be between 0.001 and 1"
        kill_zero_lengths = str(inputs.get("kill_zero_lengths", "Yes") or "Yes")
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f"Unsupported HyPhy-FUBAR zero-length branch handling: {kill_zero_lengths}"
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
                "non_zero": (
                    "BOOLEAN",
                    {"default": False, "description": "Enforce non-zero synonymous rates on the grid"},
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
                "kill_zero_lengths": (
                    "STRING",
                    {
                        "default": "Yes",
                        "options": cls.KILL_ZERO_LENGTHS,
                        "description": "Zero-length branch handling",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
