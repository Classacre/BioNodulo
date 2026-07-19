"""Focused owner for ``merge_metaphlan_tables``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from ..contracts import ToolsIUCCommandContract

class MergeMetaPhlAnTablesNode(ToolsIUCCommandContract):
    """Merge multiple MetaPhlAn relative abundance tables."""

    NODE_ID = "merge_metaphlan_tables"
    DISPLAY_NAME = "Merge MetaPhlAn Tables"
    REQUIRED_CONDA_PACKAGES = ["metaphlan"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Join one or more MetaPhlAn predicted taxon relative abundance tables into a merged sample-by-clade table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "MetaPhlAn",
        "merge_metaphlan_tables.py",
        "relative abundance",
        "abundance tables",
        "GTDB profiles",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("merged_abundance_table",)
    REQUIRED_EXECUTABLES = ["merge_metaphlan_tables.py"]
    DOCUMENTATION_URL = "https://github.com/biobakery/MetaPhlAn"
    CITATION_DOIS = [METAPHLAN_DOI]
    CITATION_URLS = [f"{DOI_URL}{METAPHLAN_DOI}"]
    CITATION_TEXT = METAPHLAN_CITATION_TEXT
    VERSION = "4.2.4"
    SHELL = True

    @classmethod
    def _input_names(cls, inputs: dict[str, Any], abundance_tables: list[str]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        for index, abundance_table in enumerate(abundance_tables):
            label = labels[index] if index < len(labels) and labels[index] else abundance_table
            names.append(_safe_identifier(label))
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        abundance_tables = _as_list(inputs.get("abundance_tables", inputs.get("inputs")))
        input_names = cls._input_names(inputs, abundance_tables)
        commands = [
            f"ln -s {shlex.quote(abundance_table)} {shlex.quote(input_name)}"
            for abundance_table, input_name in zip(abundance_tables, input_names, strict=False)
        ]
        cmd = ["merge_metaphlan_tables.py"]
        if inputs.get("gtdb_profiles", False):
            cmd.append("--gtdb_profiles")
        cmd.extend(input_names)
        _add_shell_redirect(cmd, f"{out}/merged_metaphlan_tables.tsv")
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "merged_metaphlan_tables.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        abundance_tables = _as_list(inputs.get("abundance_tables", inputs.get("inputs")))
        if not abundance_tables or any(not str(path).strip() for path in abundance_tables):
            return "At least one MetaPhlAn abundance table is required"
        labels = _as_list(inputs.get("element_identifiers"))
        if labels and len(labels) != len(abundance_tables):
            return "element_identifiers must match the number of abundance tables"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "abundance_tables": (
                    "TSV",
                    {"multiple": True, "description": "One or more MetaPhlAn predicted taxon relative abundance tables"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional sample labels used to name symlinked inputs before merging",
                    },
                ),
                "gtdb_profiles": (
                    "BOOLEAN",
                    {"default": False, "description": "Merge GTDB-based MetaPhlAn profiles using semicolon-separated clades"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
