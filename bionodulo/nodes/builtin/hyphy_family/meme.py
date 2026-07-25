"""Focused owner for ``hyphy_meme``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhyMEMENode(ToolsIUCCommandContract):
    """Detect pervasive or episodic site-level diversifying selection with HyPhy MEME."""

    NODE_ID = "hyphy_meme"
    DISPLAY_NAME = "HyPhy-MEME"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Detect pervasive or episodic site-level diversifying selection with HyPhy MEME."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "MEME",
        "Mixed Effects Model of Evolution",
        "episodic diversifying selection",
        "pervasive selection",
        "site-level selection",
        "positive selection",
        "multiple nucleotide substitutions",
        "imputed states",
        "phylogenetics",
    ]
    RETURN_TYPES = ("JSON", "TEXT")
    RETURN_NAMES = ("meme_output", "meme_md_report")
    REQUIRED_EXECUTABLES = ["HYPHYMPI", "mpirun"]
    DOCUMENTATION_URL = "http://hyphy.org/methods/selection-methods/#MEME"
    CITATION_DOIS = HYPHY_MEME_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_MEME_CITATION_DOIS]
    CITATION_TEXT = HYPHY_MEME_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    MULTIPLE_HITS = HyPhyABSRELNode.MULTIPLE_HITS
    SITE_MULTIHIT = ["Estimate", "No"]
    PRECISION_OPTIONS = ["standard", "reduced"]
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

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() in {"true", "yes", "1", "on"}
        return bool(value)

    @staticmethod
    def _yes_no(value: Any) -> str:
        return "Yes" if HyPhyMEMENode._bool_value(value) else "No"

    @staticmethod
    def _mpirun_prefix(threads: Any) -> str:
        return (
            '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe '
            '-mca orte_tmpdir_base "${TMPDIR:-.}" -np '
            f"{threads}"
            "}"
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get("input_nhx", "")).strip():
            commands.append(_shell_join(["ln", "-s", str(inputs.get("input_nhx", "")), "input.nhx"]))
        commands.append(_shell_join(["ln", "-s", str(inputs.get("input_file", "")), input_name]))

        cmd = [
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
                "--pvalue",
                str(inputs.get("p_value", 0.1)),
                "--resample",
                str(inputs.get("resample", 0)),
                "--rates",
                str(inputs.get("rates", 2)),
                "--multiple-hits",
                str(inputs.get("multiple_hits", "None") or "None"),
            ]
        )
        if str(inputs.get("multiple_hits", "None") or "None") != "None":
            cmd.extend(["--site-multihit", str(inputs.get("site_multihit", "Estimate") or "Estimate")])
        cmd.extend(
            [
                "--impute-states",
                cls._yes_no(inputs.get("impute_states", False)),
                "--precision",
                str(inputs.get("precision", "standard") or "standard"),
                "--kill-zero-lengths",
                str(inputs.get("kill_zero_lengths", "Yes") or "Yes"),
            ]
        )
        if cls._bool_value(inputs.get("restrict_sites", False)):
            cmd.extend(
                [
                    "--limit-to-sites",
                    str(inputs.get("limit_to_sites", "") or ""),
                    "--save-lf-for-sites",
                    str(inputs.get("save_lf_for_sites", "") or ""),
                ]
            )
        cmd.extend(
            [
                "--output",
                f"{out}/meme_output.json",
                "--full-model",
                cls._yes_no(inputs.get("full_model", True)),
                ">",
                f"{out}/meme_stdout.md",
            ]
        )
        commands.append(f"{cls._mpirun_prefix(inputs.get('threads', 4))} HYPHYMPI meme {_shell_join(cmd)}")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "meme_output.json", out / "meme_stdout.md"]

    @staticmethod
    def _validate_float_range(value: Any, message: str, low: float, high: float) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

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
            return "HyPhy-MEME alignment input is required"
        input_ext = str(inputs.get("input_ext", "fasta") or "fasta").strip().lstrip(".")
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f"Unsupported HyPhy-MEME input extension: {input_ext}"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        branch_sel = str(inputs.get("branch_sel", "All") or "All")
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f"Unsupported HyPhy-MEME branch selection: {branch_sel}"
        if branch_sel == "specify" and not str(inputs.get("branch_label", "")).strip():
            return "HyPhy-MEME custom branch selection requires a branch label"
        message = cls._validate_float_range(
            inputs.get("p_value", 0.1), "HyPhy-MEME p-value threshold must be between 0 and 1", 0, 1
        )
        if message:
            return message
        message = cls._validate_int_range(
            inputs.get("resample", 0), "HyPhy-MEME resampling replicates must be between 0 and 1000", 0, 1000
        )
        if message:
            return message
        message = cls._validate_int_range(
            inputs.get("rates", 2), "HyPhy-MEME omega rate classes must be between 2 and 4", 2, 4
        )
        if message:
            return message
        multiple_hits = str(inputs.get("multiple_hits", "None") or "None")
        if multiple_hits not in cls.MULTIPLE_HITS:
            return f"Unsupported HyPhy-MEME multiple-hits mode: {multiple_hits}"
        if multiple_hits != "None":
            site_multihit = str(inputs.get("site_multihit", "Estimate") or "Estimate")
            if site_multihit not in cls.SITE_MULTIHIT:
                return f"Unsupported HyPhy-MEME site-multihit mode: {site_multihit}"
        precision = str(inputs.get("precision", "standard") or "standard")
        if precision not in cls.PRECISION_OPTIONS:
            return f"Unsupported HyPhy-MEME optimization precision: {precision}"
        kill_zero_lengths = str(inputs.get("kill_zero_lengths", "Yes") or "Yes")
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f"Unsupported HyPhy-MEME zero-length branch handling: {kill_zero_lengths}"
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "HyPhy-MEME threads must be a positive integer"
        if threads < 1:
            return "HyPhy-MEME threads must be a positive integer"
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
                "p_value": (
                    "FLOAT",
                    {"default": 0.1, "min": 0, "max": 1, "description": "P-value threshold"},
                ),
                "resample": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 1000,
                        "description": "Parametric bootstrap resampling replicates per site",
                        "advanced": True,
                    },
                ),
                "rates": (
                    "INT",
                    {"default": 2, "min": 2, "max": 4, "description": "Number of omega rate classes"},
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
                "site_multihit": (
                    "STRING",
                    {
                        "default": "Estimate",
                        "options": cls.SITE_MULTIHIT,
                        "description": "Estimate multiple-hit rates for each site when multiple hits are enabled",
                        "advanced": True,
                    },
                ),
                "impute_states": (
                    "BOOLEAN",
                    {"default": False, "description": "Impute likely character states for each sequence"},
                ),
                "precision": (
                    "STRING",
                    {
                        "default": "standard",
                        "options": cls.PRECISION_OPTIONS,
                        "description": "Optimization precision for preliminary fits",
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
                "restrict_sites": (
                    "BOOLEAN",
                    {"default": False, "description": "Restrict MEME analysis to a subset of sites"},
                ),
                "limit_to_sites": (
                    "STRING",
                    {"default": "", "description": "Comma-separated 1-based site indices to analyze"},
                ),
                "save_lf_for_sites": (
                    "STRING",
                    {"default": "", "description": "Comma-separated sites for likelihood-function snapshots"},
                ),
                "full_model": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Perform branch length re-optimization under the full codon model",
                        "advanced": True,
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }
