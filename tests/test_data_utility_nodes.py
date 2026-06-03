from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

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


def test_transpose_table_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["transpose_table"]["display_name"] == "Transpose Table"
    assert info["transpose_table"]["category"] == "data_transform"
    assert info["transpose_table"]["output_name"] == ["transposed_table"]
    assert info["transpose_table"]["output"] == ["CSV"]


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
