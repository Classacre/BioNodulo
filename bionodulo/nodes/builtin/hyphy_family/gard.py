"""Focused owner for ``hyphy_gard``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode
from .bgm import HyPhyBGMNode

class HyPhyGARDNode(ToolsIUCCommandContract):
    """Detect recombination breakpoints with HyPhy GARD."""

    NODE_ID = "hyphy_gard"
    DISPLAY_NAME = "HyPhy-GARD"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Detect recombination breakpoints with HyPhy Genetic Algorithm for Recombination Detection."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "GARD",
        "Genetic Algorithm for Recombination Detection",
        "recombination detection",
        "breakpoints",
        "phylogenetic incongruence",
        "partitioned alignment",
        "site-to-site rate variation",
        "phylogenetics",
    ]
    RETURN_TYPES = ("ALIGNMENT", "JSON", "TEXT")
    RETURN_NAMES = ("gard_output", "gard_output_json", "gard_md_report")
    REQUIRED_EXECUTABLES = ["HYPHYMPI", "mpirun"]
    DOCUMENTATION_URL = "https://veg.github.io/hyphy-site/methods/gard/"
    CITATION_DOIS = HYPHY_GARD_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_GARD_CITATION_DOIS]
    CITATION_TEXT = HYPHY_GARD_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    DATATYPES = ["nucleotide", "amino-acid", "codon"]
    AMINO_ACID_MODELS = HyPhyBGMNode.AMINO_ACID_MODELS
    RATE_VARIATION = ["", "GDD", "Gamma"]
    RUN_MODES = ["Normal", "Faster"]

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("input_ext", "fasta")).strip().lstrip(".") or "fasta"
        return f"input.{ext}"

    @staticmethod
    def _mpirun_prefix(threads: Any) -> str:
        return (
            '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe '
            '-mca orte_tmpdir_base "${TMPDIR:-.}" -np '
            f"{threads}"
            "}"
        )

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands = [_shell_join(["ln", "-s", str(inputs.get("input_file", "")), input_name])]

        datatype = str(inputs.get("datatype", "nucleotide") or "nucleotide")
        cmd = [
            "--alignment",
            input_name,
            "--type",
            datatype,
        ]
        if datatype == "codon":
            cmd.extend(["--code", str(inputs.get("gencodeid", "Universal") or "Universal")])
        if datatype == "amino-acid":
            cmd.extend(["--model", str(inputs.get("model", "GTR") or "GTR")])
        rate = str(inputs.get("rate", "") or "")
        if rate:
            cmd.extend(["--rv", rate, "--rate-classes", str(inputs.get("rate_classes", 2))])
        cmd.extend(
            [
                "--max-breakpoints",
                str(inputs.get("max_breakpoints", 10000)),
                "--mode",
                str(inputs.get("mode", "Normal") or "Normal"),
            ]
        )
        command = (
            f"{cls._mpirun_prefix(inputs.get('threads', 4))} HYPHYMPI gard "
            f"{_shell_join(cmd)} "
            'ENV="TOLERATE_NUMERICAL_ERRORS=1;" '
            f"--output {_shell_join([f'{out}/gard_output.json'])} "
            f"--output-lf {_shell_join([f'{out}/gard_output.nex'])} > {_shell_join([f'{out}/gard_stdout.md'])}"
        )
        commands.append(command)
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "gard_output.nex", out / "gard_output.json", out / "gard_stdout.md"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-GARD alignment input is required"
        input_ext = str(inputs.get("input_ext", "fasta") or "fasta").strip().lstrip(".")
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f"Unsupported HyPhy-GARD input extension: {input_ext}"
        datatype = str(inputs.get("datatype", "nucleotide") or "nucleotide")
        if datatype not in cls.DATATYPES:
            return f"Unsupported HyPhy-GARD data type: {datatype}"
        if datatype == "amino-acid":
            model = str(inputs.get("model", "GTR") or "GTR")
            if model not in cls.AMINO_ACID_MODELS:
                return f"Unsupported HyPhy-GARD amino-acid substitution model: {model}"
        if datatype == "codon":
            gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
            if gencodeid not in cls.GENETIC_CODES:
                return f"Unsupported HyPhy genetic code: {gencodeid}"
        rate = str(inputs.get("rate", "") or "")
        if rate not in cls.RATE_VARIATION:
            return f"Unsupported HyPhy-GARD rate variation setting: {rate}"
        if rate:
            message = cls._validate_int_range(
                inputs.get("rate_classes", 2), "HyPhy-GARD rate classes must be between 2 and 6", 2, 6
            )
            if message:
                return message
        message = cls._validate_int_range(
            inputs.get("max_breakpoints", 10000),
            "HyPhy-GARD maximum breakpoints must be between 1 and 10000",
            1,
            10000,
        )
        if message:
            return message
        mode = str(inputs.get("mode", "Normal") or "Normal")
        if mode not in cls.RUN_MODES:
            return f"Unsupported HyPhy-GARD run mode: {mode}"
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "HyPhy-GARD threads must be a positive integer"
        if threads < 1:
            return "HyPhy-GARD threads must be a positive integer"
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
                "input_ext": (
                    "STRING",
                    {"default": "fasta", "options": cls.INPUT_EXTENSIONS, "advanced": True},
                ),
                "datatype": (
                    "STRING",
                    {"default": "nucleotide", "options": cls.DATATYPES, "description": "Alignment data type"},
                ),
                "model": (
                    "STRING",
                    {
                        "default": "GTR",
                        "options": cls.AMINO_ACID_MODELS,
                        "description": "Amino-acid substitution model used for protein alignments",
                    },
                ),
                "gencodeid": (
                    "STRING",
                    {
                        "default": "Universal",
                        "options": cls.GENETIC_CODES,
                        "description": "HyPhy genetic code used for codon alignments",
                    },
                ),
                "rate": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.RATE_VARIATION,
                        "description": "Site-to-site rate variation model",
                    },
                ),
                "rate_classes": (
                    "INT",
                    {"default": 2, "min": 2, "max": 6, "description": "Discrete rate classes for GDD or Gamma"},
                ),
                "max_breakpoints": (
                    "INT",
                    {
                        "default": 10000,
                        "min": 1,
                        "max": 10000,
                        "description": "Maximum number of breakpoints to consider",
                        "advanced": True,
                    },
                ),
                "mode": (
                    "STRING",
                    {
                        "default": "Normal",
                        "options": cls.RUN_MODES,
                        "description": "Run mode for optimization and convergence settings",
                        "advanced": True,
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }
