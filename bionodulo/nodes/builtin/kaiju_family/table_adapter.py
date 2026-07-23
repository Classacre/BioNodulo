"""Shared Kaiju table contract for its focused owner."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from .adapter import (
    KaijuContractNode,
    _KaijuContract,
)


class _Kaiju2TableContract(KaijuContractNode):
    """Summarize Kaiju classifications by taxonomic rank."""

    LEGACY_NODE_ID = "kaiju2table"
    DISPLAY_NAME = "Kaiju2Table"
    REQUIRED_CONDA_PACKAGES = ["kaiju"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert one or more Kaiju classification outputs into summary tables by taxonomic rank."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "kaiju",
        "kaiju2table",
        "summary table",
        "minimum reporting percentage",
        "taxonomic rank",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("summary_table",)
    REQUIRED_EXECUTABLES = ["kaiju2table"]
    DOCUMENTATION_URL = _KaijuContract.DOCUMENTATION_URL
    CITATION_DOIS = _KaijuContract.CITATION_DOIS
    CITATION_URLS = _KaijuContract.CITATION_URLS
    CITATION_TEXT = _KaijuContract.CITATION_TEXT
    VERSION = _KaijuContract.VERSION
    SHELL = True

    @classmethod
    def _linked_names(cls, inputs: dict[str, Any], tables: list[str]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        for index, table in enumerate(tables):
            label = labels[index] if index < len(labels) and labels[index] else table
            names.append(_safe_identifier(label))
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        tables = _as_list(inputs.get("kaiju_tables"))
        linked_names = cls._linked_names(inputs, tables)
        commands = [
            f"ln -sf {shlex.quote(table)} {shlex.quote(linked_name)}"
            for table, linked_name in zip(tables, linked_names, strict=False)
        ]

        reference = str(inputs.get("reference_database", "")).rstrip("/")
        cmd = [
            "kaiju2table",
            "-t",
            f"{reference}/nodes.dmp",
            "-n",
            f"{reference}/names.dmp",
            "-r",
            str(inputs.get("rank", "phylum")),
            "-o",
            f"{out}/kaiju_summary.tsv",
        ]
        _add_if_value(cmd, "-m", inputs.get("minimum_percentage"))
        _add_if_value(cmd, "-c", inputs.get("minimum_reads"))
        if inputs.get("expand_viruses", False):
            cmd.append("-e")
        if inputs.get("exclude_unclassified", False):
            cmd.append("-u")

        tax_path_report = str(inputs.get("tax_path_report", ""))
        if tax_path_report == "full":
            cmd.append("-p")
        elif tax_path_report == "partial":
            selected_ranks = ",".join(_as_list(inputs.get("selected_ranks")))
            if selected_ranks:
                cmd.extend(["-l", selected_ranks])

        cmd.extend(linked_names)
        commands.append(shlex.join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "kaiju_summary.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "kaiju_tables": (
                    "TSV",
                    {"multiple": True, "description": "One or more Kaiju output tables"},
                ),
                "reference_database": (
                    "DIRECTORY",
                    {"description": "Kaiju database directory containing nodes.dmp and names.dmp"},
                ),
                "rank": (
                    "STRING",
                    {
                        "default": "phylum",
                        "options": ["phylum", "class", "order", "family", "genus", "species"],
                        "description": "Taxonomic rank to summarize",
                    },
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional sample labels matching the input table order",
                    },
                ),
                "minimum_percentage": (
                    "FLOAT",
                    {
                        "default": "",
                        "min": 0,
                        "max": 100,
                        "description": "Minimum reporting percentage; cannot be combined with minimum_reads",
                    },
                ),
                "minimum_reads": (
                    "INT",
                    {
                        "default": "",
                        "min": 1,
                        "description": "Minimum required number of reads; cannot be combined with minimum_percentage",
                    },
                ),
                "expand_viruses": (
                    "BOOLEAN",
                    {"default": False, "description": "Always show viruses as full taxon paths"},
                ),
                "exclude_unclassified": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not count unclassified reads in percentage totals"},
                ),
                "tax_path_report": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "full", "partial"],
                        "description": "Report full or selected taxonomic paths instead of only the selected rank",
                    },
                ),
                "selected_ranks": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Ranks included when tax_path_report is partial",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
