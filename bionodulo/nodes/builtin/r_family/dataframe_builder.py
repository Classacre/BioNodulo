"""Deterministic CSV builder used by R visualization templates."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


_PRODUCT_SOURCE_COMMIT = "827ffffc57530d60becfc66f190c35e79d2df7fc"
_PRODUCT_SOURCE_PATH = "bionodulo/nodes/builtin/r_family/dataframe_builder.py"


def _csv_values(value: Any) -> list[str]:
    rows = list(csv.reader([str(value)]))
    return [item.strip() for item in rows[0]] if rows else []


class DataFrameBuilderNode(BaseNode):
    """Build a rectangular CSV from two required columns and one optional group."""

    NODE_ID = "r_dataframe_builder"
    DISPLAY_NAME = "R DataFrame Builder"
    CATEGORY = "r"
    DESCRIPTION = "Build a strict rectangular CSV for downstream R plotting nodes."
    SEARCH_ALIASES = ["BioNodulo builtin", "R", "CSV", "data frame", "plot data"]
    RETURN_TYPES = ("CSV",)
    RETURN_NAMES = ("csv",)
    REQUIRES_EXTERNAL_TOOLS = False
    VERSION = "1.0.0"
    GIT_URL = "https://github.com/Classacre/BioNodulo.git"
    GIT_COMMIT = _PRODUCT_SOURCE_COMMIT
    PRODUCT_SOURCE_COMMIT = _PRODUCT_SOURCE_COMMIT
    PRODUCT_SOURCE_PATH = _PRODUCT_SOURCE_PATH
    PRODUCT_SOURCE_SYMBOL = "DataFrameBuilderNode"
    SOURCE_URL = (
        f"https://github.com/Classacre/BioNodulo/blob/{PRODUCT_SOURCE_COMMIT}/"
        f"{PRODUCT_SOURCE_PATH}"
    )
    UPSTREAM_SOURCE = f"{PRODUCT_SOURCE_PATH}:{PRODUCT_SOURCE_SYMBOL}"
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/csv.html"
    RUNTIME_DOCUMENTATION_URLS = (
        DOCUMENTATION_URL,
        "https://stat.ethz.ch/R-manual/R-devel/library/base/html/data.frame.html",
    )
    SOURCE_AUTHORITIES = {
        "product_contract": SOURCE_URL,
        "python_csv_runtime": RUNTIME_DOCUMENTATION_URLS[0],
        "r_downstream_data_frame": RUNTIME_DOCUMENTATION_URLS[1],
    }
    EXIT_SEMANTICS = (
        "This Python in-process node does not execute R and has no subprocess exit code; invalid "
        "column/value shapes and file I/O errors raise before a rectangular CSV is returned."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "x_column": ("STRING", {"default": "x"}),
                "x_values": ("STRING", {"default": "1,2,3,4,5", "multiline": True}),
                "y_column": ("STRING", {"default": "y"}),
                "y_values": ("STRING", {"default": "2,4,6,8,10", "multiline": True}),
            },
            "optional": {
                "group_column": ("STRING", {"default": "", "advanced": True}),
                "group_values": ("STRING", {"default": "", "multiline": True, "advanced": True}),
            },
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [Path(output_dir) / cls.NODE_ID / "data.csv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        x_column = str(inputs.get("x_column", "")).strip()
        y_column = str(inputs.get("y_column", "")).strip()
        if not x_column or not y_column:
            return "Inputs 'x_column' and 'y_column' must be non-empty"
        if x_column == y_column:
            return "Inputs 'x_column' and 'y_column' must be different"
        x_values = _csv_values(inputs.get("x_values", ""))
        y_values = _csv_values(inputs.get("y_values", ""))
        if not x_values or not y_values or any(value == "" for value in (*x_values, *y_values)):
            return "Inputs 'x_values' and 'y_values' must contain non-empty CSV values"
        if len(x_values) != len(y_values):
            return "Inputs 'x_values' and 'y_values' must contain the same number of values"
        group_column = str(inputs.get("group_column", "")).strip()
        group_values_raw = str(inputs.get("group_values", "") or "")
        group_values = _csv_values(group_values_raw) if group_values_raw else []
        if group_column and group_column in {x_column, y_column}:
            return "Input 'group_column' must be different from the X and Y column names"
        if bool(group_column) != bool(group_values):
            return "Inputs 'group_column' and 'group_values' must be provided together"
        if group_values and (any(value == "" for value in group_values) or len(group_values) != len(x_values)):
            return "Input 'group_values' must contain one non-empty value per X/Y row"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        output_dir = Path(getattr(context, "node_dir", ".") if context else kwargs.pop("output_dir", "."))
        output_path = self.PLAN_OUTPUTS(kwargs, output_dir)[0]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        x_column = str(kwargs["x_column"]).strip()
        y_column = str(kwargs["y_column"]).strip()
        x_values = _csv_values(kwargs["x_values"])
        y_values = _csv_values(kwargs["y_values"])
        group_column = str(kwargs.get("group_column", "")).strip()
        group_values = _csv_values(kwargs.get("group_values", "") or "") if group_column else []

        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([x_column, y_column, *([group_column] if group_column else [])])
            for index, (x_value, y_value) in enumerate(zip(x_values, y_values, strict=True)):
                row = [x_value, y_value]
                if group_column:
                    row.append(group_values[index])
                writer.writerow(row)
        return (str(output_path),)
