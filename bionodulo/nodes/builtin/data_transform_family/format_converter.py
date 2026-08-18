"""Pure Python CSV, TSV, and JSON record conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    TABLE_FORMATS,
    PythonDataTransformNode,
    node_output_dir,
    normalize_table_format,
    path_value,
    read_records,
    safe_output_stem,
    validate_choice,
    write_records,
)


class FormatConverterNode(PythonDataTransformNode):
    """Convert record-oriented files between CSV, TSV, and JSON."""

    NODE_ID = "format_converter"
    DISPLAY_NAME = "Format Converter"
    DESCRIPTION = "Convert record-oriented files between CSV, TSV, and JSON without external tools."
    SEARCH_ALIASES = ["format", "convert", "converter", "csv", "tsv", "json", "table"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("converted_file",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/csv.html"
    UPSTREAM_SOURCE = "Lib/csv.py; Lib/json"
    PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
    EXIT_SEMANTICS = (
        "Missing files, unknown formats, malformed CSV/TSV, non-record JSON, and headerless record output are "
        "fatal; the node never invokes samtools, bcftools, gffread, seqtk, or a shell."
    )
    EXTENSIONS = {"csv": ".csv", "tsv": ".tsv", "json": ".json", "jsonl": ".jsonl"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FILE", {"description": "CSV, TSV, or JSON records file"}),
                "output_format": (list(TABLE_FORMATS), {"default": "tsv"}),
            },
            "optional": {
                "input_format": (["auto", *TABLE_FORMATS], {"default": "auto"}),
                "output_name": ("STRING", {"default": "", "description": "Output filename stem"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not path_value(inputs.get("input_file")):
            return "Input 'input_file' must be a non-empty path-like value"
        validation = validate_choice(inputs.get("output_format", "tsv"), "output_format", TABLE_FORMATS)
        if validation is not True:
            return validation
        return validate_choice(
            inputs.get("input_format", "auto"),
            "input_format",
            ("auto", *TABLE_FORMATS),
        )

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        input_file = Path(path_value(kwargs["input_file"])).expanduser()
        input_format = normalize_table_format(kwargs.get("input_format", "auto"), input_file)
        output_format = normalize_table_format(kwargs.get("output_format", "tsv"))
        fieldnames, records = read_records(input_file, input_format)
        requested_name = str(kwargs.get("output_name", "") or "").strip()
        stem = safe_output_stem(requested_name or input_file.stem, fallback=self.NODE_ID)
        output_path = node_output_dir(self, context) / f"{stem}{self.EXTENSIONS[output_format]}"
        write_records(output_path, output_format, fieldnames, records)
        return (str(output_path),)
