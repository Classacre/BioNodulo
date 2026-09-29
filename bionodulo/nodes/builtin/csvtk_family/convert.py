"""csvtk convert node: one conversion operation with a target-format choice.

This deliberately replaces seven near-identical nodes (``csv2tab``, ``tab2csv``,
``csv2json``, ``csv2md``, ``csv2rst``, ``csv2xlsx``) with one node plus a dropdown.
Those seven are not seven operations: they are one operation — re-encode a
delimited table — with six output encodings. They share their ports, their
semantics and their failure modes, and they differ only in the target format.

The repository already models conversion this way: the builtin ``format_converter``
node converts between CSV, TSV and JSON with ``input_format``/``output_format``
dropdowns rather than one node per pair. This follows that precedent.

Everything else in the csvtk family stays a separate node, because those operations
do genuinely different work (``join`` combines two tables, ``sort`` orders rows,
``split`` writes many files) and collapsing them would hide the operation from the
canvas.

Semantics were established by running the tool, not by reading its documentation:
the subcommand is chosen by the TARGET format and the inherited ``-t`` flag handles
tab-delimited input, so ``csv2tab -t`` correctly re-emits a tab file as tab.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase

# target format -> (csvtk subcommand, output file extension)
CONVERSIONS: dict[str, tuple[str, str]] = {
    "tab": ("csv2tab", "tsv"),
    "comma": ("tab2csv", "csv"),
    "json": ("csv2json", "json"),
    "markdown": ("csv2md", "md"),
    "rst": ("csv2rst", "rst"),
    "xlsx": ("csv2xlsx", "xlsx"),
}
# Declared as an explicit literal so scripts/generate_subcommand_nodes.py can read
# it by pattern and know these subcommands are already represented.
COVERS_SUBCOMMANDS: tuple[str, ...] = (
    "csv2tab",
    "tab2csv",
    "csv2json",
    "csv2md",
    "csv2rst",
    "csv2xlsx",
)


class CsvtkConvertNode(CsvtkBase):
    """Re-encode a delimited table into another text or spreadsheet format."""

    NODE_ID = "csvtk_convert"
    DISPLAY_NAME = "csvtk Convert"
    DESCRIPTION = (
        "Re-encode a CSV/TSV table as tab, comma, JSON, Markdown, reStructuredText, "
        "or an Excel workbook"
    )
    SEARCH_ALIASES = [
        "csvtk", "convert", "csv2json", "csv2tab", "tab2csv", "csv2md",
        "csv2rst", "csv2xlsx", "to json", "to markdown", "to excel",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("converted",)
    OUTPUT_FILENAMES = ("converted.tsv",)
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/csvtk/usage/"

    @classmethod
    def output_name(cls, inputs: dict[str, Any]) -> str:
        target = str(inputs.get("to", "tab") or "tab")
        extension = CONVERSIONS.get(target, CONVERSIONS["tab"])[1]
        return f"converted.{extension}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": (
                    ("CSV", "TSV", "FILE"),
                    {"description": "Input delimited text file"},
                ),
                "to": (
                    "STRING",
                    {
                        "default": "tab",
                        "options": list(CONVERSIONS),
                        "description": "Target format",
                    },
                ),
            },
            "optional": {
                "delimiter": (
                    "STRING",
                    {"default": "tab", "options": ["tab", "comma"],
                     "description": "Delimiter of the input file"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        target = str(inputs.get("to", "tab") or "tab")
        if target not in CONVERSIONS:
            return f"Input 'to' must be one of: {', '.join(CONVERSIONS)}"
        # csvtk has no comma-to-comma converter: ``tab2csv`` reads tab by design.
        if target == "comma" and str(inputs.get("delimiter", "tab") or "tab") != "tab":
            return "Converting to comma requires a tab-delimited input (csvtk has no csv2csv)"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        target = str(inputs.get("to", "tab") or "tab")
        subcommand, _extension = CONVERSIONS[target]
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ["csvtk", subcommand, *cls.delimiter_flags(inputs)]
        command.extend(["-o", str(output_dir / cls.output_name(inputs))])
        command.append(str(inputs.get("table", "")))
        return command
