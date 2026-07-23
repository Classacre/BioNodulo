"""Focused owner for ``hyphy_relax``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhyRELAXNode(ToolsIUCCommandContract):
    """Detect relaxed or intensified selection with HyPhy RELAX."""

    NODE_ID = "hyphy_relax"
    DISPLAY_NAME = "HyPhy-RELAX"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Detect relaxed or intensified selection in a codon-based phylogenetic framework with HyPhy RELAX."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "RELAX",
        "relaxed selection",
        "intensified selection",
        "selection intensity",
        "phylogenetic framework",
        "test branches",
        "reference branches",
        "group mode",
        "multiple alignments",
        "synonymous rate variation",
        "phylogenetics",
    ]
    RETURN_TYPES = ("JSON", "TEXT")
    RETURN_NAMES = ("relax_output", "relax_md_report")
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "http://hyphy.org/methods/selection-methods/#RELAX"
    CITATION_DOIS = HYPHY_RELAX_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_RELAX_CITATION_DOIS]
    CITATION_TEXT = HYPHY_RELAX_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    MULTIPLE_HITS = HyPhyABSRELNode.MULTIPLE_HITS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS
    INPUT_TYPES_OPTIONS = ["single", "multiple"]
    MODEL_OPTIONS = ["All", "Minimal"]
    MODE_OPTIONS = ["Classic mode", "Group mode"]
    SRV_OPTIONS = ["No", "Yes", "Branch-site", "HMM"]

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("input_ext", "fasta")).strip().lstrip(".") or "fasta"
        return f"input.{ext}"

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() in {"true", "yes", "1", "on"}
        return bool(value)

    @classmethod
    def _multiple_inputs(cls, inputs: dict[str, Any]) -> list[dict[str, str]]:
        raw = inputs.get("input_data_and_tree")
        if isinstance(raw, list):
            normalized = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                normalized.append(
                    {
                        "input_file": str(item.get("input_file", "")),
                        "input_ext": str(item.get("input_ext", item.get("ext", "fasta")) or "fasta").strip().lstrip("."),
                        "input_nhx": str(item.get("input_nhx", item.get("input_tree", "")) or ""),
                    }
                )
            return normalized

        input_files = _as_list(inputs.get("input_files"))
        input_exts = _as_list(inputs.get("input_exts"))
        input_trees = _as_list(inputs.get("input_trees"))
        normalized = []
        for index, input_file in enumerate(input_files):
            normalized.append(
                {
                    "input_file": input_file,
                    "input_ext": input_exts[index] if index < len(input_exts) else "fasta",
                    "input_nhx": input_trees[index] if index < len(input_trees) else "",
                }
            )
        return normalized

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands: list[str] = []
        cmd = ["hyphy", "relax"]
        input_type = str(inputs.get("input_type", "single") or "single")
        if input_type == "multiple":
            for index, input_data in enumerate(cls._multiple_inputs(inputs)):
                input_name = f"input_{index}.{input_data['input_ext']}"
                commands.append(_shell_join(["ln", "-s", input_data["input_file"], input_name]))
                if input_data["input_nhx"].strip():
                    commands.append(_shell_join(["ln", "-s", input_data["input_nhx"], f"input_{index}.nhx"]))
                commands.append(_shell_join(["echo", input_name, ">>", "filelist.txt"]))
            cmd.extend(["--multiple-files", "Yes", "--filelist", "filelist.txt"])
            for index, input_data in enumerate(cls._multiple_inputs(inputs)):
                if input_data["input_nhx"].strip():
                    cmd.extend(["--tree", f"input_{index}.nhx"])
        else:
            input_name = cls._input_name(inputs)
            if str(inputs.get("input_nhx", "")).strip():
                commands.append(_shell_join(["ln", "-s", str(inputs.get("input_nhx", "")), "input.nhx"]))
            commands.append(_shell_join(["ln", "-s", str(inputs.get("input_file", "")), input_name]))
            cmd.extend(["--alignment", input_name])
            if str(inputs.get("input_nhx", "")).strip():
                cmd.extend(["--tree", "input.nhx"])

        cmd.extend(
            [
                "--models",
                str(inputs.get("models", "All") or "All"),
                "--code",
                str(inputs.get("gencodeid", "Universal") or "Universal"),
                "--test",
                str(inputs.get("test", "Unlabeled branches") or "Unlabeled branches"),
            ]
        )
        if str(inputs.get("reference", "")).strip():
            cmd.extend(["--reference", str(inputs.get("reference", ""))])
        mode = str(inputs.get("mode", "Classic mode") or "Classic mode")
        cmd.extend(["--mode", mode])
        if mode == "Group mode" and str(inputs.get("reference_group", "")).strip():
            cmd.extend(["--reference-group", str(inputs.get("reference_group", ""))])
        cmd.extend(
            [
                "--grid-size",
                str(inputs.get("grid_size", 250)),
                "--starting-points",
                str(inputs.get("starting_points", 1)),
                "--syn-rates",
                str(inputs.get("syn_rates", 3)),
                "--rates",
                str(inputs.get("rates", 3)),
                "--srv",
                str(inputs.get("srv", "No") or "No"),
            ]
        )
        multiple_hits = str(inputs.get("multiple_hits", "None") or "None")
        if multiple_hits != "None":
            cmd.extend(["--multiple-hits", multiple_hits])
        cmd.extend(
            [
                "--kill-zero-lengths",
                str(inputs.get("kill_zero_lengths", "Yes") or "Yes"),
                "--output",
                f"{out}/relax_output.json",
                ">",
                f"{out}/relax_stdout.md",
            ]
        )
        threads = inputs.get("threads", 1)
        commands.append(f'export OMP_NUM_THREADS="${{GALAXY_SLOTS:-{threads}}}"')
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "relax_output.json", out / "relax_stdout.md"]

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def _validate_alignment_inputs(cls, inputs: dict[str, Any]) -> str | None:
        input_type = str(inputs.get("input_type", "single") or "single")
        if input_type == "single":
            if not str(inputs.get("input_file", "")).strip():
                return "HyPhy-RELAX alignment input is required"
            input_ext = str(inputs.get("input_ext", "fasta") or "fasta").strip().lstrip(".")
            if input_ext not in cls.INPUT_EXTENSIONS:
                return f"Unsupported HyPhy-RELAX input extension: {input_ext}"
            return None
        input_data_and_tree = cls._multiple_inputs(inputs)
        if not input_data_and_tree:
            return "HyPhy-RELAX multiple-input mode requires at least one alignment"
        for input_data in input_data_and_tree:
            if not input_data["input_file"].strip():
                return "HyPhy-RELAX multiple-input mode requires non-empty alignment files"
            input_ext = str(input_data["input_ext"] or "fasta").strip().lstrip(".")
            if input_ext not in cls.INPUT_EXTENSIONS:
                return f"Unsupported HyPhy-RELAX input extension: {input_ext}"
        return None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = str(inputs.get("input_type", "single") or "single")
        if input_type not in cls.INPUT_TYPES_OPTIONS:
            return f"Unsupported HyPhy-RELAX input type: {input_type}"
        message = cls._validate_alignment_inputs(inputs)
        if message:
            return message
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        models = str(inputs.get("models", "All") or "All")
        if models not in cls.MODEL_OPTIONS:
            return f"Unsupported HyPhy-RELAX analysis type: {models}"
        if not str(inputs.get("test", "Unlabeled branches") or "").strip():
            return "HyPhy-RELAX test branch label is required"
        mode = str(inputs.get("mode", "Classic mode") or "Classic mode")
        if mode not in cls.MODE_OPTIONS:
            return f"Unsupported HyPhy-RELAX run mode: {mode}"
        for key, default, low, high, label in [
            ("grid_size", 250, 1, 5000, "grid size"),
            ("starting_points", 1, 1, 1000, "starting points"),
            ("syn_rates", 3, 1, 10, "synonymous rate classes"),
            ("rates", 3, 2, 10, "non-synonymous rate classes"),
        ]:
            message = cls._validate_int_range(
                inputs.get(key, default), f"HyPhy-RELAX {label} must be between {low} and {high}", low, high
            )
            if message:
                return message
        srv = str(inputs.get("srv", "No") or "No")
        if srv not in cls.SRV_OPTIONS:
            return f"Unsupported HyPhy-RELAX synonymous rate variation setting: {srv}"
        multiple_hits = str(inputs.get("multiple_hits", "None") or "None")
        if multiple_hits not in cls.MULTIPLE_HITS:
            return f"Unsupported HyPhy-RELAX multiple-hits mode: {multiple_hits}"
        kill_zero_lengths = str(inputs.get("kill_zero_lengths", "Yes") or "Yes")
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f"Unsupported HyPhy-RELAX zero-length branch handling: {kill_zero_lengths}"
        try:
            threads = int(inputs.get("threads", 1))
        except (TypeError, ValueError):
            return "HyPhy-RELAX threads must be a positive integer"
        if threads < 1:
            return "HyPhy-RELAX threads must be a positive integer"
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
                "input_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": cls.INPUT_TYPES_OPTIONS,
                        "description": "Use a single alignment or multiple alignment/tree pairs",
                    },
                ),
                "input_nhx": ("FILE", {"default": "", "description": "Optional Newick/NHX phylogenetic tree"}),
                "input_ext": (
                    "STRING",
                    {"default": "fasta", "options": cls.INPUT_EXTENSIONS, "advanced": True},
                ),
                "input_data_and_tree": (
                    "JSON",
                    {
                        "default": [],
                        "description": "Galaxy repeat-style list of alignment/tree dictionaries for multiple mode",
                    },
                ),
                "input_files": (
                    "FILE",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Alignment files for multiple mode",
                    },
                ),
                "input_trees": (
                    "FILE",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Newick/NHX trees matching input_files",
                    },
                ),
                "input_exts": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.INPUT_EXTENSIONS,
                        "description": "File extensions matching input_files",
                    },
                ),
                "gencodeid": (
                    "STRING",
                    {
                        "default": "Universal",
                        "options": cls.GENETIC_CODES,
                        "description": "HyPhy genetic code for codon interpretation",
                    },
                ),
                "models": (
                    "STRING",
                    {
                        "default": "All",
                        "options": cls.MODEL_OPTIONS,
                        "description": "Fit all RELAX models or the faster minimal test",
                    },
                ),
                "test": (
                    "STRING",
                    {"default": "Unlabeled branches", "description": "Branch label used as the RELAX test set"},
                ),
                "reference": (
                    "STRING",
                    {"default": "", "description": "Optional branch label used as the RELAX reference set"},
                ),
                "mode": (
                    "STRING",
                    {
                        "default": "Classic mode",
                        "options": cls.MODE_OPTIONS,
                        "description": "RELAX classic test/reference mode or group comparison mode",
                    },
                ),
                "reference_group": (
                    "STRING",
                    {"default": "", "description": "Reference branch group for group mode"},
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
                "syn_rates": (
                    "INT",
                    {"default": 3, "min": 1, "max": 10, "description": "Synonymous rate classes"},
                ),
                "rates": (
                    "INT",
                    {"default": 3, "min": 2, "max": 10, "description": "Non-synonymous omega rate classes"},
                ),
                "srv": (
                    "STRING",
                    {
                        "default": "No",
                        "options": cls.SRV_OPTIONS,
                        "description": "Synonymous rate variation model",
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
                "kill_zero_lengths": (
                    "STRING",
                    {
                        "default": "Yes",
                        "options": cls.KILL_ZERO_LENGTHS,
                        "description": "Zero-length branch handling",
                        "advanced": True,
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }
