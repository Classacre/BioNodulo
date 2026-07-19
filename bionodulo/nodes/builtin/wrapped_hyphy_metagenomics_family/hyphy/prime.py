"""Focused owner for ``hyphy_prime``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from ..contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhyPRIMENode(ToolsIUCCommandContract):
    """Model site-level physicochemical selection with HyPhy PRIME."""

    NODE_ID = "hyphy_prime"
    DISPLAY_NAME = "HyPhy-PRIME"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Model site-level physicochemical selection with HyPhy PRIME."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "PRIME",
        "Property Informed Models of Evolution",
        "PRoperty Informed Models of Evolution",
        "physicochemical selection",
        "biochemical properties",
        "amino-acid properties",
        "property-informed codon model",
        "site-level constraints",
        "protein evolution",
        "phylogenetics",
    ]
    RETURN_TYPES = ("JSON", "TEXT", "JSON")
    RETURN_NAMES = ("prime_output", "prime_md_report", "intermediate_fits")
    REQUIRED_EXECUTABLES = ["HYPHYMPI", "mpirun"]
    DOCUMENTATION_URL = "http://hyphy.org/methods/selection-methods/#PRIME"
    CITATION_DOIS = HYPHY_PRIME_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_PRIME_CITATION_DOIS]
    CITATION_TEXT = HYPHY_PRIME_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS
    PROPERTY_SOURCE_TYPES = ["builtin", "custom"]
    PROPERTY_SETS = [
        "Atchley",
        "2PROP",
        "3PROP",
        "4PROP",
        "5PROP",
        "Random-2",
        "Random-3",
        "Random-4",
        "Random-5",
    ]

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
        return "Yes" if HyPhyPRIMENode._bool_value(value) else "No"

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
            ]
        )
        if str(inputs.get("prop_source_type", "builtin") or "builtin") == "custom":
            cmd.extend(["--property-set", "Custom", "--property-file", str(inputs.get("property_file", ""))])
        else:
            cmd.extend(["--property-set", str(inputs.get("prop_set", "3PROP") or "3PROP")])
        cmd.extend(
            [
                "--pvalue",
                str(inputs.get("p_value", 0.1)),
                "--impute-states",
                cls._yes_no(inputs.get("impute_states", False)),
            ]
        )
        if cls._bool_value(inputs.get("save_intermediate", False)):
            cmd.extend(["--intermediate-fits", f"{out}/intermediate_fits.json"])
        cmd.extend(
            [
                "--kill-zero-lengths",
                str(inputs.get("kill_zero_lengths", "Yes") or "Yes"),
                "--output",
                f"{out}/prime_output.json",
                ">",
                f"{out}/prime_stdout.md",
            ]
        )
        commands.append(f"{cls._mpirun_prefix(inputs.get('threads', 4))} HYPHYMPI prime {_shell_join(cmd)}")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "prime_output.json", out / "prime_stdout.md"]
        if cls._bool_value(inputs.get("save_intermediate", False)):
            outputs.append(out / "intermediate_fits.json")
        return outputs

    @staticmethod
    def _validate_float_range(value: Any, message: str, low: float, high: float) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-PRIME alignment input is required"
        input_ext = str(inputs.get("input_ext", "fasta") or "fasta").strip().lstrip(".")
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f"Unsupported HyPhy-PRIME input extension: {input_ext}"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        branch_sel = str(inputs.get("branch_sel", "All") or "All")
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f"Unsupported HyPhy-PRIME branch selection: {branch_sel}"
        if branch_sel == "specify" and not str(inputs.get("branch_label", "")).strip():
            return "HyPhy-PRIME custom branch selection requires a branch label"
        prop_source_type = str(inputs.get("prop_source_type", "builtin") or "builtin")
        if prop_source_type not in cls.PROPERTY_SOURCE_TYPES:
            return f"Unsupported HyPhy-PRIME property source: {prop_source_type}"
        if prop_source_type == "custom":
            if not str(inputs.get("property_file", "")).strip():
                return "HyPhy-PRIME custom property source requires a property JSON file"
        else:
            prop_set = str(inputs.get("prop_set", "3PROP") or "3PROP")
            if prop_set not in cls.PROPERTY_SETS:
                return f"Unsupported HyPhy-PRIME property set: {prop_set}"
        message = cls._validate_float_range(
            inputs.get("p_value", 0.1), "HyPhy-PRIME p-value threshold must be between 0 and 1", 0, 1
        )
        if message:
            return message
        kill_zero_lengths = str(inputs.get("kill_zero_lengths", "Yes") or "Yes")
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f"Unsupported HyPhy-PRIME zero-length branch handling: {kill_zero_lengths}"
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "HyPhy-PRIME threads must be a positive integer"
        if threads < 1:
            return "HyPhy-PRIME threads must be a positive integer"
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
                        "description": "Branches to test for property-informed selection",
                    },
                ),
                "branch_label": (
                    "STRING",
                    {"default": "", "description": "Custom branch label when branch selection is specify"},
                ),
                "prop_source_type": (
                    "STRING",
                    {
                        "default": "builtin",
                        "options": cls.PROPERTY_SOURCE_TYPES,
                        "description": "Source of amino-acid property definitions",
                    },
                ),
                "prop_set": (
                    "STRING",
                    {
                        "default": "3PROP",
                        "options": cls.PROPERTY_SETS,
                        "description": "Built-in biochemical property set",
                    },
                ),
                "property_file": (
                    "JSON",
                    {"default": "", "description": "Custom amino-acid property JSON file"},
                ),
                "p_value": (
                    "FLOAT",
                    {"default": 0.1, "min": 0, "max": 1, "description": "P-value threshold"},
                ),
                "impute_states": (
                    "BOOLEAN",
                    {"default": False, "description": "Impute likely character states for each sequence"},
                ),
                "save_intermediate": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Save intermediate PRIME model fits as JSON",
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
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }
