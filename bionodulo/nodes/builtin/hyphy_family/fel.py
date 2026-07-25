"""Focused owner for ``hyphy_fel``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhyFELNode(ToolsIUCCommandContract):
    """Detect pervasive site-level selection with HyPhy FEL."""

    NODE_ID = "hyphy_fel"
    DISPLAY_NAME = "HyPhy-FEL"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Detect pervasive site-level selection with HyPhy Fixed Effects Likelihood."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "FEL",
        "Fixed Effects Likelihood",
        "pervasive selection",
        "site-level selection",
        "diversifying selection",
        "purifying selection",
        "synonymous rate variation",
        "multiple nucleotide substitutions",
        "phylogenetics",
    ]
    RETURN_TYPES = ("JSON", "TEXT")
    RETURN_NAMES = ("fel_output", "fel_md_report")
    REQUIRED_EXECUTABLES = ["HYPHYMPI", "mpirun"]
    DOCUMENTATION_URL = "http://hyphy.org/methods/selection-methods/#FEL"
    CITATION_DOIS = HYPHY_FEL_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_FEL_CITATION_DOIS]
    CITATION_TEXT = HYPHY_FEL_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    MULTIPLE_HITS = HyPhyABSRELNode.MULTIPLE_HITS
    SITE_MULTIHIT = ["Estimate", "No"]
    SRV_OPTIONS = ["Yes", "No"]
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
                "--multiple-hits",
                str(inputs.get("multiple_hits", "None") or "None"),
                "--branches",
                cls._branch_arg(inputs),
                "--srv",
                str(inputs.get("srv", "Yes") or "Yes"),
                "--pvalue",
                str(inputs.get("pvalue", 0.1)),
            ]
        )
        resample = inputs.get("resample", 0)
        if str(resample) not in {"", "0"}:
            cmd.extend(["--resample", str(resample)])
        if cls._bool_value(inputs.get("restrict_sites", False)):
            cmd.extend(
                [
                    "--limit-to-sites",
                    str(inputs.get("limit_to_sites", "null") or "null"),
                    "--save-lf-for-sites",
                    str(inputs.get("save_lf_for_sites", "null") or "null"),
                ]
            )
        cmd.extend(["--precision", str(inputs.get("precision", "standard") or "standard")])
        if cls._bool_value(inputs.get("ci", False)):
            cmd.extend(["--ci", "Yes"])
        cmd.extend(["--output", f"{out}/fel_output.json"])
        multiple_hits = str(inputs.get("multiple_hits", "None") or "None")
        if multiple_hits != "None":
            cmd.extend(["--site-multihit", str(inputs.get("site_multihit", "Estimate") or "Estimate")])
        cmd.extend(["--kill-zero-lengths", str(inputs.get("kill_zero_lengths", "Yes") or "Yes")])
        if cls._bool_value(inputs.get("full_model", True)):
            cmd.extend(["--full-model", "Yes"])
        cmd.extend([">", f"{out}/fel_stdout.md"])
        commands.append(f"{cls._mpirun_prefix(inputs.get('threads', 4))} HYPHYMPI fel {_shell_join(cmd)}")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "fel_output.json", out / "fel_stdout.md"]

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
            return "HyPhy-FEL alignment input is required"
        input_ext = str(inputs.get("input_ext", "fasta") or "fasta").strip().lstrip(".")
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f"Unsupported HyPhy-FEL input extension: {input_ext}"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        branch_sel = str(inputs.get("branch_sel", "All") or "All")
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f"Unsupported HyPhy-FEL branch selection: {branch_sel}"
        if branch_sel == "specify" and not str(inputs.get("branch_label", "")).strip():
            return "HyPhy-FEL custom branch selection requires a branch label"
        multiple_hits = str(inputs.get("multiple_hits", "None") or "None")
        if multiple_hits not in cls.MULTIPLE_HITS:
            return f"Unsupported HyPhy-FEL multiple-hits mode: {multiple_hits}"
        if multiple_hits != "None":
            site_multihit = str(inputs.get("site_multihit", "Estimate") or "Estimate")
            if site_multihit not in cls.SITE_MULTIHIT:
                return f"Unsupported HyPhy-FEL site-multihit mode: {site_multihit}"
        srv = str(inputs.get("srv", "Yes") or "Yes")
        if srv not in cls.SRV_OPTIONS:
            return f"Unsupported HyPhy-FEL synonymous rate variation setting: {srv}"
        message = cls._validate_unit_float(inputs.get("pvalue", 0.1), "HyPhy-FEL p-value threshold must be between 0 and 1")
        if message:
            return message
        message = cls._validate_int_range(inputs.get("resample", 0), "HyPhy-FEL resampling replicates must be between 0 and 1000", 0, 1000)
        if message:
            return message
        precision = str(inputs.get("precision", "standard") or "standard")
        if precision not in cls.PRECISION_OPTIONS:
            return f"Unsupported HyPhy-FEL optimization precision: {precision}"
        kill_zero_lengths = str(inputs.get("kill_zero_lengths", "Yes") or "Yes")
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f"Unsupported HyPhy-FEL zero-length branch handling: {kill_zero_lengths}"
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "HyPhy-FEL threads must be a positive integer"
        if threads < 1:
            return "HyPhy-FEL threads must be a positive integer"
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
                        "description": "Branches to test for pervasive selection",
                    },
                ),
                "branch_label": (
                    "STRING",
                    {"default": "", "description": "Custom branch label when branch selection is specify"},
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
                "srv": (
                    "STRING",
                    {
                        "default": "Yes",
                        "options": cls.SRV_OPTIONS,
                        "description": "Include synonymous rate variation",
                    },
                ),
                "pvalue": (
                    "FLOAT",
                    {"default": 0.1, "min": 0, "max": 1, "description": "P-value threshold for site tests"},
                ),
                "ci": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Compute profile likelihood confidence intervals for each variable site",
                        "advanced": True,
                    },
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
                "restrict_sites": (
                    "BOOLEAN",
                    {"default": False, "description": "Restrict FEL analysis to a subset of sites"},
                ),
                "limit_to_sites": (
                    "STRING",
                    {"default": "null", "description": "Comma-separated 1-based site indices to analyze"},
                ),
                "save_lf_for_sites": (
                    "STRING",
                    {"default": "null", "description": "Comma-separated sites for likelihood-function snapshots"},
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
                "full_model": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Re-optimize branch lengths under the full codon model",
                        "advanced": True,
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }
