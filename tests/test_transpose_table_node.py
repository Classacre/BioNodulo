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


def test_transpose_table_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["transpose_table"]["display_name"] == "Transpose Table"
    assert info["transpose_table"]["category"] == "data_transform"
    assert info["transpose_table"]["output_name"] == ["transposed_table"]
    assert info["transpose_table"]["output"] == ["CSV"]
    assert info["transpose_table"]["python_class"] == (
        "bionodulo.nodes.builtin.data_transform.TransposeTableNode"
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


@pytest.mark.asyncio
async def test_transpose_table_preserves_row_labels_from_explicit_id_column(tmp_path: Path) -> None:
    table = tmp_path / "expression.tsv"
    _write_table(table, [
        {"description": "tumor suppressor", "gene_id": "BRCA1", "S1": "10", "S2": "12"},
        {"description": "cell cycle", "gene_id": "TP53", "S1": "3", "S2": "8"},
    ])

    result = await _node_class("transpose_table")().run(
        table=str(table),
        id_column="gene_id",
        new_header="sample",
        output_type="TSV",
        context=_context(tmp_path, "transpose-id"),
    )

    output_path = Path(result[0])
    assert output_path.name == "expression.transposed.tsv"
    rows = _read_table(output_path)
    assert list(rows[0]) == ["sample", "BRCA1", "TP53"]
    assert rows == [
        {"sample": "description", "BRCA1": "tumor suppressor", "TP53": "cell cycle"},
        {"sample": "S1", "BRCA1": "10", "TP53": "3"},
        {"sample": "S2", "BRCA1": "12", "TP53": "8"},
    ]
