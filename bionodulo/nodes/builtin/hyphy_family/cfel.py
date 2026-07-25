"""Focused owner for ``hyphy_cfel``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhyCFELNode(ToolsIUCCommandContract):
    """Compare site-wise selective pressures among branch sets with HyPhy Contrast-FEL."""

    NODE_ID = "hyphy_cfel"
    DISPLAY_NAME = "HyPhy-CFEL"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Test for site-wise selective pressure differences among clades or branch sets with HyPhy Contrast-FEL."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "CFEL",
        "Contrast-FEL",
        "Fixed Effects Likelihood",
        "Contrast-FEL branch sets",
        "branch sets",
        "clade selection",
        "selective pressure differences",
        "site-wise selection",
        "phylogenetics",
    ]
    RETURN_TYPES = ("JSON", "TEXT")
    RETURN_NAMES = ("cfel_output", "cfel_md_report")
    REQUIRED_EXECUTABLES = ["HYPHYMPI", "mpirun"]
    DOCUMENTATION_URL = "http://www.hyphy.org/methods/other/contrast-fel/"
    CITATION_DOIS = HYPHY_CFEL_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_CFEL_CITATION_DOIS]
    CITATION_TEXT = HYPHY_CFEL_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS
    SRV_OPTIONS = ["Yes", "No"]

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("input_ext", "fasta")).strip().lstrip(".") or "fasta"
        return f"input.{ext}"

    @staticmethod
    def _bool_yes_no(value: Any) -> str:
        if isinstance(value, str):
            return "Yes" if value.lower() in {"true", "yes", "1", "on"} else "No"
        return "Yes" if bool(value) else "No"

    @staticmethod
    def _mpirun_prefix(threads: Any) -> str:
        return (
            '${GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe '
            '-mca orte_tmpdir_base "${TMPDIR:-.}" -np '
            f"{threads}"
            "}"
        )

    @classmethod
    def _branch_sets(cls, inputs: dict[str, Any]) -> list[str]:
        values = _as_list(inputs.get("branch_sets", inputs.get("branch_labels", ["Test"])))
        return values or ["Test"]

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
            input_name,
        ]
        if str(inputs.get("input_nhx", "")).strip():
            cmd.extend(["--tree", "input.nhx"])
        cmd.extend(["--code", str(inputs.get("gencodeid", "Universal") or "Universal")])
        for branch_set in cls._branch_sets(inputs):
            cmd.extend(["--branch-set", branch_set])
        cmd.extend(
            [
                "--srv",
                str(inputs.get("srv", "Yes") or "Yes"),
                "--permutations",
                cls._bool_yes_no(inputs.get("permutations", False)),
                "--pvalue",
                str(inputs.get("pvalue", 0.05)),
                "--qvalue",
                str(inputs.get("qvalue", 0.2)),
            ]
        )
        _add_if_value(cmd, "--limit-to-sites", inputs.get("limit_to_sites"))
        _add_if_value(cmd, "--save-lf-for-sites", inputs.get("save_lf_for_sites"))
        if cls._bool_yes_no(inputs.get("intermediate_fits", False)) == "Yes":
            cmd.extend(["--intermediate-fits", f"{out}/intermediate_fits.json"])
        cmd.extend(
            [
                "--kill-zero-lengths",
                str(inputs.get("kill_zero_lengths", "Yes") or "Yes"),
                "--output",
                f"{out}/cfel_output.json",
                ">",
                f"{out}/cfel_stdout.md",
            ]
        )
        commands.append(f"{cls._mpirun_prefix(inputs.get('threads', 4))} HYPHYMPI contrast-fel {_shell_join(cmd)}")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "cfel_output.json", out / "cfel_stdout.md"]

    @staticmethod
    def _validate_unit_float(value: Any, message: str) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < 0 or parsed > 1 else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-CFEL alignment input is required"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        raw_branch_sets = inputs.get("branch_sets", inputs.get("branch_labels", ["Test"]))
        branch_sets = [str(value) for value in raw_branch_sets] if isinstance(raw_branch_sets, (list, tuple)) else _as_list(raw_branch_sets)
        if not branch_sets:
            return "HyPhy-CFEL requires at least one branch set"
        if any(not branch_set.strip() for branch_set in branch_sets):
            return "HyPhy-CFEL branch set labels must be non-empty"
        srv = str(inputs.get("srv", "Yes") or "Yes")
        if srv not in cls.SRV_OPTIONS:
            return f"Unsupported HyPhy-CFEL synonymous rate variation setting: {srv}"
        message = cls._validate_unit_float(inputs.get("pvalue", 0.05), "HyPhy-CFEL p-value threshold must be between 0 and 1")
        if message:
            return message
        message = cls._validate_unit_float(inputs.get("qvalue", 0.2), "HyPhy-CFEL q-value threshold must be between 0 and 1")
        if message:
            return message
        kill_zero_lengths = str(inputs.get("kill_zero_lengths", "Yes") or "Yes")
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f"Unsupported HyPhy-CFEL zero-length branch handling: {kill_zero_lengths}"
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "HyPhy-CFEL threads must be a positive integer"
        if threads < 1:
            return "HyPhy-CFEL threads must be a positive integer"
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
                "branch_sets": (
                    "STRING",
                    {
                        "default": ["Test"],
                        "multiple": True,
                        "description": "Branch-set labels to compare, including tree labels or built-in branch sets",
                    },
                ),
                "pvalue": (
                    "FLOAT",
                    {"default": 0.05, "min": 0, "max": 1, "description": "Significance threshold for site tests"},
                ),
                "qvalue": (
                    "FLOAT",
                    {"default": 0.2, "min": 0, "max": 1, "description": "False discovery rate reporting threshold"},
                ),
                "srv": (
                    "STRING",
                    {
                        "default": "Yes",
                        "options": cls.SRV_OPTIONS,
                        "description": "Include synonymous rate variation",
                    },
                ),
                "permutations": (
                    "BOOLEAN",
                    {"default": False, "description": "Perform permutation significance tests"},
                ),
                "limit_to_sites": (
                    "STRING",
                    {"default": "", "description": "Comma/range list of 1-based sites to analyze"},
                ),
                "save_lf_for_sites": (
                    "STRING",
                    {"default": "", "description": "Comma/range list of sites for likelihood-function snapshots"},
                ),
                "intermediate_fits": (
                    "BOOLEAN",
                    {"default": False, "description": "Save intermediate initial-guess model fits"},
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
