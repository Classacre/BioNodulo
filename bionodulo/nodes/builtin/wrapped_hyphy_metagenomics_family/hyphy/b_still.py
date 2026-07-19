"""Focused owner for ``hyphy_b_still``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from ..contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhyBStillNode(ToolsIUCCommandContract):
    """Detect invariant or near-invariant codon sites with HyPhy B-STILL."""

    NODE_ID = "hyphy_b_still"
    DISPLAY_NAME = "HyPhy-B-STILL"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Detect invariant or near-invariant codon sites with HyPhy B-STILL."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "B-STILL",
        "Bayesian Significance Test of Invariant Low Likelihoods",
        "FUBAR",
        "invariant sites",
        "purifying selection",
        "phylogenetics",
    ]
    RETURN_TYPES = ("JSON", "TEXT")
    RETURN_NAMES = ("b_still_output", "b_still_md_report")
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/SelectionAnalyses/B-STILL.bf"
    CITATION_DOIS = HYPHY_B_STILL_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_B_STILL_CITATION_DOIS]
    CITATION_TEXT = HYPHY_B_STILL_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS
    POSTERIOR_ESTIMATION_METHODS = ["Variational-Bayes", "Metropolis-Hastings", "Collapsed-Gibbs"]

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("input_ext", "fasta")).strip().lstrip(".") or "fasta"
        return f"input.{ext}"

    @classmethod
    def _yes_no(cls, value: Any) -> str:
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

        method = str(inputs.get("method", "Variational-Bayes") or "Variational-Bayes")
        cmd = [
            "hyphy",
            "b-still",
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
                "--ebf",
                str(inputs.get("ebf", 10.0)),
                "--radius-threshold",
                str(inputs.get("radius_threshold", 0.5)),
                "--kill-zero-lengths",
                str(inputs.get("kill_zero_lengths", "Yes") or "Yes"),
                "--output",
                f"{out}/b_still_output.json",
                ">",
                f"{out}/b_still_stdout.md",
            ]
        )
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "b_still_output.json", out / "b_still_stdout.md"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-B-STILL alignment input is required"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        method = str(inputs.get("method", "Variational-Bayes") or "Variational-Bayes")
        if method not in cls.POSTERIOR_ESTIMATION_METHODS:
            return f"Unsupported HyPhy-B-STILL posterior estimation method: {method}"

        try:
            grid = int(inputs.get("grid", 20))
        except (TypeError, ValueError):
            return "HyPhy-B-STILL grid points must be between 5 and 50"
        if grid < 5 or grid > 50:
            return "HyPhy-B-STILL grid points must be between 5 and 50"

        try:
            concentration = float(inputs.get("concentration_parameter", 0.5))
        except (TypeError, ValueError):
            return "HyPhy-B-STILL concentration parameter must be between 0.001 and 1"
        if concentration < 0.001 or concentration > 1:
            return "HyPhy-B-STILL concentration parameter must be between 0.001 and 1"

        try:
            ebf = float(inputs.get("ebf", 10.0))
        except (TypeError, ValueError):
            return "HyPhy-B-STILL EBF threshold must be non-negative"
        if ebf < 0:
            return "HyPhy-B-STILL EBF threshold must be non-negative"
        if ebf > 10000:
            return "HyPhy-B-STILL EBF threshold must be between 0 and 10000"

        try:
            radius_threshold = float(inputs.get("radius_threshold", 0.5))
        except (TypeError, ValueError):
            return "HyPhy-B-STILL radius threshold must be between 0 and 10"
        if radius_threshold < 0 or radius_threshold > 10:
            return "HyPhy-B-STILL radius threshold must be between 0 and 10"

        kill_zero_lengths = str(inputs.get("kill_zero_lengths", "Yes") or "Yes")
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f"Unsupported HyPhy-B-STILL zero-length branch handling: {kill_zero_lengths}"

        if method != "Variational-Bayes":
            try:
                chains = int(inputs.get("chains", 5))
            except (TypeError, ValueError):
                return "HyPhy-B-STILL chains must be between 2 and 20"
            if chains < 2 or chains > 20:
                return "HyPhy-B-STILL chains must be between 2 and 20"

            try:
                chain_length = int(inputs.get("chain_length", 2000000))
            except (TypeError, ValueError):
                return "HyPhy-B-STILL chain length must be between 500000 and 50000000"
            if chain_length < 500000 or chain_length > 50000000:
                return "HyPhy-B-STILL chain length must be between 500000 and 50000000"

            try:
                burn_in = int(inputs.get("burn_in", 1000000))
            except (TypeError, ValueError):
                return "HyPhy-B-STILL burn-in samples must be between 100000 and 1900000"
            if burn_in < 100000 or burn_in > 1900000:
                return "HyPhy-B-STILL burn-in samples must be between 100000 and 1900000"

            try:
                samples = int(inputs.get("samples", 100))
            except (TypeError, ValueError):
                return "HyPhy-B-STILL samples per chain must be between 50 and 1000000"
            if samples < 50 or samples > 1000000:
                return "HyPhy-B-STILL samples per chain must be between 50 and 1000000"
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
                "grid": (
                    "INT",
                    {
                        "default": 20,
                        "min": 5,
                        "max": 50,
                        "description": "Grid points used to approximate the posterior distribution",
                    },
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
                "ebf": (
                    "FLOAT",
                    {
                        "default": 10.0,
                        "min": 0,
                        "max": 10000,
                        "description": "Empirical Bayes Factor threshold for proximal invariance",
                    },
                ),
                "radius_threshold": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0,
                        "max": 10,
                        "description": "Expected substitution multiplier for near-zero selective regimes",
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
