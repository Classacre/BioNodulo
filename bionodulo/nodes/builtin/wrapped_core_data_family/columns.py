"""Focused columns node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class AddInputNameAsColumnNode(CommandNode):
    """Add the input dataset name as an appended or prepended tabular column."""

    NODE_ID = "add_input_name_as_column"
    DISPLAY_NAME = "Add input name as column"
    REQUIRED_CONDA_PACKAGES = ["python"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Add the input dataset name as an appended or prepended tabular column."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Add input name as column",
        "add_input_name_as_column",
        "dataset collection labels",
        "history dataset name",
        "sample label column",
        "tabular label column",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = ADD_INPUT_NAME_AS_COLUMN_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [ADD_INPUT_NAME_AS_COLUMN_CITATION_URL]
    CITATION_TEXT = ADD_INPUT_NAME_AS_COLUMN_CITATION_TEXT
    VERSION = "0.3.0"
    SHELL = True

    HEADER_OPTIONS = ["yes", "no"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "add_input_name_as_column.py")),
            "--input",
            str(inputs.get("input", "")),
            "--label",
            str(inputs.get("label", "")),
            "--output",
            cls._output_path(inputs),
        ]
        if str(inputs.get("contains_header", "yes") or "yes") == "yes":
            cmd.extend(["--header", str(inputs.get("colname", "sample") or "sample")])
        if inputs.get("prepend"):
            cmd.append("--prepend")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not str(inputs.get("label", "")).strip():
            return "label is required"
        contains_header = str(inputs.get("contains_header", "yes") or "yes")
        if contains_header not in cls.HEADER_OPTIONS:
            return f"contains_header must be one of: {', '.join(cls.HEADER_OPTIONS)}"
        if contains_header == "yes" and not str(inputs.get("colname", "sample") or "").strip():
            return "colname is required when contains_header is yes"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TXT", {"description": "Text or tabular dataset to annotate with its input label"}),
                "label": ("STRING", {"description": "Dataset label to add, matching Galaxy's input element identifier"}),
            },
            "optional": {
                "contains_header": (
                    "STRING",
                    {
                        "default": "yes",
                        "options": cls.HEADER_OPTIONS,
                        "description": "Whether the first line should receive a column header instead of the dataset label",
                    },
                ),
                "colname": (
                    "STRING",
                    {"default": "sample", "description": "Column name added to the first line when the input has a header"},
                ),
                "prepend": (
                    "BOOLEAN",
                    {"default": False, "description": "Prepend the label column instead of appending it"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "add_input_name_as_column.py",
                        "advanced": True,
                        "description": "Path to the Galaxy add_input_name_as_column.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AddInputNameAsColumnGalaxyNode(AddInputNameAsColumnNode):
    """Galaxy wrapper-ID compatible alias for Add input name as column."""

    NODE_ID = "addName"
    DISPLAY_NAME = "Add input name as column (Galaxy)"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "addName",
        "Add input name as column",
        "add_input_name_as_column",
        "dataset collection labels",
        "history dataset name",
        "sample label column",
        "tabular label column",
    ]

class ColumnRemoveByHeaderNode(CommandNode):
    """Remove or keep tabular columns by matching header names."""

    NODE_ID = "column_remove_by_header"
    DISPLAY_NAME = "Remove columns"
    REQUIRED_CONDA_PACKAGES = ["python"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Remove or keep columns from a tabular file by matching header names."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "column_remove_by_header",
        "Remove columns",
        "remove columns by heading",
        "keep named columns",
        "header names",
        "tabular column filter",
        "unicode escaped columns",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output_tabular",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = COLUMN_REMOVE_BY_HEADER_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COLUMN_REMOVE_BY_HEADER_CITATION_URL]
    CITATION_TEXT = COLUMN_REMOVE_BY_HEADER_CITATION_TEXT
    VERSION = "1.0"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_tabular.tsv"

    @classmethod
    def _headers(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get("headers")
        if isinstance(raw, str):
            return [header.strip() for header in raw.split(",") if header.strip()]
        return _as_list(raw)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "column_remove_by_header.py") or "column_remove_by_header.py"),
            "-i",
            str(inputs.get("input_tabular", "")),
            "-o",
            cls._output_path(inputs),
            "-d",
            str(inputs.get("delimiter", "\\t") or "\\t"),
        ]
        if inputs.get("keep_columns"):
            cmd.append("--keep")
        cmd.extend(
            [
                "-s",
                str(inputs.get("strip_characters", "#")),
                "--unicode-escaped-cols",
                "--columns",
                *cls._headers(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output_tabular.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_tabular", "")).strip():
            return "input_tabular is required"
        if not cls._headers(inputs):
            return "at least one header is required"
        delimiter = str(inputs.get("delimiter", "\\t"))
        if delimiter == "":
            return "delimiter is required"
        try:
            delimiter.encode("ascii")
        except UnicodeEncodeError:
            return "delimiter must contain only ASCII characters"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_tabular": ("TSV", {"description": "Tabular file with a header row"}),
                "headers": (
                    "STRING",
                    {
                        "is_list": True,
                        "description": "Header names to remove, or to keep when keep_columns is enabled",
                    },
                ),
            },
            "optional": {
                "keep_columns": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Keep named columns and drop all other columns",
                    },
                ),
                "strip_characters": (
                    "STRING",
                    {
                        "default": "#",
                        "description": "Leading characters to strip from the first header before comparison",
                    },
                ),
                "delimiter": ("STRING", {"default": "\\t", "description": "ASCII field delimiter"}),
                "script_path": (
                    "FILE",
                    {
                        "default": "column_remove_by_header.py",
                        "advanced": True,
                        "description": "Path to the Galaxy column_remove_by_header.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ColumnOrderHeaderSortNode(CommandNode):
    """Sort tabular columns by header while optionally preserving an identifier column."""

    NODE_ID = "column_order_header_sort"
    DISPLAY_NAME = "Sort Column Order"
    REQUIRED_CONDA_PACKAGES = ["python", "gawk"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Reorder tabular columns by sorted header values, with an optional identifier column first."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "column_order_header_sort",
        "Sort Column Order",
        "sort column order",
        "sorted header fields",
        "identifier column",
        "tabular column sort",
        "column order by heading",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output_tabular",)
    REQUIRED_EXECUTABLES = ["python", "gawk"]
    DOCUMENTATION_URL = COLUMN_ORDER_HEADER_SORT_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COLUMN_ORDER_HEADER_SORT_CITATION_URL]
    CITATION_TEXT = COLUMN_ORDER_HEADER_SORT_CITATION_TEXT
    VERSION = "0.0.1"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_tabular.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "column_order_header_sort.py") or "column_order_header_sort.py"),
            str(inputs.get("input_tabular", "")),
            cls._output_path(inputs),
            str(inputs.get("delimiter", "\\t") or "\\t"),
            str(inputs.get("key_column", 0)),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output_tabular.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_tabular", "")).strip():
            return "input_tabular is required"
        try:
            key_column = int(inputs.get("key_column", 0))
        except (TypeError, ValueError):
            return "key_column must be an integer"
        if key_column < 0:
            return "key_column must be greater than or equal to 0"
        delimiter = str(inputs.get("delimiter", "\\t"))
        if delimiter == "":
            return "delimiter is required"
        try:
            delimiter.encode("ascii")
        except UnicodeEncodeError:
            return "delimiter must contain only ASCII characters"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_tabular": ("TSV", {"description": "Tabular file with unique header values"}),
            },
            "optional": {
                "key_column": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "description": "Optional 1-based identifier column to keep leftmost; 0 disables it",
                    },
                ),
                "delimiter": ("STRING", {"default": "\\t", "description": "ASCII field delimiter"}),
                "script_path": (
                    "FILE",
                    {
                        "default": "column_order_header_sort.py",
                        "advanced": True,
                        "description": "Path to the Galaxy column_order_header_sort.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(AddInputNameAsColumnNode)
pin_contract(AddInputNameAsColumnGalaxyNode)
pin_contract(ColumnRemoveByHeaderNode)
pin_contract(ColumnOrderHeaderSortNode)

__all__ = ['AddInputNameAsColumnNode', 'AddInputNameAsColumnGalaxyNode', 'ColumnRemoveByHeaderNode', 'ColumnOrderHeaderSortNode']
