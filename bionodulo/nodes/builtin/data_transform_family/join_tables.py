"""Multi-key and row-index joins for strict CSV/TSV tables."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

from .adapter import (
    DELIMITER_MODES,
    PythonDataTransformNode,
    append_table_footer,
    delimiter_for,
    node_output_dir,
    path_value,
    read_table,
    split_fields,
    validate_choice,
    write_table,
)


JOIN_MODES = ("inner", "left", "right", "outer")


class JoinTablesNode(PythonDataTransformNode):
    """Join two tables by shared multi-column keys or row index."""

    NODE_ID = "join_tables"
    DISPLAY_NAME = "Join Tables"
    DESCRIPTION = (
        "Join two CSV/TSV tables by shared multi-column keys or by row index. "
        "Empty-tolerant: when either input table has zero data rows (header-only, "
        "provenance-footer-only, or no header at all) the node emits a header-only "
        "joined table with a provenance footer documenting the empty side instead of "
        "erroring, so evaluator ensembles where one evaluator legitimately produced "
        "no records still join."
    )
    SEARCH_ALIASES = ["join", "tables", "multi-key", "index join", "advanced join", "csv", "tsv"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("joined_table",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/csv.html"
    UPSTREAM_SOURCE = "Lib/csv.py; ordered dict insertion semantics"
    PRODUCT_ORIGIN_COMMIT = "c9191042c21e18a38500aba29517ff0ede13271c"
    EXIT_SEMANTICS = (
        "Missing files, malformed tables, absent keys, invalid join modes, and suffix collisions are fatal; "
        "empty join_keys explicitly selects deterministic row-index joining; an input table with zero "
        "data rows (including no header at all) yields a header-only joined table with a provenance "
        "footer rather than an error."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table_a": ("FILE", {"description": "Left CSV/TSV table"}),
                "table_b": ("FILE", {"description": "Right CSV/TSV table"}),
                "join_keys": (
                    "STRING",
                    {"default": "", "description": "Shared keys; empty joins rows by zero-based position"},
                ),
            },
            "optional": {
                "how": (list(JOIN_MODES), {"default": "inner"}),
                "delimiter": (list(DELIMITER_MODES), {"default": "auto"}),
                "left_suffix": ("STRING", {"default": "_left", "advanced": True}),
                "right_suffix": ("STRING", {"default": "_right", "advanced": True}),
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
        validation = validate_choice(inputs.get("how", "inner"), "how", JOIN_MODES)
        if validation is not True:
            return validation
        return validate_choice(inputs.get("delimiter", "auto"), "delimiter", DELIMITER_MODES)

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        table_a = Path(path_value(kwargs["table_a"])).expanduser()
        table_b = Path(path_value(kwargs["table_b"])).expanduser()
        delimiter_mode = kwargs.get("delimiter", "auto")
        fields_a, rows_a = self._read_table_lenient(table_a, delimiter_mode, "table_a")
        fields_b, rows_b = self._read_table_lenient(table_b, delimiter_mode, "table_b")
        join_keys = split_fields(kwargs.get("join_keys", ""))
        how = str(kwargs.get("how", "inner"))
        left_suffix = str(kwargs.get("left_suffix", "_left"))
        right_suffix = str(kwargs.get("right_suffix", "_right"))

        # Empty-tolerant join: an evaluator ensemble where ANY input table has
        # zero data rows (header-only, provenance-footer-only, or a fully empty
        # file) cannot produce joined records, so emit a header-only table with
        # a provenance footer documenting why — never a hard error.
        if not rows_a or not rows_b:
            empty_sides = [name for name, rows in (("table_a", rows_a), ("table_b", rows_b)) if not rows]
            output_path = node_output_dir(self, context) / "joined.tsv"
            write_table(
                output_path,
                self._empty_join_header(fields_a, fields_b, join_keys, left_suffix, right_suffix),
                [],
                "\t",
            )
            append_table_footer(
                output_path,
                [f"empty join: {', '.join(empty_sides)} has zero data rows"],
            )
            return (str(output_path),)

        output_fields = self.output_fields(fields_a, fields_b, join_keys, left_suffix, right_suffix)
        if len(output_fields) != len(set(output_fields)):
            raise ValueError("Join suffixes produce duplicate output column names")
        output_rows = (
            self.join_by_keys(
                rows_a,
                rows_b,
                fields_a,
                fields_b,
                output_fields,
                join_keys,
                how,
                left_suffix,
                right_suffix,
            )
            if join_keys
            else self.join_by_index(
                rows_a,
                rows_b,
                fields_a,
                fields_b,
                output_fields,
                how,
                left_suffix,
                right_suffix,
            )
        )
        output_path = node_output_dir(self, context) / "joined.tsv"
        write_table(output_path, output_fields, output_rows, "\t")
        return (str(output_path),)

    @staticmethod
    def _read_table_lenient(
        path: Path,
        delimiter_mode: str,
        name: str,
    ) -> tuple[list[str], list[dict[str, str]]]:
        """read_table, but a file with no header at all counts as zero data rows.

        Structural problems (blank/duplicate header names, ragged rows) stay
        fatal; only "there is literally nothing in this table" degrades to an
        empty side of the join.
        """
        try:
            return read_table(path, delimiter_for(delimiter_mode, path))
        except ValueError as exc:
            if "Table is empty" not in str(exc):
                raise
            return [], []

    @staticmethod
    def _empty_join_header(
        fields_a: list[str],
        fields_b: list[str],
        join_keys: list[str],
        left_suffix: str,
        right_suffix: str,
    ) -> list[str]:
        """Header for a zero-row join: the normal join header when both sides
        declare one, else whichever side's header survives, else the join keys
        (or a placeholder column) so the output is still a valid table."""
        if fields_a and fields_b:
            try:
                return JoinTablesNode.output_fields(fields_a, fields_b, join_keys, left_suffix, right_suffix)
            except ValueError:
                pass
        header = fields_a or fields_b or join_keys or ["id"]
        return list(dict.fromkeys(header))

    @staticmethod
    def output_fields(
        fields_a: list[str],
        fields_b: list[str],
        join_keys: list[str],
        left_suffix: str,
        right_suffix: str,
    ) -> list[str]:
        for key in join_keys:
            if key not in fields_a or key not in fields_b:
                raise ValueError(f"Join key {key!r} must exist in both tables")
        overlapping = (set(fields_a) & set(fields_b)) - set(join_keys)
        output = [f"{field}{left_suffix}" if field in overlapping else field for field in fields_a]
        output.extend(
            f"{field}{right_suffix}" if field in overlapping else field for field in fields_b if field not in join_keys
        )
        return output

    @classmethod
    def join_by_keys(
        cls,
        rows_a: list[dict[str, str]],
        rows_b: list[dict[str, str]],
        fields_a: list[str],
        fields_b: list[str],
        output_fields: list[str],
        join_keys: list[str],
        how: str,
        left_suffix: str,
        right_suffix: str,
    ) -> list[dict[str, str]]:
        right_by_key: OrderedDict[tuple[str, ...], list[dict[str, str]]] = OrderedDict()
        left_by_key: OrderedDict[tuple[str, ...], list[dict[str, str]]] = OrderedDict()
        for row in rows_b:
            right_by_key.setdefault(cls.key(row, join_keys), []).append(row)
        for row in rows_a:
            left_by_key.setdefault(cls.key(row, join_keys), []).append(row)
        output: list[dict[str, str]] = []
        if how in {"inner", "left", "outer"}:
            for left in rows_a:
                matches = right_by_key.get(cls.key(left, join_keys), [])
                if matches:
                    output.extend(
                        cls.combine(
                            left,
                            right,
                            fields_a,
                            fields_b,
                            join_keys,
                            output_fields,
                            left_suffix,
                            right_suffix,
                        )
                        for right in matches
                    )
                elif how in {"left", "outer"}:
                    output.append(
                        cls.combine(
                            left,
                            None,
                            fields_a,
                            fields_b,
                            join_keys,
                            output_fields,
                            left_suffix,
                            right_suffix,
                        )
                    )
        if how in {"right", "outer"}:
            for right in rows_b:
                matches = left_by_key.get(cls.key(right, join_keys), [])
                if how == "right" and matches:
                    output.extend(
                        cls.combine(
                            left,
                            right,
                            fields_a,
                            fields_b,
                            join_keys,
                            output_fields,
                            left_suffix,
                            right_suffix,
                        )
                        for left in matches
                    )
                elif not matches:
                    output.append(
                        cls.combine(
                            None,
                            right,
                            fields_a,
                            fields_b,
                            join_keys,
                            output_fields,
                            left_suffix,
                            right_suffix,
                        )
                    )
        return output

    @classmethod
    def join_by_index(
        cls,
        rows_a: list[dict[str, str]],
        rows_b: list[dict[str, str]],
        fields_a: list[str],
        fields_b: list[str],
        output_fields: list[str],
        how: str,
        left_suffix: str,
        right_suffix: str,
    ) -> list[dict[str, str]]:
        if how == "inner":
            indexes = range(min(len(rows_a), len(rows_b)))
        elif how == "left":
            indexes = range(len(rows_a))
        elif how == "right":
            indexes = range(len(rows_b))
        else:
            indexes = range(max(len(rows_a), len(rows_b)))
        return [
            cls.combine(
                rows_a[index] if index < len(rows_a) else None,
                rows_b[index] if index < len(rows_b) else None,
                fields_a,
                fields_b,
                [],
                output_fields,
                left_suffix,
                right_suffix,
            )
            for index in indexes
        ]

    @staticmethod
    def key(row: dict[str, str], join_keys: list[str]) -> tuple[str, ...]:
        return tuple(row.get(key, "") for key in join_keys)

    @staticmethod
    def combine(
        left: dict[str, str] | None,
        right: dict[str, str] | None,
        fields_a: list[str],
        fields_b: list[str],
        join_keys: list[str],
        output_fields: list[str],
        left_suffix: str,
        right_suffix: str,
    ) -> dict[str, str]:
        overlapping = (set(fields_a) & set(fields_b)) - set(join_keys)
        output = {field: "" for field in output_fields}
        for field in fields_a:
            target = f"{field}{left_suffix}" if field in overlapping else field
            output[target] = (
                left.get(field, "") if left else right.get(field, "") if right and field in join_keys else ""
            )
        for field in fields_b:
            if field in join_keys:
                if not output.get(field) and right:
                    output[field] = right.get(field, "")
                continue
            target = f"{field}{right_suffix}" if field in overlapping else field
            output[target] = right.get(field, "") if right else ""
        return output
