"""Focused join, aggregation, and transposition behavior."""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.builtin.data_transform_family import (
    AggregateByGroupNode,
    JoinTablesNode,
    MergeTablesNode,
    TransposeTableNode,
)


def write_table(path: Path, rows: list[dict[str, Any]], delimiter: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_table(path: str | Path, delimiter: str = "\t") -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


@pytest.mark.asyncio
async def test_merge_tables_infers_each_input_delimiter_and_maps_keys(tmp_path: Path) -> None:
    left = tmp_path / "left.csv"
    right = tmp_path / "right.tsv"
    write_table(left, [{"id": "g1", "value": "2"}, {"id": "g2", "value": "3"}], ",")
    write_table(right, [{"accession": "g1", "value": "annotated"}], "\t")
    result = await MergeTablesNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        table_a=str(left),
        table_b=str(right),
        key_column_a="id",
        key_column_b="accession",
        join_type="left",
        delimiter="auto",
        suffix_a="_left",
        suffix_b="_right",
    )
    assert read_table(result[0]) == [
        {"id": "g1", "value_left": "2", "value_right": "annotated"},
        {"id": "g2", "value_left": "3", "value_right": ""},
    ]


@pytest.mark.asyncio
async def test_join_tables_outer_multi_key_preserves_unmatched_keys(tmp_path: Path) -> None:
    left = tmp_path / "left.tsv"
    right = tmp_path / "right.tsv"
    write_table(left, [{"sample": "S1", "feature": "A", "value": "2"}], "\t")
    write_table(right, [{"sample": "S2", "feature": "B", "value": "5"}], "\t")
    result = await JoinTablesNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        table_a=str(left),
        table_b=str(right),
        join_keys="sample,feature",
        how="outer",
        left_suffix="_a",
        right_suffix="_b",
    )
    assert read_table(result[0]) == [
        {"sample": "S1", "feature": "A", "value_a": "2", "value_b": ""},
        {"sample": "S2", "feature": "B", "value_a": "", "value_b": "5"},
    ]


@pytest.mark.asyncio
async def test_aggregate_by_group_supports_mean_and_count_without_value_column(tmp_path: Path) -> None:
    table = tmp_path / "values.tsv"
    write_table(
        table,
        [
            {"group": "A", "value": "2"},
            {"group": "A", "value": "4"},
            {"group": "B", "value": "10"},
        ],
        "\t",
    )
    mean = await AggregateByGroupNode().run(
        context=SimpleNamespace(node_dir=tmp_path / "mean"),
        table=str(table),
        group_by="group",
        value_column="value",
        operation="mean",
    )
    count = await AggregateByGroupNode().run(
        context=SimpleNamespace(node_dir=tmp_path / "count"),
        table=str(table),
        group_by="group",
        operation="count",
    )
    assert read_table(mean[0]) == [
        {"group": "A", "mean_value": "3"},
        {"group": "B", "mean_value": "10"},
    ]
    assert read_table(count[0]) == [
        {"group": "A", "count_rows": "2"},
        {"group": "B", "count_rows": "1"},
    ]


@pytest.mark.asyncio
async def test_transpose_table_emits_requested_csv_and_rejects_duplicate_ids(tmp_path: Path) -> None:
    table = tmp_path / "matrix.tsv"
    write_table(
        table,
        [{"gene": "g1", "S1": "2", "S2": "3"}, {"gene": "g2", "S1": "4", "S2": "5"}],
        "\t",
    )
    result = await TransposeTableNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        table=str(table),
        id_column="gene",
        new_header="sample",
        output_type="CSV",
    )
    assert read_table(result[0], delimiter=",") == [
        {"sample": "S1", "g1": "2", "g2": "4"},
        {"sample": "S2", "g1": "3", "g2": "5"},
    ]

    duplicate = tmp_path / "duplicate.tsv"
    write_table(duplicate, [{"gene": "g1", "S1": "2"}, {"gene": "g1", "S1": "3"}], "\t")
    with pytest.raises(ValueError, match="duplicate values: g1"):
        await TransposeTableNode().run(
            context=SimpleNamespace(node_dir=tmp_path / "bad"),
            table=str(duplicate),
        )
