from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def _context(tmp_path: Path, name: str) -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir()
    return SimpleNamespace(node_dir=node_dir)


def _write_table(path: Path, rows: list[dict[str, Any]], delimiter: str = "	") -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


def _read_table(path: str | Path, delimiter: str = "	") -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def test_filter_rows_exposes_planned_search_aliases_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    aliases = registry.object_info()["filter_rows"]["search_aliases"]

    assert "subset rows" in aliases
    assert "where" in aliases
    assert "query" in aliases
    assert "conditional filter" in aliases


@pytest.mark.asyncio
async def test_filter_rows_filters_numeric_tsv_conditions(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "depth": "8", "status": "fail"},
        {"sample": "S2", "depth": "12", "status": "pass"},
        {"sample": "S3", "depth": "40", "status": "pass"},
    ])

    result = await _node_class("filter_rows")().run(
        table=str(table),
        column="depth",
        operator="greater_than",
        value="10",
        delimiter="tsv",
        context=_context(tmp_path, "filter"),
    )

    rows = _read_table(result[0])
    assert [row["sample"] for row in rows] == ["S2", "S3"]


@pytest.mark.asyncio
async def test_filter_rows_supports_planned_membership_operator_and_csv_output(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "depth": "8", "status": "fail"},
        {"sample": "S2", "depth": "12", "status": "pass"},
        {"sample": "S3", "depth": "40", "status": "review"},
    ])

    result = await _node_class("filter_rows")().run(
        table=str(table),
        column="status",
        operator="in",
        value="pass,review",
        delimiter="tsv",
        output_type="CSV",
        context=_context(tmp_path, "filter-in"),
    )

    output_path = Path(result[0])
    assert output_path.name == "samples.filtered.csv"
    rows = _read_table(output_path, delimiter=",")
    assert [row["sample"] for row in rows] == ["S2", "S3"]


@pytest.mark.asyncio
async def test_filter_rows_supports_not_contains_operator(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "tumor_A", "depth": "40", "status": "pass"},
        {"sample": "control_A", "depth": "35", "status": "pass"},
        {"sample": "tumor_B", "depth": "5", "status": "fail"},
    ])

    result = await _node_class("filter_rows")().run(
        table=str(table),
        column="sample",
        operator="not_contains",
        value="control",
        delimiter="tsv",
        context=_context(tmp_path, "filter-not-contains"),
    )

    rows = _read_table(result[0])
    assert [row["sample"] for row in rows] == ["tumor_A", "tumor_B"]


@pytest.mark.asyncio
async def test_filter_rows_combines_two_conditions_with_and_or(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "depth": "8", "status": "fail"},
        {"sample": "S2", "depth": "12", "status": "pass"},
        {"sample": "S3", "depth": "40", "status": "review"},
        {"sample": "S4", "depth": "50", "status": "pass"},
    ])
    node_class = _node_class("filter_rows")

    and_result = await node_class().run(
        table=str(table),
        column="depth",
        operator=">=",
        value="10",
        column_2="status",
        operator_2="==",
        value_2="pass",
        logical_op="AND",
        delimiter="tsv",
        context=_context(tmp_path, "filter-and"),
    )
    or_result = await node_class().run(
        table=str(table),
        column="depth",
        operator="<",
        value="10",
        column_2="status",
        operator_2="==",
        value_2="review",
        logical_op="OR",
        delimiter="tsv",
        context=_context(tmp_path, "filter-or"),
    )

    assert [row["sample"] for row in _read_table(and_result[0])] == ["S2", "S4"]
    assert [row["sample"] for row in _read_table(or_result[0])] == ["S1", "S3"]


@pytest.mark.asyncio
async def test_extract_columns_reorders_and_renames_columns(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "depth": "8", "status": "fail"},
        {"sample": "S2", "depth": "12", "status": "pass"},
    ])

    result = await _node_class("extract_columns")().run(
        table=str(table),
        columns="status,sample",
        rename_map="status:qc_status",
        delimiter="tsv",
        context=_context(tmp_path, "extract"),
    )

    rows = _read_table(result[0])
    assert list(rows[0]) == ["qc_status", "sample"]
    assert rows == [
        {"qc_status": "fail", "sample": "S1"},
        {"qc_status": "pass", "sample": "S2"},
    ]


@pytest.mark.asyncio
async def test_extract_columns_auto_output_type_preserves_csv_input_format(tmp_path: Path) -> None:
    table = tmp_path / "samples.csv"
    _write_table(table, [
        {"sample": "S1", "depth": "8", "status": "fail"},
        {"sample": "S2", "depth": "12", "status": "pass"},
    ], delimiter=",")

    result = await _node_class("extract_columns")().run(
        table=str(table),
        columns="status,sample",
        rename_map="status:qc_status",
        delimiter="auto",
        output_type="AUTO",
        context=_context(tmp_path, "extract-auto-csv"),
    )

    output_path = Path(result[0])
    assert output_path.name == "samples.extracted.csv"
    rows = _read_table(output_path, delimiter=",")
    assert list(rows[0]) == ["qc_status", "sample"]
    assert rows == [
        {"qc_status": "fail", "sample": "S1"},
        {"qc_status": "pass", "sample": "S2"},
    ]


@pytest.mark.asyncio
async def test_merge_tables_supports_left_join_with_blank_missing_values(tmp_path: Path) -> None:
    table_a = tmp_path / "expression.tsv"
    table_b = tmp_path / "annotation.tsv"
    _write_table(table_a, [
        {"gene": "g1", "logfc": "2.0"},
        {"gene": "g2", "logfc": "-1.2"},
    ])
    _write_table(table_b, [
        {"gene": "g1", "symbol": "ABC1"},
        {"gene": "g3", "symbol": "XYZ3"},
    ])

    result = await _node_class("merge_tables")().run(
        table_a=str(table_a),
        table_b=str(table_b),
        join_key="gene",
        join_type="left",
        delimiter="tsv",
        context=_context(tmp_path, "merge"),
    )

    rows = _read_table(result[0])
    assert rows == [
        {"gene": "g1", "logfc": "2.0", "symbol": "ABC1"},
        {"gene": "g2", "logfc": "-1.2", "symbol": ""},
    ]


def test_merge_tables_exposes_output_type_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["merge_tables"]
    assert node_info["display_name"] == "Merge Tables"
    assert node_info["output_name"] == ["merged_table"]
    assert set(node_info["input"]["required"]) == {"table_a", "table_b"}
    assert {"join_key", "key_column_a", "key_column_b", "suffix_a", "suffix_b"}.issubset(
        node_info["input"]["optional"]
    )
    assert node_info["input"]["optional"]["join_type"][1]["options"] == ["inner", "left", "right", "outer", "cross"]
    output_type = node_info["input"]["optional"]["output_type"]
    assert output_type[1]["default"] == "AUTO"
    assert output_type[1]["options"] == ["AUTO", "CSV", "TSV"]


@pytest.mark.asyncio
async def test_merge_tables_auto_output_type_preserves_csv_inputs(tmp_path: Path) -> None:
    table_a = tmp_path / "expression.csv"
    table_b = tmp_path / "annotation.csv"
    _write_table(table_a, [
        {"gene": "g1", "logfc": "2.0"},
        {"gene": "g2", "logfc": "-1.2"},
    ], delimiter=",")
    _write_table(table_b, [
        {"gene": "g1", "symbol": "ABC1"},
        {"gene": "g3", "symbol": "XYZ3"},
    ], delimiter=",")

    result = await _node_class("merge_tables")().run(
        table_a=str(table_a),
        table_b=str(table_b),
        join_key="gene",
        join_type="left",
        delimiter="auto",
        output_type="AUTO",
        context=_context(tmp_path, "merge-auto-csv"),
    )

    output_path = Path(result[0])
    assert output_path.name == "expression.merged.csv"
    rows = _read_table(output_path, delimiter=",")
    assert rows == [
        {"gene": "g1", "logfc": "2.0", "symbol": "ABC1"},
        {"gene": "g2", "logfc": "-1.2", "symbol": ""},
    ]


@pytest.mark.asyncio
async def test_merge_tables_supports_spec_style_different_key_columns(tmp_path: Path) -> None:
    table_a = tmp_path / "transcripts.tsv"
    table_b = tmp_path / "annotation.tsv"
    _write_table(table_a, [
        {"transcript_id": "tx1", "tpm": "12.5"},
        {"transcript_id": "tx2", "tpm": "0.8"},
    ])
    _write_table(table_b, [
        {"tx_id": "tx1", "symbol": "ABC1"},
        {"tx_id": "tx3", "symbol": "XYZ3"},
    ])

    result = await _node_class("merge_tables")().run(
        table_a=str(table_a),
        table_b=str(table_b),
        key_column_a="transcript_id",
        key_column_b="tx_id",
        join_type="inner",
        delimiter="tsv",
        context=_context(tmp_path, "merge-different-keys"),
    )

    rows = _read_table(result[0])
    assert rows == [
        {"transcript_id": "tx1", "tpm": "12.5", "symbol": "ABC1"},
    ]


@pytest.mark.asyncio
async def test_merge_tables_auto_detects_common_key_when_not_specified(tmp_path: Path) -> None:
    table_a = tmp_path / "expression.tsv"
    table_b = tmp_path / "annotation.tsv"
    _write_table(table_a, [
        {"gene": "g1", "logfc": "2.0"},
        {"gene": "g2", "logfc": "-1.2"},
    ])
    _write_table(table_b, [
        {"gene": "g1", "symbol": "ABC1"},
        {"gene": "g3", "symbol": "XYZ3"},
    ])

    result = await _node_class("merge_tables")().run(
        table_a=str(table_a),
        table_b=str(table_b),
        join_type="left",
        delimiter="tsv",
        context=_context(tmp_path, "merge-auto-key"),
    )

    rows = _read_table(result[0])
    assert rows == [
        {"gene": "g1", "logfc": "2.0", "symbol": "ABC1"},
        {"gene": "g2", "logfc": "-1.2", "symbol": ""},
    ]


@pytest.mark.asyncio
async def test_merge_tables_cross_join_does_not_require_key_columns(tmp_path: Path) -> None:
    table_a = tmp_path / "samples.tsv"
    table_b = tmp_path / "conditions.tsv"
    _write_table(table_a, [
        {"sample": "S1"},
        {"sample": "S2"},
    ])
    _write_table(table_b, [
        {"condition": "control"},
        {"condition": "treated"},
    ])

    result = await _node_class("merge_tables")().run(
        table_a=str(table_a),
        table_b=str(table_b),
        join_type="cross",
        delimiter="tsv",
        context=_context(tmp_path, "merge-cross"),
    )

    rows = _read_table(result[0])
    assert rows == [
        {"sample": "S1", "condition": "control"},
        {"sample": "S1", "condition": "treated"},
        {"sample": "S2", "condition": "control"},
        {"sample": "S2", "condition": "treated"},
    ]


@pytest.mark.asyncio
async def test_merge_tables_suffixes_both_overlapping_non_key_columns(tmp_path: Path) -> None:
    table_a = tmp_path / "expression.tsv"
    table_b = tmp_path / "annotation.tsv"
    _write_table(table_a, [
        {"gene": "g1", "score": "0.91"},
    ])
    _write_table(table_b, [
        {"gene": "g1", "score": "curated", "symbol": "ABC1"},
    ])

    result = await _node_class("merge_tables")().run(
        table_a=str(table_a),
        table_b=str(table_b),
        join_key="gene",
        join_type="inner",
        delimiter="tsv",
        suffix_a="_expr",
        suffix_b="_ann",
        context=_context(tmp_path, "merge-suffixes"),
    )

    rows = _read_table(result[0])
    assert list(rows[0]) == ["gene", "score_expr", "score_ann", "symbol"]
    assert rows == [
        {"gene": "g1", "score_expr": "0.91", "score_ann": "curated", "symbol": "ABC1"},
    ]


def test_join_tables_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["join_tables"]
    assert node_info["display_name"] == "Join Tables"
    assert node_info["category"] == "data_transform"
    assert node_info["description"].startswith("Join two CSV/TSV tables")
    assert node_info["output_name"] == ["joined_table"]
    assert node_info["output"] == ["TSV"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"table_a", "table_b", "join_keys"}
    assert set(inputs["optional"]) == {"how", "delimiter", "left_suffix", "right_suffix"}
    assert "advanced join" in node_info["search_aliases"]


def test_extract_columns_exposes_output_type_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["extract_columns"]
    assert node_info["display_name"] == "Extract Columns"
    assert node_info["output_name"] == ["extracted_table"]
    output_type = node_info["input"]["optional"]["output_type"]
    assert output_type[1]["default"] == "AUTO"
    assert output_type[1]["options"] == ["AUTO", "CSV", "TSV"]
    assert "column_indices" in node_info["input"]["optional"]
    assert "rename_to" in node_info["input"]["optional"]
    assert "drop_mode" in node_info["input"]["optional"]


@pytest.mark.asyncio
async def test_extract_columns_supports_zero_based_column_indices(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "depth": "8", "status": "fail"},
        {"sample": "S2", "depth": "12", "status": "pass"},
    ])

    result = await _node_class("extract_columns")().run(
        table=str(table),
        columns="",
        column_indices="2,0",
        delimiter="tsv",
        output_type="TSV",
        context=_context(tmp_path, "extract-indices"),
    )

    rows = _read_table(result[0])
    assert list(rows[0]) == ["status", "sample"]
    assert rows == [
        {"status": "fail", "sample": "S1"},
        {"status": "pass", "sample": "S2"},
    ]


@pytest.mark.asyncio
async def test_extract_columns_supports_positional_rename_to(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "depth": "8", "status": "fail"},
        {"sample": "S2", "depth": "12", "status": "pass"},
    ])

    result = await _node_class("extract_columns")().run(
        table=str(table),
        columns="status,sample",
        rename_to="qc_status,sample_id",
        delimiter="tsv",
        output_type="TSV",
        context=_context(tmp_path, "extract-rename-to"),
    )

    rows = _read_table(result[0])
    assert list(rows[0]) == ["qc_status", "sample_id"]
    assert rows == [
        {"qc_status": "fail", "sample_id": "S1"},
        {"qc_status": "pass", "sample_id": "S2"},
    ]


@pytest.mark.asyncio
async def test_extract_columns_rejects_rename_to_count_mismatch(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "depth": "8", "status": "fail"},
    ])

    with pytest.raises(ValueError, match="rename_to length"):
        await _node_class("extract_columns")().run(
            table=str(table),
            columns="status,sample",
            rename_to="qc_status",
            delimiter="tsv",
            output_type="TSV",
            context=_context(tmp_path, "extract-rename-to-mismatch"),
        )


@pytest.mark.asyncio
async def test_extract_columns_drop_mode_removes_selected_columns(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "depth": "8", "status": "fail"},
        {"sample": "S2", "depth": "12", "status": "pass"},
    ])

    result = await _node_class("extract_columns")().run(
        table=str(table),
        columns="depth",
        drop_mode=True,
        delimiter="tsv",
        output_type="TSV",
        context=_context(tmp_path, "extract-drop-mode"),
    )

    rows = _read_table(result[0])
    assert list(rows[0]) == ["sample", "status"]
    assert rows == [
        {"sample": "S1", "status": "fail"},
        {"sample": "S2", "status": "pass"},
    ]


@pytest.mark.asyncio
async def test_extract_columns_star_selects_all_columns(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "depth": "8", "status": "fail"},
        {"sample": "S2", "depth": "12", "status": "pass"},
    ])

    result = await _node_class("extract_columns")().run(
        table=str(table),
        columns="*",
        delimiter="tsv",
        output_type="TSV",
        context=_context(tmp_path, "extract-star"),
    )

    rows = _read_table(result[0])
    assert list(rows[0]) == ["sample", "depth", "status"]
    assert rows == [
        {"sample": "S1", "depth": "8", "status": "fail"},
        {"sample": "S2", "depth": "12", "status": "pass"},
    ]


@pytest.mark.asyncio
async def test_extract_columns_colon_prefix_selects_first_n_columns(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "depth": "8", "status": "fail"},
        {"sample": "S2", "depth": "12", "status": "pass"},
    ])

    result = await _node_class("extract_columns")().run(
        table=str(table),
        columns=":2",
        delimiter="tsv",
        output_type="TSV",
        context=_context(tmp_path, "extract-first-two"),
    )

    rows = _read_table(result[0])
    assert list(rows[0]) == ["sample", "depth"]
    assert rows == [
        {"sample": "S1", "depth": "8"},
        {"sample": "S2", "depth": "12"},
    ]


@pytest.mark.asyncio
async def test_join_tables_supports_multi_key_outer_join_and_suffixes(tmp_path: Path) -> None:
    table_a = tmp_path / "left.tsv"
    table_b = tmp_path / "right.tsv"
    _write_table(table_a, [
        {"sample": "S1", "gene": "g1", "value": "10", "left_only": "L1"},
        {"sample": "S1", "gene": "g2", "value": "20", "left_only": "L2"},
    ])
    _write_table(table_b, [
        {"sample": "S1", "gene": "g1", "value": "A", "symbol": "ABC1"},
        {"sample": "S2", "gene": "g3", "value": "B", "symbol": "XYZ3"},
    ])

    result = await _node_class("join_tables")().run(
        table_a=str(table_a),
        table_b=str(table_b),
        join_keys="sample,gene",
        how="outer",
        delimiter="tsv",
        left_suffix="_left",
        right_suffix="_right",
        context=_context(tmp_path, "join-outer"),
    )

    rows = _read_table(result[0])
    assert list(rows[0]) == ["sample", "gene", "value_left", "left_only", "value_right", "symbol"]
    assert rows == [
        {
            "sample": "S1",
            "gene": "g1",
            "value_left": "10",
            "left_only": "L1",
            "value_right": "A",
            "symbol": "ABC1",
        },
        {
            "sample": "S1",
            "gene": "g2",
            "value_left": "20",
            "left_only": "L2",
            "value_right": "",
            "symbol": "",
        },
        {
            "sample": "S2",
            "gene": "g3",
            "value_left": "",
            "left_only": "",
            "value_right": "B",
            "symbol": "XYZ3",
        },
    ]


@pytest.mark.asyncio
async def test_join_tables_supports_index_join_when_keys_are_empty(tmp_path: Path) -> None:
    table_a = tmp_path / "left.tsv"
    table_b = tmp_path / "right.tsv"
    _write_table(table_a, [
        {"sample": "S1", "depth": "10"},
        {"sample": "S2", "depth": "20"},
    ])
    _write_table(table_b, [
        {"qc": "pass"},
        {"qc": "fail"},
    ])

    result = await _node_class("join_tables")().run(
        table_a=str(table_a),
        table_b=str(table_b),
        join_keys="",
        how="inner",
        delimiter="tsv",
        context=_context(tmp_path, "join-index"),
    )

    assert _read_table(result[0]) == [
        {"sample": "S1", "depth": "10", "qc": "pass"},
        {"sample": "S2", "depth": "20", "qc": "fail"},
    ]


@pytest.mark.asyncio
async def test_aggregate_by_group_computes_mean_values(tmp_path: Path) -> None:
    table = tmp_path / "counts.tsv"
    _write_table(table, [
        {"condition": "case", "count": "10"},
        {"condition": "case", "count": "14"},
        {"condition": "control", "count": "3"},
    ])

    result = await _node_class("aggregate_by_group")().run(
        table=str(table),
        group_by="condition",
        value_column="count",
        operation="mean",
        delimiter="tsv",
        context=_context(tmp_path, "aggregate"),
    )

    rows = _read_table(result[0])
    assert rows == [
        {"condition": "case", "mean_count": "12"},
        {"condition": "control", "mean_count": "3"},
    ]


@pytest.mark.asyncio
async def test_string_format_uses_json_variables(tmp_path: Path) -> None:
    result = await _node_class("string_format")().run(
        template="sample {sample} depth {depth}",
        variables_json=json.dumps({"sample": "S1", "depth": 12}),
        context=_context(tmp_path, "string"),
    )

    assert result == ("sample S1 depth 12",)


@pytest.mark.asyncio
async def test_math_expression_evaluates_safe_variable_expression(tmp_path: Path) -> None:
    result = await _node_class("math_expression")().run(
        expression="a * 2 + b",
        variables_json=json.dumps({"a": 3, "b": 4}),
        context=_context(tmp_path, "math"),
    )

    assert result == (10.0, 10, True, "10")


@pytest.mark.asyncio
async def test_format_converter_converts_csv_to_json_records(tmp_path: Path) -> None:
    table = tmp_path / "samples.csv"
    _write_table(table, [
        {"sample": "S1", "depth": "12"},
        {"sample": "S2", "depth": "8"},
    ], delimiter=",")

    result = await _node_class("format_converter")().run(
        input_file=str(table),
        input_format="csv",
        output_format="json",
        context=_context(tmp_path, "format-json"),
    )

    output_path = Path(result[0])
    assert output_path.name == "samples.json"
    assert json.loads(output_path.read_text(encoding="utf-8")) == [
        {"sample": "S1", "depth": "12"},
        {"sample": "S2", "depth": "8"},
    ]


@pytest.mark.asyncio
async def test_format_converter_converts_json_records_to_tsv(tmp_path: Path) -> None:
    records = tmp_path / "records.json"
    records.write_text(
        json.dumps([
            {"sample": "S1", "depth": 12},
            {"sample": "S2", "status": "pass"},
        ]),
        encoding="utf-8",
    )

    result = await _node_class("format_converter")().run(
        input_file=str(records),
        input_format="json",
        output_format="tsv",
        context=_context(tmp_path, "format-tsv"),
    )

    rows = _read_table(result[0])
    assert list(rows[0]) == ["sample", "depth", "status"]
    assert rows == [
        {"sample": "S1", "depth": "12", "status": ""},
        {"sample": "S2", "depth": "", "status": "pass"},
    ]


def test_format_converter_advertises_bio_conversion_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_info = registry.object_info()["format_converter"]

    assert node_info["category"] == "data_transform"
    assert node_info["requires_external_tools"] is True
    assert node_info["required_executables"] == ["samtools", "bcftools", "gffread", "seqtk"]
    assert node_info["required_conda_packages"] == ["samtools", "bcftools", "gffread", "seqtk"]
    assert "bam to cram" in node_info["search_aliases"]
    assert "fastq to fasta" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert inputs["required"]["input_file"][0] == "STRING"
    assert set(inputs["required"]["output_format"][1]["options"]) == {
        "csv",
        "tsv",
        "json",
        "SAM",
        "BAM",
        "CRAM",
        "VCF",
        "VCF_GZ",
        "BCF",
        "GFF",
        "GTF",
        "FASTQ",
        "FASTA",
    }
    assert set(inputs["optional"]) == {"input_format", "reference", "compression_level", "threads", "output_name"}
    assert node_info["output"] == ["FILE"]
    assert node_info["output_name"] == ["converted_file"]


def test_format_converter_plans_bio_output_extension() -> None:
    node_class = _node_class("format_converter")

    outputs = node_class.PLAN_OUTPUTS(
        {"input_file": "sample.bam", "output_format": "CRAM", "output_name": "archive copy"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == ["/tmp/run/format_converter/archive_copy.cram"]


def test_format_converter_renders_samtools_cram_command() -> None:
    node_class = _node_class("format_converter")

    cmd = node_class.render_command({
        "input_file": "sample.bam",
        "output_format": "CRAM",
        "reference": "GRCh38.fa",
        "compression_level": 7,
        "threads": 4,
        "output": "/tmp/run/format_converter",
    })

    assert cmd == [
        "samtools",
        "view",
        "-@",
        "4",
        "-C",
        "-l",
        "7",
        "-T",
        "GRCh38.fa",
        "-o",
        "/tmp/run/format_converter/sample.to_cram.cram",
        "sample.bam",
    ]


def test_format_converter_renders_bcftools_bcf_command() -> None:
    node_class = _node_class("format_converter")

    cmd = node_class.render_command({
        "input_file": "cohort.vcf.gz",
        "output_format": "BCF",
        "threads": 2,
        "output": "/tmp/run/format_converter",
    })

    assert cmd == [
        "bcftools",
        "view",
        "--threads",
        "2",
        "-Ob",
        "-o",
        "/tmp/run/format_converter/cohort.to_bcf.bcf",
        "cohort.vcf.gz",
    ]


def test_format_converter_renders_gffread_and_seqtk_commands() -> None:
    node_class = _node_class("format_converter")

    gtf_cmd = node_class.render_command({
        "input_file": "genes.gff3",
        "output_format": "GTF",
        "output": "/tmp/run/format_converter",
    })
    fasta_cmd = node_class.render_command({
        "input_file": "reads.fastq.gz",
        "output_format": "FASTA",
        "output": "/tmp/run/format_converter",
    })

    assert gtf_cmd == [
        "gffread",
        "genes.gff3",
        "-T",
        "-o",
        "/tmp/run/format_converter/genes.to_gtf.gtf",
    ]
    assert fasta_cmd == [
        "seqtk",
        "seq",
        "-A",
        "reads.fastq.gz",
        ">",
        "/tmp/run/format_converter/reads.to_fasta.fasta",
    ]


def test_format_converter_rejects_unsupported_bio_conversion() -> None:
    node_class = _node_class("format_converter")

    assert node_class.VALIDATE_INPUTS({
        "input_file": "reads.fastq.gz",
        "output_format": "BAM",
    }) == "Cannot convert FASTQ to BAM with format_converter"


def test_format_converter_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["gffread"] == "gffread"
    assert EXECUTABLE_TO_CONDA_PACKAGE["seqtk"] == "seqtk"
    assert PACKAGE_MIN_VERSIONS["gffread"] == ">=0.12.7"
    assert PACKAGE_MIN_VERSIONS["seqtk"] == ">=1.4"


@pytest.mark.asyncio
async def test_format_converter_runs_bio_command_from_base_node_dir(tmp_path: Path) -> None:
    calls: list[tuple[str | list[str], Path | None]] = []

    class CommandContext(SimpleNamespace):
        async def run_command(self, cmd: str | list[str], cwd: Path | str | None = None) -> dict[str, Any]:
            calls.append((cmd, Path(cwd) if cwd is not None else None))
            return {"returncode": 0, "stderr": ""}

    context = CommandContext(node_dir=tmp_path / "format-run")
    context.node_dir.mkdir()

    result = await _node_class("format_converter")().run(
        input_file="reads.fastq.gz",
        output_format="FASTA",
        context=context,
    )

    assert result == (str(context.node_dir / "format_converter" / "reads.to_fasta.fasta"),)
    assert calls == [(
        f"seqtk seq -A reads.fastq.gz > {context.node_dir / 'format_converter' / 'reads.to_fasta.fasta'}",
        context.node_dir,
    )]


def test_transpose_table_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["transpose_table"]["display_name"] == "Transpose Table"
    assert info["transpose_table"]["category"] == "data_transform"
    assert info["transpose_table"]["output_name"] == ["transposed_table"]
    assert info["transpose_table"]["output"] == ["CSV"]


def test_tsv_to_fasta_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["tsv_to_fasta"]
    assert node_info["display_name"] == "TSV to FASTA"
    assert node_info["category"] == "data_transform"
    assert node_info["output_name"] == ["fasta"]
    assert node_info["output"] == ["FASTA"]
    assert set(node_info["input"]["required"]) == {"table", "id_column", "seq_column"}


@pytest.mark.asyncio
async def test_tsv_to_fasta_converts_table_rows_to_records(tmp_path: Path) -> None:
    table = tmp_path / "sequences.tsv"
    _write_table(table, [
        {"sample": "S1", "sequence": "ACGTACGT", "condition": "case"},
        {"sample": "S2", "sequence": "TTTTCCCC", "condition": "control"},
    ])

    result = await _node_class("tsv_to_fasta")().run(
        table=str(table),
        id_column="sample",
        seq_column="sequence",
        delimiter="tsv",
        context=_context(tmp_path, "tsv-fasta"),
    )

    output_path = Path(result[0])
    assert output_path.name == "sequences.fasta"
    assert output_path.read_text(encoding="utf-8") == ">S1\nACGTACGT\n>S2\nTTTTCCCC\n"


@pytest.mark.asyncio
async def test_tsv_to_fasta_auto_detects_csv_and_wraps_sequences(tmp_path: Path) -> None:
    table = tmp_path / "amplicons.csv"
    _write_table(table, [
        {"id": "amp 1", "seq": "ACGTACGTAC"},
    ], delimiter=",")

    result = await _node_class("tsv_to_fasta")().run(
        table=str(table),
        id_column="id",
        seq_column="seq",
        line_width=4,
        context=_context(tmp_path, "csv-fasta"),
    )

    assert Path(result[0]).read_text(encoding="utf-8") == ">amp_1\nACGT\nACGT\nAC\n"


@pytest.mark.asyncio
async def test_tsv_to_fasta_rejects_missing_columns_and_empty_sequences(tmp_path: Path) -> None:
    table = tmp_path / "sequences.tsv"
    _write_table(table, [
        {"sample": "S1", "sequence": ""},
    ])
    node = _node_class("tsv_to_fasta")()

    with pytest.raises(ValueError, match="Column\\(s\\) not found: missing"):
        await node.run(
            table=str(table),
            id_column="sample",
            seq_column="missing",
            context=_context(tmp_path, "missing-column"),
        )

    with pytest.raises(ValueError, match="Row 1 has an empty sequence"):
        await node.run(
            table=str(table),
            id_column="sample",
            seq_column="sequence",
            context=_context(tmp_path, "empty-sequence"),
        )


@pytest.mark.asyncio
async def test_transpose_table_transposes_tsv_using_first_column_ids(tmp_path: Path) -> None:
    table = tmp_path / "counts.tsv"
    _write_table(table, [
        {"gene": "BRCA1", "S1": "10", "S2": "12"},
        {"gene": "TP53", "S1": "3", "S2": "8"},
    ])

    result = await _node_class("transpose_table")().run(
        table=str(table),
        output_type="TSV",
        context=_context(tmp_path, "transpose"),
    )

    output_path = Path(result[0])
    assert output_path.name == "counts.transposed.tsv"
    rows = _read_table(output_path)
    assert list(rows[0]) == ["gene", "BRCA1", "TP53"]
    assert rows == [
        {"gene": "S1", "BRCA1": "10", "TP53": "3"},
        {"gene": "S2", "BRCA1": "12", "TP53": "8"},
    ]


def test_replace_text_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["replace_text"]["display_name"] == "Replace Text"
    assert info["replace_text"]["category"] == "data_transform"
    assert info["replace_text"]["output_name"] == ["replaced_file"]
    assert info["replace_text"]["output"] == ["FILE"]


@pytest.mark.asyncio
async def test_replace_text_literal_case_insensitive_whole_word(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("chr1\t100\nchromosome chr2\nCHR and chr\n", encoding="utf-8")

    result = await _node_class("replace_text")().run(
        file=str(source),
        search="chr",
        replace="chrom",
        case_sensitive=False,
        whole_word=True,
        context=_context(tmp_path, "replace-literal"),
    )

    output_path = Path(result[0])
    assert output_path.name == "notes.replaced.txt"
    assert output_path.read_text(encoding="utf-8") == "chr1\t100\nchromosome chr2\nchrom and chrom\n"


@pytest.mark.asyncio
async def test_replace_text_regex_affected_lines_only_and_output_extension(tmp_path: Path) -> None:
    source = tmp_path / "samples.tsv"
    source.write_text("sample\tstatus\nSAMPLE_001\tfail\ncontrol\tpass\nSAMPLE_002\tpass\n", encoding="utf-8")

    result = await _node_class("replace_text")().run(
        file=str(source),
        search=r"SAMPLE_(\d+)",
        replace=r"PATIENT_\1",
        use_regex=True,
        affected_lines_only=True,
        output_extension=".txt",
        context=_context(tmp_path, "replace-regex"),
    )

    output_path = Path(result[0])
    assert output_path.name == "samples.replaced.txt"
    assert output_path.read_text(encoding="utf-8") == "PATIENT_001\tfail\nPATIENT_002\tpass\n"


def test_sort_file_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["sort_file"]["display_name"] == "Sort File"
    assert info["sort_file"]["category"] == "data_transform"
    assert info["sort_file"]["output_name"] == ["sorted_file"]
    assert info["sort_file"]["output"] == ["CSV"]


@pytest.mark.asyncio
async def test_sort_file_sorts_tsv_by_numeric_column_descending(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "depth": "8"},
        {"sample": "S2", "depth": "12"},
        {"sample": "S3", "depth": "40"},
    ])

    result = await _node_class("sort_file")().run(
        file=str(table),
        sort_column="depth",
        sort_type="numeric",
        ascending=False,
        separator="tab",
        output_type="TSV",
        context=_context(tmp_path, "sort-numeric"),
    )

    output_path = Path(result[0])
    assert output_path.name == "samples.sorted.tsv"
    rows = _read_table(output_path)
    assert [row["sample"] for row in rows] == ["S3", "S2", "S1"]


@pytest.mark.asyncio
async def test_sort_file_sorts_no_header_by_column_index(tmp_path: Path) -> None:
    table = tmp_path / "regions.bed"
    table.write_text("chr2\t30\t40\nchr1\t20\t30\nchr1\t10\t20\n", encoding="utf-8")

    result = await _node_class("sort_file")().run(
        file=str(table),
        sort_column="0,1",
        sort_type="auto",
        has_header=False,
        separator="tab",
        output_type="TSV",
        context=_context(tmp_path, "sort-index"),
    )

    output_path = Path(result[0])
    assert output_path.name == "regions.sorted.tsv"
    assert output_path.read_text(encoding="utf-8") == "chr1\t10\t20\nchr1\t20\t30\nchr2\t30\t40\n"


def test_deduplicate_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["deduplicate"]["display_name"] == "Deduplicate"
    assert info["deduplicate"]["category"] == "data_transform"
    assert info["deduplicate"]["output_name"] == ["deduplicated", "duplicates"]
    assert info["deduplicate"]["output"] == ["CSV", "CSV"]


@pytest.mark.asyncio
async def test_deduplicate_keeps_first_by_subset_columns_and_reports_duplicates(tmp_path: Path) -> None:
    table = tmp_path / "variants.tsv"
    _write_table(table, [
        {"sample": "S1", "variant": "v1", "depth": "12"},
        {"sample": "S1", "variant": "v1", "depth": "18"},
        {"sample": "S2", "variant": "v1", "depth": "22"},
        {"sample": "S2", "variant": "v2", "depth": "30"},
    ])

    result = await _node_class("deduplicate")().run(
        table=str(table),
        subset_columns="sample,variant",
        keep="first",
        report_dups=True,
        delimiter="tsv",
        output_type="TSV",
        context=_context(tmp_path, "dedupe-first"),
    )

    deduplicated, duplicates = result
    assert Path(deduplicated).name == "variants.deduplicated.tsv"
    assert Path(duplicates).name == "variants.duplicates.tsv"
    assert _read_table(deduplicated) == [
        {"sample": "S1", "variant": "v1", "depth": "12"},
        {"sample": "S2", "variant": "v1", "depth": "22"},
        {"sample": "S2", "variant": "v2", "depth": "30"},
    ]
    assert _read_table(duplicates) == [
        {"sample": "S1", "variant": "v1", "depth": "18"},
    ]


@pytest.mark.asyncio
async def test_deduplicate_keep_none_removes_all_rows_with_duplicate_keys(tmp_path: Path) -> None:
    table = tmp_path / "counts.tsv"
    _write_table(table, [
        {"gene": "A", "count": "10"},
        {"gene": "B", "count": "5"},
        {"gene": "A", "count": "12"},
        {"gene": "C", "count": "2"},
    ])

    result = await _node_class("deduplicate")().run(
        table=str(table),
        subset_columns="gene",
        keep="none",
        report_dups=True,
        delimiter="tsv",
        output_type="TSV",
        context=_context(tmp_path, "dedupe-none"),
    )

    deduplicated, duplicates = result
    assert _read_table(deduplicated) == [
        {"gene": "B", "count": "5"},
        {"gene": "C", "count": "2"},
    ]
    assert _read_table(duplicates) == [
        {"gene": "A", "count": "10"},
        {"gene": "A", "count": "12"},
    ]


@pytest.mark.asyncio
async def test_deduplicate_fasta_keeps_first_sequence_and_reports_duplicates(tmp_path: Path) -> None:
    fasta = tmp_path / "contigs.fasta"
    fasta.write_text(
        ">contig1 sample=A\n"
        "ACGTACGT\n"
        ">contig2 sample=B\n"
        "TTTT\n"
        ">contig3 duplicate_of_1\n"
        "ACGT\n"
        "ACGT\n",
        encoding="utf-8",
    )

    deduplicated, duplicates = await _node_class("deduplicate")().run(
        table=str(fasta),
        keep="first",
        report_dups=True,
        context=_context(tmp_path, "dedupe-fasta"),
    )

    assert Path(deduplicated).name == "contigs.deduplicated.fasta"
    assert Path(duplicates).name == "contigs.duplicates.fasta"
    assert Path(deduplicated).read_text(encoding="utf-8") == (
        ">contig1 sample=A\n"
        "ACGTACGT\n"
        ">contig2 sample=B\n"
        "TTTT\n"
    )
    assert Path(duplicates).read_text(encoding="utf-8") == (
        ">contig3 duplicate_of_1\n"
        "ACGTACGT\n"
    )


def test_set_fields_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_info = registry.object_info()["set_fields"]

    assert node_info["display_name"] == "Set Fields"
    assert node_info["category"] == "data_transform"
    assert node_info["output_name"] == ["updated_table"]
    assert "field mapping" in node_info["search_aliases"]
    assert node_info["input"]["required"]["assignments"][0] == "STRING"


@pytest.mark.asyncio
async def test_set_fields_adds_constants_and_templates_per_row(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "condition": "tumor", "depth": "40"},
        {"sample": "S2", "condition": "control", "depth": "12"},
    ])

    result = await _node_class("set_fields")().run(
        table=str(table),
        assignments='{"qc_status": "review", "label": "{sample}:{condition}", "depth": "{depth}x"}',
        delimiter="tsv",
        output_type="TSV",
        context=_context(tmp_path, "set-fields"),
    )

    output_path = Path(result[0])
    assert output_path.name == "samples.set.tsv"
    assert _read_table(output_path) == [
        {"sample": "S1", "condition": "tumor", "depth": "40x", "qc_status": "review", "label": "S1:tumor"},
        {"sample": "S2", "condition": "control", "depth": "12x", "qc_status": "review", "label": "S2:control"},
    ]


@pytest.mark.asyncio
async def test_set_fields_can_keep_only_selected_fields_and_preserve_csv(tmp_path: Path) -> None:
    table = tmp_path / "samples.csv"
    _write_table(table, [
        {"sample": "S1", "condition": "tumor", "depth": "40"},
        {"sample": "S2", "condition": "control", "depth": "12"},
    ], delimiter=",")

    result = await _node_class("set_fields")().run(
        table=str(table),
        assignments='{"label": "{sample}-{condition}", "batch": "A"}',
        keep_only_set=True,
        field_order="label,batch",
        delimiter="auto",
        output_type="AUTO",
        context=_context(tmp_path, "set-fields-keep"),
    )

    output_path = Path(result[0])
    assert output_path.name == "samples.set.csv"
    assert _read_table(output_path, delimiter=",") == [
        {"label": "S1-tumor", "batch": "A"},
        {"label": "S2-control", "batch": "A"},
    ]
