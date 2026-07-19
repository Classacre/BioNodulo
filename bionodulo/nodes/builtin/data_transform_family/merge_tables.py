"""Single-key and cross joins for strict CSV/TSV tables."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .adapter import (
    DELIMITER_MODES,
    OUTPUT_TYPES,
    PythonDataTransformNode,
    delimiter_for,
    node_output_dir,
    output_delimiter_and_extension,
    path_value,
    read_table,
    validate_choice,
    write_table,
)


MERGE_JOIN_TYPES = ("inner", "left", "right", "outer", "cross")


class MergeTablesNode(PythonDataTransformNode):
    """Join two tables by one shared or mapped key, or form a cross product."""

    NODE_ID = "merge_tables"
    DISPLAY_NAME = "Merge Tables"
    DESCRIPTION = "Join two CSV/TSV tables by one shared or mapped key, including cross joins."
    SEARCH_ALIASES = [
        "merge",
        "join",
        "table",
        "left join",
        "right join",
        "outer join",
        "cross join",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("merged_table",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/csv.html"
    UPSTREAM_SOURCE = "Lib/csv.py; ordered dict insertion semantics"
    PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
    EXIT_SEMANTICS = (
        "Missing files, malformed tables, absent keys, invalid join modes, and output-name collisions are fatal; "
        "many-to-many keys emit the deterministic Cartesian set of matching rows."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table_a": ("FILE", {"description": "Left CSV/TSV table"}),
                "table_b": ("FILE", {"description": "Right CSV/TSV table"}),
            },
            "optional": {
                "join_key": (
                    "STRING",
                    {"default": "", "description": "Shared key; empty auto-detects the first common column"},
                ),
                "key_column_a": ("STRING", {"default": "", "description": "Mapped key in table A"}),
                "key_column_b": ("STRING", {"default": "", "description": "Mapped key in table B"}),
                "join_type": (list(MERGE_JOIN_TYPES), {"default": "inner"}),
                "delimiter": (list(DELIMITER_MODES), {"default": "auto"}),
                "suffix_a": ("STRING", {"default": "_a", "advanced": True}),
                "suffix_b": ("STRING", {"default": "_b", "advanced": True}),
                "right_suffix": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Backward-compatible suffix_b alias"},
                ),
                "output_type": (list(OUTPUT_TYPES), {"default": "AUTO"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("table_a", "table_b"):
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        validation = validate_choice(inputs.get("join_type", "inner"), "join_type", MERGE_JOIN_TYPES)
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("delimiter", "auto"), "delimiter", DELIMITER_MODES)
        if validation is not True:
            return validation
        return validate_choice(inputs.get("output_type", "AUTO"), "output_type", OUTPUT_TYPES)

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        table_a = Path(path_value(kwargs["table_a"])).expanduser()
        table_b = Path(path_value(kwargs["table_b"])).expanduser()
        delimiter_mode = kwargs.get("delimiter", "auto")
        fields_a, rows_a = read_table(table_a, delimiter_for(delimiter_mode, table_a))
        fields_b, rows_b = read_table(table_b, delimiter_for(delimiter_mode, table_b))
        join_type = str(kwargs.get("join_type", "inner"))
        key_a, key_b = ("", "") if join_type == "cross" else self.resolve_join_keys(kwargs, fields_a, fields_b)
        suffix_a = str(kwargs.get("suffix_a", "_a"))
        compatibility_suffix = str(kwargs.get("right_suffix", "") or "")
        suffix_b = compatibility_suffix or str(kwargs.get("suffix_b", "_b"))
        left_names, right_names = self.output_name_maps(fields_a, fields_b, key_a, key_b, suffix_a, suffix_b)
        output_fields = [*left_names.values(), *right_names.values()]
        if len(output_fields) != len(set(output_fields)):
            raise ValueError("Join suffixes produce duplicate output column names")

        if join_type == "cross":
            output_rows = [self.combine(left, right, left_names, right_names) for left in rows_a for right in rows_b]
        else:
            output_rows = self.join_rows(
                rows_a,
                rows_b,
                fields_a,
                key_a,
                key_b,
                join_type,
                left_names,
                right_names,
            )

        output_delimiter, extension = output_delimiter_and_extension(
            kwargs.get("output_type", "AUTO"), table_a, table_b
        )
        output_path = node_output_dir(self, context) / f"{table_a.stem}.merged{extension}"
        write_table(output_path, output_fields, output_rows, output_delimiter)
        return (str(output_path),)

    @staticmethod
    def resolve_join_keys(inputs: dict[str, Any], fields_a: list[str], fields_b: list[str]) -> tuple[str, str]:
        shared = str(inputs.get("join_key", "") or "").strip()
        key_a = str(inputs.get("key_column_a", "") or "").strip() or shared
        key_b = str(inputs.get("key_column_b", "") or "").strip() or shared or key_a
        if not key_a and not key_b:
            common = [field for field in fields_a if field in fields_b]
            if not common:
                raise ValueError("No common columns found; specify join_key or mapped key columns")
            key_a = key_b = common[0]
        elif key_a and not key_b:
            key_b = key_a
        elif key_b and not key_a:
            key_a = key_b
        if key_a not in fields_a:
            raise ValueError(f"Key column {key_a!r} must exist in table A")
        if key_b not in fields_b:
            raise ValueError(f"Key column {key_b!r} must exist in table B")
        return key_a, key_b

    @staticmethod
    def output_name_maps(
        fields_a: list[str],
        fields_b: list[str],
        key_a: str,
        key_b: str,
        suffix_a: str,
        suffix_b: str,
    ) -> tuple[OrderedDict[str, str], OrderedDict[str, str]]:
        overlapping = (set(fields_a) - {key_a}) & (set(fields_b) - {key_b})
        left_names: OrderedDict[str, str] = OrderedDict()
        right_names: OrderedDict[str, str] = OrderedDict()
        for field in fields_a:
            left_names[field] = f"{field}{suffix_a}" if field in overlapping else field
        for field in fields_b:
            if field == key_b:
                continue
            right_names[field] = f"{field}{suffix_b}" if field in overlapping else field
        return left_names, right_names

    @classmethod
    def join_rows(
        cls,
        rows_a: list[dict[str, str]],
        rows_b: list[dict[str, str]],
        fields_a: list[str],
        key_a: str,
        key_b: str,
        join_type: str,
        left_names: OrderedDict[str, str],
        right_names: OrderedDict[str, str],
    ) -> list[dict[str, str]]:
        right_by_key: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        left_by_key: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        for row in rows_b:
            right_by_key.setdefault(row.get(key_b, ""), []).append(row)
        for row in rows_a:
            left_by_key.setdefault(row.get(key_a, ""), []).append(row)

        output_rows: list[dict[str, str]] = []
        if join_type in {"inner", "left", "outer"}:
            for left in rows_a:
                matches = right_by_key.get(left.get(key_a, ""), [])
                if matches:
                    output_rows.extend(cls.combine(left, right, left_names, right_names) for right in matches)
                elif join_type in {"left", "outer"}:
                    output_rows.append(cls.combine(left, None, left_names, right_names))
        if join_type in {"right", "outer"}:
            for right in rows_b:
                matches = left_by_key.get(right.get(key_b, ""), [])
                if join_type == "right" and matches:
                    output_rows.extend(cls.combine(left, right, left_names, right_names) for left in matches)
                elif not matches:
                    left_stub = {field: "" for field in fields_a}
                    left_stub[key_a] = right.get(key_b, "")
                    output_rows.append(cls.combine(left_stub, right, left_names, right_names))
        return output_rows

    @staticmethod
    def combine(
        left: dict[str, str],
        right: dict[str, str] | None,
        left_names: Mapping[str, str],
        right_names: Mapping[str, str],
    ) -> dict[str, str]:
        output = {target: left.get(source, "") for source, target in left_names.items()}
        for source, target in right_names.items():
            output[target] = right.get(source, "") if right else ""
        return output
