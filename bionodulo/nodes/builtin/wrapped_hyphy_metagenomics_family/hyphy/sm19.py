"""Focused owner for ``hyphy_sm19``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from ..contracts import ToolsIUCCommandContract

class HyPhySM2019Node(ToolsIUCCommandContract):
    """Partition trees using the modified Slatkin-Maddison test."""

    NODE_ID = "hyphy_sm19"
    DISPLAY_NAME = "HyPhy-SM2019"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Partition trees using the modified Slatkin-Maddison test with HyPhy SM2019."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "SM2019",
        "SM19",
        "Structured Slatkin-Maddison",
        "Modified Slatkin-Maddison Test",
        "population segregation",
        "gene flow",
        "migration events",
        "compartmentalization",
        "phylogenetics",
    ]
    RETURN_TYPES = ("JSON", "TEXT")
    RETURN_NAMES = ("sm19_output", "sm19_md_report")
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "https://github.com/veg/hyphy-analyses/tree/master/SlatkinMaddison"
    CITATION_DOIS = HYPHY_SM19_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_SM19_CITATION_DOIS]
    CITATION_TEXT = HYPHY_SM19_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    DEFAULT_PARTITIONS = [
        {"label": "Partition 1", "regex": "P1[0-9]+"},
        {"label": "Partition 2", "regex": "P2[0-9]+"},
    ]

    @classmethod
    def _partitions(cls, inputs: dict[str, Any]) -> list[dict[str, str]]:
        raw_partitions = inputs.get("partitions", cls.DEFAULT_PARTITIONS)
        if not isinstance(raw_partitions, (list, tuple)):
            return []
        partitions: list[dict[str, str]] = []
        for partition in raw_partitions:
            if not isinstance(partition, dict):
                return []
            partitions.append(
                {
                    "label": str(partition.get("label", "")).strip(),
                    "regex": str(partition.get("regex", "")).strip(),
                }
            )
        return partitions

    @classmethod
    def _yes_no(cls, value: Any) -> str:
        if isinstance(value, str):
            return "Yes" if value.lower() in {"true", "yes", "1", "on"} else "No"
        return "Yes" if bool(value) else "No"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        partitions = cls._partitions(inputs)
        commands = [_shell_join(["ln", "-s", str(inputs.get("input_file", "")), "sm19_input.nhx"])]
        cmd = [
            "hyphy",
            f"CPU={inputs.get('threads', 4)}",
            "sm",
            "--tree",
            "./sm19_input.nhx",
            "--groups",
            str(len(partitions)),
        ]
        for index, partition in enumerate(partitions, start=1):
            cmd.extend([f"--description-{index}", partition["label"], f"--regexp-{index}", partition["regex"]])
        cmd.extend(
            [
                "--replicates",
                str(inputs.get("replicates", 100)),
                "--weight",
                str(inputs.get("weight", 0.2)),
                "--use-bootstrap",
                cls._yes_no(inputs.get("use_bootstrap", True)),
                "--output",
                f"{out}/sm19_output.json",
                ">",
                f"{out}/sm19_stdout.md",
            ]
        )
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "sm19_output.json", out / "sm19_stdout.md"]

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

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
            return "HyPhy-SM2019 input tree is required"
        partitions = cls._partitions(inputs)
        if len(partitions) < 2 or len(partitions) > 50:
            return "HyPhy-SM2019 requires between 2 and 50 partitions"
        if any(not partition["label"] or not partition["regex"] for partition in partitions):
            return "HyPhy-SM2019 partition labels and regular expressions are required"
        message = cls._validate_int_range(
            inputs.get("replicates", 100),
            "HyPhy-SM2019 bootstrap replicates must be between 1 and 1000000",
            1,
            1000000,
        )
        if message:
            return message
        message = cls._validate_unit_float(
            inputs.get("weight", 0.2), "HyPhy-SM2019 structured permutation weight must be between 0 and 1"
        )
        if message:
            return message
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "HyPhy-SM2019 threads must be a positive integer"
        if threads < 1:
            return "HyPhy-SM2019 threads must be a positive integer"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "PHYLOGENY_TREE",
                    {
                        "description": (
                            "Newick, NHX, or NEXUS tree whose leaf names can be partitioned by regular expression"
                        )
                    },
                ),
                "partitions": (
                    "JSON",
                    {
                        "default": cls.DEFAULT_PARTITIONS,
                        "min_items": 2,
                        "max_items": 50,
                        "description": "List of partition objects with label and regex fields",
                    },
                ),
            },
            "optional": {
                "replicates": (
                    "INT",
                    {"default": 100, "min": 1, "max": 1000000, "description": "Number of bootstrap replicates"},
                ),
                "weight": (
                    "FLOAT",
                    {
                        "default": 0.2,
                        "min": 0,
                        "max": 1,
                        "description": "Probability of branch selection for structured permutation",
                    },
                ),
                "use_bootstrap": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Use bootstrap weights to respect well supported clades",
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }
