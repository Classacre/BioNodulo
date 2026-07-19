"""Focused owner for ``hyphy_absrel``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from ..contracts import ToolsIUCCommandContract

class HyPhyABSRELNode(ToolsIUCCommandContract):
    """Detect episodic diversifying selection with HyPhy aBSREL."""

    NODE_ID = "hyphy_absrel"
    DISPLAY_NAME = "HyPhy-aBSREL"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Detect episodic diversifying selection with adaptive Branch-Site Random Effects Likelihood."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "aBSREL",
        "adaptive branch-site random effects likelihood",
        "episodic diversifying selection",
        "selection",
        "phylogenetics",
    ]
    RETURN_TYPES = ("TEXT", "JSON")
    RETURN_NAMES = ("absrel_md_report", "absrel_output")
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "http://www.hyphy.org/methods/selection-methods/#absrel"
    CITATION_DOIS = HYPHY_ABSREL_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_ABSREL_CITATION_DOIS]
    CITATION_TEXT = HYPHY_ABSREL_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = [
        "Universal",
        "Vertebrate-mtDNA",
        "Yeast-mtDNA",
        "Mold-Protozoan-mtDNA",
        "Invertebrate-mtDNA",
        "Ciliate-Nuclear",
        "Echinoderm-mtDNA",
        "Euplotid-Nuclear",
        "Alt-Yeast-Nuclear",
        "Ascidian-mtDNA",
        "Flatworm-mtDNA",
        "Blepharisma-Nuclear",
        "Chlorophycean-mtDNA",
        "Trematode-mtDNA",
        "Scenedesmus-obliquus-mtDNA",
        "Thraustochytrium-mtDNA",
        "Pterobranchia-mtDNA",
        "SR1-and-Gracilibacteria",
        "Pachysolen-Nuclear",
        "Mesodinium-Nuclear",
        "Peritrich-Nuclear",
        "Cephalodiscidae-mtDNA",
    ]
    BRANCH_SELECTIONS = ["All", "Internal", "Leaves", "Unlabeled-branches", "specify"]
    MULTIPLE_HITS = ["None", "Double", "Double+Triple"]
    KILL_ZERO_LENGTHS = ["Yes", "Constrain", "No"]
    INPUT_EXTENSIONS = ["fasta", "fasta.gz", "nex"]

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
    def _srv_enabled(cls, inputs: dict[str, Any]) -> bool:
        value = inputs.get("srv_enabled", True)
        if isinstance(value, str):
            return value.lower() in {"true", "yes", "1", "on"}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get("input_nhx", "")).strip():
            commands.append(_shell_join(["ln", "-s", str(inputs.get("input_nhx", "")), "input.nhx"]))
        commands.append(_shell_join(["ln", "-s", str(inputs.get("input_file", "")), input_name]))
        commands.append(_shell_join(["ln", "-s", f"{out}/absrel_output.json", f"{input_name}.aBSREL.json"]))

        cmd = [
            "hyphy",
            f"CPU={inputs.get('threads', 4)}",
            "absrel",
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
                "--output",
                f"{out}/absrel_output.json",
                "--multiple-hits",
                str(inputs.get("multiple_hits", "None") or "None"),
            ]
        )
        if cls._srv_enabled(inputs):
            cmd.extend(["--srv", "Yes", "--syn-rates", str(inputs.get("syn_rates", 3))])
        cmd.extend(
            [
                "--blb",
                str(inputs.get("blb", 1.0)),
                "--kill-zero-lengths",
                str(inputs.get("kill_zero_lengths", "Yes") or "Yes"),
                ">",
                f"{out}/absrel_stdout.md",
            ]
        )
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "absrel_stdout.md", out / "absrel_output.json"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-aBSREL alignment input is required"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        branch_sel = str(inputs.get("branch_sel", "All") or "All")
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f"Unsupported HyPhy-aBSREL branch selection: {branch_sel}"
        if branch_sel == "specify" and not str(inputs.get("branch_label", "")).strip():
            return "HyPhy-aBSREL custom branch selection requires a branch label"
        multiple_hits = str(inputs.get("multiple_hits", "None") or "None")
        if multiple_hits not in cls.MULTIPLE_HITS:
            return f"Unsupported HyPhy-aBSREL multiple-hits mode: {multiple_hits}"
        if cls._srv_enabled(inputs):
            try:
                syn_rates = int(inputs.get("syn_rates", 3))
            except (TypeError, ValueError):
                return "HyPhy-aBSREL synonymous rate classes must be between 1 and 10"
            if syn_rates < 1 or syn_rates > 10:
                return "HyPhy-aBSREL synonymous rate classes must be between 1 and 10"
        kill_zero_lengths = str(inputs.get("kill_zero_lengths", "Yes") or "Yes")
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f"Unsupported HyPhy-aBSREL zero-length branch handling: {kill_zero_lengths}"
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "HyPhy-aBSREL threads must be a positive integer"
        if threads < 1:
            return "HyPhy-aBSREL threads must be a positive integer"
        try:
            blb = float(inputs.get("blb", 1.0))
        except (TypeError, ValueError):
            return "HyPhy-aBSREL BLB resampling value must be non-negative"
        if blb < 0:
            return "HyPhy-aBSREL BLB resampling value must be non-negative"
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
                "multiple_hits": (
                    "STRING",
                    {
                        "default": "None",
                        "options": cls.MULTIPLE_HITS,
                        "description": "Multiple-hit correction mode",
                        "advanced": True,
                    },
                ),
                "blb": (
                    "FLOAT",
                    {"default": 1.0, "min": 0, "description": "Bag of little bootstrap resampling rate"},
                ),
                "srv_enabled": (
                    "BOOLEAN",
                    {"default": True, "description": "Enable synonymous rate variation modelling"},
                ),
                "syn_rates": (
                    "INT",
                    {"default": 3, "min": 1, "max": 10, "description": "Synonymous rate classes"},
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
