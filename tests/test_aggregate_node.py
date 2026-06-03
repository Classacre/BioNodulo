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


def test_aggregate_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["aggregate"]["display_name"] == "Aggregate"
    assert info["aggregate"]["category"] == "data_transform"
    assert info["aggregate"]["output_name"] == ["aggregated_table"]
    assert info["aggregate"]["output"] == ["CSV"]


@pytest.mark.asyncio
async def test_aggregate_groups_by_multiple_columns_and_sums_values(tmp_path: Path) -> None:
    table = tmp_path / "counts.tsv"
    _write_table(table, [
        {"condition": "case", "gene": "A", "count": "10"},
        {"condition": "case", "gene": "A", "count": "5"},
        {"condition": "case", "gene": "B", "count": "2"},
        {"condition": "control", "gene": "A", "count": "7"},
    ])

    result = await _node_class("aggregate")().run(
        table=str(table),
        group_columns="condition,gene",
        agg_column="count",
        agg_function="sum",
        output_type="TSV",
        context=_context(tmp_path, "aggregate-sum"),
    )

    output_path = Path(result[0])
    assert output_path.name == "counts.aggregated.tsv"
    assert _read_table(output_path) == [
        {"condition": "case", "gene": "A", "sum_count": "15"},
        {"condition": "case", "gene": "B", "sum_count": "2"},
        {"condition": "control", "gene": "A", "sum_count": "7"},
    ]


@pytest.mark.asyncio
async def test_aggregate_supports_second_aggregation(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"condition": "case", "sample": "S1", "count": "10"},
        {"condition": "case", "sample": "S1", "count": "14"},
        {"condition": "case", "sample": "S2", "count": "4"},
        {"condition": "control", "sample": "S3", "count": "8"},
    ])

    result = await _node_class("aggregate")().run(
        table=str(table),
        group_columns="condition",
        agg_column="count",
        agg_function="mean",
        agg_column_2="sample",
        agg_function_2="nunique",
        output_type="TSV",
        context=_context(tmp_path, "aggregate-two"),
    )

    assert _read_table(result[0]) == [
        {"condition": "case", "mean_count": "9.333333333333334", "nunique_sample": "2"},
        {"condition": "control", "mean_count": "8", "nunique_sample": "1"},
    ]
