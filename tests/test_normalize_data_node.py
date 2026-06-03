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


def test_normalize_data_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["normalize_data"]["display_name"] == "Normalize Data"
    assert info["normalize_data"]["category"] == "data_transform"
    assert info["normalize_data"]["output_name"] == ["normalized_table"]
    assert info["normalize_data"]["output"] == ["CSV"]


@pytest.mark.asyncio
async def test_normalize_data_min_max_across_columns_preserves_id_columns(tmp_path: Path) -> None:
    table = tmp_path / "expression.tsv"
    _write_table(table, [
        {"gene": "A", "s1": "10", "s2": "20"},
        {"gene": "B", "s1": "5", "s2": "5"},
    ])

    result = await _node_class("normalize_data")().run(
        table=str(table),
        method="min_max",
        id_columns="gene",
        axis="columns",
        min_max_range="0,1",
        output_type="TSV",
        context=_context(tmp_path, "min-max"),
    )

    output_path = Path(result[0])
    assert output_path.name == "expression.norm_min_max.tsv"
    assert _read_table(output_path) == [
        {"gene": "A", "s1": "0", "s2": "1"},
        {"gene": "B", "s1": "0", "s2": "0"},
    ]


@pytest.mark.asyncio
async def test_normalize_data_z_score_across_rows_normalizes_each_sample_column(tmp_path: Path) -> None:
    table = tmp_path / "counts.tsv"
    _write_table(table, [
        {"gene": "A", "s1": "1", "s2": "10"},
        {"gene": "B", "s1": "2", "s2": "20"},
        {"gene": "C", "s1": "3", "s2": "30"},
    ])

    result = await _node_class("normalize_data")().run(
        table=str(table),
        method="z_score",
        id_columns="gene",
        axis="rows",
        output_type="TSV",
        context=_context(tmp_path, "z-score"),
    )

    rows = _read_table(result[0])
    assert rows[0]["gene"] == "A"
    assert rows[1]["gene"] == "B"
    assert rows[2]["gene"] == "C"
    assert [rows[index]["s1"] for index in range(3)] == ["-1", "0", "1"]
    assert [rows[index]["s2"] for index in range(3)] == ["-1", "0", "1"]


@pytest.mark.asyncio
async def test_normalize_data_log2_and_cpm_methods(tmp_path: Path) -> None:
    table = tmp_path / "counts.tsv"
    _write_table(table, [
        {"gene": "A", "s1": "3", "s2": "1"},
        {"gene": "B", "s1": "1", "s2": "3"},
    ])

    log_result = await _node_class("normalize_data")().run(
        table=str(table),
        method="log2",
        id_columns="gene",
        pseudocount=1,
        output_type="TSV",
        context=_context(tmp_path, "log2"),
    )
    assert _read_table(log_result[0]) == [
        {"gene": "A", "s1": "2", "s2": "1"},
        {"gene": "B", "s1": "1", "s2": "2"},
    ]

    cpm_result = await _node_class("normalize_data")().run(
        table=str(table),
        method="cpm",
        id_columns="gene",
        output_type="TSV",
        context=_context(tmp_path, "cpm"),
    )
    assert _read_table(cpm_result[0]) == [
        {"gene": "A", "s1": "750000", "s2": "250000"},
        {"gene": "B", "s1": "250000", "s2": "750000"},
    ]
