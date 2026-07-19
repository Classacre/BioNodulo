from __future__ import annotations

import csv
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


def _write_table(path: Path, rows: list[dict[str, Any]], delimiter: str = "\t") -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


def _read_table(path: str | Path, delimiter: str = "\t") -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def test_pivot_table_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["pivot_table"]["display_name"] == "Pivot Table"
    assert info["pivot_table"]["category"] == "data_transform"
    assert info["pivot_table"]["output_name"] == ["reshaped_table"]
    assert info["pivot_table"]["output"] == ["CSV"]
    assert info["pivot_table"]["python_class"] == (
        "bionodulo.nodes.builtin.data_transform_family.pivot_table.PivotTableNode"
    )
    output_type = info["pivot_table"]["input"]["optional"]["output_type"]
    assert output_type[1]["default"] == "AUTO"
    assert output_type[1]["options"] == ["AUTO", "CSV", "TSV"]


def test_reshape_table_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["reshape_table"]
    assert node_info["display_name"] == "Reshape Table"
    assert node_info["category"] == "data_transform"
    assert node_info["description"].startswith("Convert tables between wide and long formats")
    assert node_info["output_name"] == ["reshaped_table"]
    assert node_info["output"] == ["CSV"]
    assert node_info["python_class"] == (
        "bionodulo.nodes.builtin.data_transform_family.pivot_table.ReshapeTableNode"
    )
    assert "melt" in node_info["search_aliases"]
    assert "pivot_longer" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"table", "direction", "id_vars"}
    assert inputs["required"]["direction"][1]["options"] == ["long", "wide"]
    assert inputs["optional"]["output_type"][1]["default"] == "AUTO"
    assert inputs["optional"]["output_type"][1]["options"] == ["AUTO", "CSV", "TSV"]
    assert set(inputs["optional"]) == {
        "value_vars",
        "names_to",
        "values_to",
        "names_from",
        "values_from",
        "fill_value",
        "delimiter",
        "output_type",
    }


@pytest.mark.asyncio
async def test_pivot_wide_reshapes_long_tsv_with_fill_value(tmp_path: Path) -> None:
    table = tmp_path / "expression.tsv"
    _write_table(table, [
        {"gene": "BRCA1", "sample": "S1", "count": "10"},
        {"gene": "BRCA1", "sample": "S2", "count": "12"},
        {"gene": "TP53", "sample": "S1", "count": "3"},
    ])

    result = await _node_class("pivot_table")().run(
        table=str(table),
        operation="pivot_wide",
        index_column="gene",
        names_from="sample",
        values_from="count",
        fill_value="0",
        output_type="TSV",
        context=_context(tmp_path, "pivot-wide"),
    )

    output_path = Path(result[0])
    assert output_path.name == "expression.wide.tsv"
    rows = _read_table(output_path)
    assert list(rows[0]) == ["gene", "S1", "S2"]
    assert rows == [
        {"gene": "BRCA1", "S1": "10", "S2": "12"},
        {"gene": "TP53", "S1": "3", "S2": "0"},
    ]


@pytest.mark.asyncio
async def test_pivot_table_accepts_spec_api_with_multiple_index_columns(tmp_path: Path) -> None:
    table = tmp_path / "expression.tsv"
    _write_table(table, [
        {"gene": "BRCA1", "condition": "case", "sample": "S1", "count": "10"},
        {"gene": "BRCA1", "condition": "case", "sample": "S2", "count": "12"},
        {"gene": "BRCA1", "condition": "control", "sample": "S1", "count": "3"},
    ])

    result = await _node_class("pivot_table")().run(
        table=str(table),
        operation="pivot_wide",
        index_columns="gene,condition",
        columns_column="sample",
        values_column="count",
        fill_value="0",
        output_type="TSV",
        context=_context(tmp_path, "pivot-spec-api"),
    )

    rows = _read_table(result[0])
    assert list(rows[0]) == ["gene", "condition", "S1", "S2"]
    assert rows == [
        {"gene": "BRCA1", "condition": "case", "S1": "10", "S2": "12"},
        {"gene": "BRCA1", "condition": "control", "S1": "3", "S2": "0"},
    ]


@pytest.mark.asyncio
async def test_melt_long_reshapes_wide_tsv_to_long_rows(tmp_path: Path) -> None:
    table = tmp_path / "counts.tsv"
    _write_table(table, [
        {"gene": "BRCA1", "S1": "10", "S2": "12"},
        {"gene": "TP53", "S1": "3", "S2": "8"},
    ])

    result = await _node_class("pivot_table")().run(
        table=str(table),
        operation="melt_long",
        id_columns="gene",
        value_columns="S1,S2",
        variable_name="sample",
        value_name="count",
        output_type="TSV",
        context=_context(tmp_path, "melt-long"),
    )

    output_path = Path(result[0])
    assert output_path.name == "counts.long.tsv"
    rows = _read_table(output_path)
    assert list(rows[0]) == ["gene", "sample", "count"]
    assert rows == [
        {"gene": "BRCA1", "sample": "S1", "count": "10"},
        {"gene": "BRCA1", "sample": "S2", "count": "12"},
        {"gene": "TP53", "sample": "S1", "count": "3"},
        {"gene": "TP53", "sample": "S2", "count": "8"},
    ]


@pytest.mark.asyncio
async def test_pivot_table_agg_sums_duplicate_long_values(tmp_path: Path) -> None:
    table = tmp_path / "replicates.tsv"
    _write_table(table, [
        {"gene": "BRCA1", "sample": "S1", "count": "10"},
        {"gene": "BRCA1", "sample": "S1", "count": "2"},
        {"gene": "BRCA1", "sample": "S2", "count": "5"},
    ])

    result = await _node_class("pivot_table")().run(
        table=str(table),
        operation="pivot_table_agg",
        index_column="gene",
        names_from="sample",
        values_from="count",
        agg_func="sum",
        fill_value="0",
        output_type="TSV",
        context=_context(tmp_path, "pivot-agg"),
    )

    output_path = Path(result[0])
    assert output_path.name == "replicates.pivot.tsv"
    rows = _read_table(output_path)
    assert rows == [
        {"gene": "BRCA1", "S1": "12", "S2": "5"},
    ]


@pytest.mark.parametrize(
    ("agg_func", "expected_s1", "expected_s2"),
    [
        ("count", "3", "1"),
        ("min", "2", "5"),
        ("max", "10", "5"),
        ("median", "4", "5"),
    ],
)
@pytest.mark.asyncio
async def test_pivot_table_agg_supports_planned_functions(
    tmp_path: Path,
    agg_func: str,
    expected_s1: str,
    expected_s2: str,
) -> None:
    table = tmp_path / f"replicates_{agg_func}.tsv"
    _write_table(table, [
        {"gene": "BRCA1", "sample": "S1", "count": "10"},
        {"gene": "BRCA1", "sample": "S1", "count": "2"},
        {"gene": "BRCA1", "sample": "S1", "count": "4"},
        {"gene": "BRCA1", "sample": "S2", "count": "5"},
    ])

    result = await _node_class("pivot_table")().run(
        table=str(table),
        operation="pivot_table_agg",
        index_column="gene",
        names_from="sample",
        values_from="count",
        agg_func=agg_func,
        fill_value="0",
        output_type="TSV",
        context=_context(tmp_path, f"pivot-agg-{agg_func}"),
    )

    rows = _read_table(result[0])
    assert rows == [
        {"gene": "BRCA1", "S1": expected_s1, "S2": expected_s2},
    ]


@pytest.mark.asyncio
async def test_pivot_table_auto_output_type_preserves_csv_input_format(tmp_path: Path) -> None:
    table = tmp_path / "expression.csv"
    _write_table(table, [
        {"gene": "BRCA1", "sample": "S1", "count": "10"},
        {"gene": "BRCA1", "sample": "S2", "count": "12"},
        {"gene": "TP53", "sample": "S1", "count": "3"},
    ], delimiter=",")

    result = await _node_class("pivot_table")().run(
        table=str(table),
        operation="pivot_wide",
        index_column="gene",
        names_from="sample",
        values_from="count",
        fill_value="0",
        output_type="AUTO",
        context=_context(tmp_path, "pivot-auto-csv"),
    )

    output_path = Path(result[0])
    assert output_path.name == "expression.wide.csv"
    rows = _read_table(output_path, delimiter=",")
    assert rows == [
        {"gene": "BRCA1", "S1": "10", "S2": "12"},
        {"gene": "TP53", "S1": "3", "S2": "0"},
    ]


@pytest.mark.asyncio
async def test_reshape_table_long_direction_melts_wide_tsv(tmp_path: Path) -> None:
    table = tmp_path / "counts.tsv"
    _write_table(table, [
        {"gene": "BRCA1", "S1": "10", "S2": "12"},
        {"gene": "TP53", "S1": "3", "S2": "8"},
    ])

    result = await _node_class("reshape_table")().run(
        table=str(table),
        direction="long",
        id_vars="gene",
        value_vars="S1,S2",
        names_to="sample",
        values_to="count",
        output_type="TSV",
        context=_context(tmp_path, "reshape-long"),
    )

    output_path = Path(result[0])
    assert output_path.name == "counts.long.tsv"
    assert output_path.parent.name == "reshape_table"
    rows = _read_table(output_path)
    assert list(rows[0]) == ["gene", "sample", "count"]
    assert rows == [
        {"gene": "BRCA1", "sample": "S1", "count": "10"},
        {"gene": "BRCA1", "sample": "S2", "count": "12"},
        {"gene": "TP53", "sample": "S1", "count": "3"},
        {"gene": "TP53", "sample": "S2", "count": "8"},
    ]


@pytest.mark.asyncio
async def test_reshape_table_wide_direction_pivots_long_tsv(tmp_path: Path) -> None:
    table = tmp_path / "expression.tsv"
    _write_table(table, [
        {"gene": "BRCA1", "sample": "S1", "count": "10"},
        {"gene": "BRCA1", "sample": "S2", "count": "12"},
        {"gene": "TP53", "sample": "S1", "count": "3"},
    ])

    result = await _node_class("reshape_table")().run(
        table=str(table),
        direction="wide",
        id_vars="gene",
        names_from="sample",
        values_from="count",
        fill_value="0",
        output_type="TSV",
        context=_context(tmp_path, "reshape-wide"),
    )

    output_path = Path(result[0])
    assert output_path.name == "expression.wide.tsv"
    assert output_path.parent.name == "reshape_table"
    rows = _read_table(output_path)
    assert list(rows[0]) == ["gene", "S1", "S2"]
    assert rows == [
        {"gene": "BRCA1", "S1": "10", "S2": "12"},
        {"gene": "TP53", "S1": "3", "S2": "0"},
    ]


@pytest.mark.asyncio
async def test_reshape_table_rejects_unknown_direction(tmp_path: Path) -> None:
    table = tmp_path / "counts.tsv"
    _write_table(table, [{"gene": "BRCA1", "S1": "10"}])

    with pytest.raises(ValueError, match="Unsupported reshape direction: sideways"):
        await _node_class("reshape_table")().run(
            table=str(table),
            direction="sideways",
            id_vars="gene",
            context=_context(tmp_path, "reshape-invalid"),
        )
