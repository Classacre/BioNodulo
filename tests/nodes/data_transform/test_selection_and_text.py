"""Focused filtering, selection, replacement, and sorting behavior."""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.builtin.data_transform_family import (
    ExtractColumnsNode,
    FilterRowsNode,
    ReplaceTextNode,
    SortFileNode,
)


def write_table(path: Path, rows: list[dict[str, Any]], delimiter: str = "\t") -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_table(path: str | Path, delimiter: str = "\t") -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


@pytest.mark.asyncio
async def test_filter_rows_combines_predicates_and_preserves_requested_csv(tmp_path: Path) -> None:
    table = tmp_path / "results.csv"
    write_table(
        table,
        [
            {"gene": "g1", "padj": "0.01", "log2FoldChange": "2.0"},
            {"gene": "g2", "padj": "0.20", "log2FoldChange": "1.0"},
            {"gene": "g3", "padj": "0.03", "log2FoldChange": ""},
        ],
        delimiter=",",
    )

    result = await FilterRowsNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        table=str(table),
        column="padj",
        operator="<=",
        value="0.05",
        column_2="log2FoldChange",
        operator_2="is_not_empty",
        logical_op="AND",
        output_type="CSV",
    )

    assert Path(result[0]).name == "results.filtered.csv"
    assert read_table(result[0], delimiter=",") == [{"gene": "g1", "padj": "0.01", "log2FoldChange": "2.0"}]
    assert (
        FilterRowsNode.VALIDATE_INPUTS({"table": "x.tsv", "column": "x", "operator": ">", "value": "not-a-number"})
        == "Input 'value' must be a finite number for greater_than"
    )


@pytest.mark.asyncio
async def test_extract_columns_reorders_renames_and_rejects_ambiguous_outputs(tmp_path: Path) -> None:
    table = tmp_path / "quant.tsv"
    write_table(
        table,
        [
            {"Name": "tx1", "TPM": "2.5", "NumReads": "10"},
            {"Name": "tx2", "TPM": "3.0", "NumReads": "12"},
        ],
    )
    result = await ExtractColumnsNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        table=str(table),
        columns="Name,TPM,NumReads",
        rename_to="target_id,tpm,reads",
        output_type="TSV",
    )
    assert read_table(result[0]) == [
        {"target_id": "tx1", "tpm": "2.5", "reads": "10"},
        {"target_id": "tx2", "tpm": "3.0", "reads": "12"},
    ]

    with pytest.raises(ValueError, match="Output column names must be unique"):
        await ExtractColumnsNode().run(
            context=SimpleNamespace(node_dir=tmp_path / "bad"),
            table=str(table),
            columns="Name,TPM",
            rename_to="value,value",
        )


@pytest.mark.asyncio
async def test_replace_text_distinguishes_literal_replacement_from_regex_backreferences(
    tmp_path: Path,
) -> None:
    source = tmp_path / "input.txt"
    source.write_text("sample $1\ncontrol $1\n", encoding="utf-8")
    literal = await ReplaceTextNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        file=str(source),
        search="$1",
        replace=r"\1",
        use_regex=False,
    )
    assert Path(literal[0]).read_text(encoding="utf-8") == "sample \\1\ncontrol \\1\n"
    assert (
        ReplaceTextNode.VALIDATE_INPUTS(
            {"file": "input.txt", "search": "x", "replace": "y", "output_extension": "../txt"}
        )
        == "Input 'output_extension' must be a filename extension without path separators"
    )


@pytest.mark.asyncio
async def test_sort_file_is_numeric_descending_and_stable_for_equal_keys(tmp_path: Path) -> None:
    source = tmp_path / "scores.tsv"
    source.write_text("sample\tscore\nA\t2\nB\t10\nC\t10\n", encoding="utf-8")
    result = await SortFileNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        file=str(source),
        sort_column="score",
        sort_type="numeric",
        ascending=False,
        separator="tab",
        output_type="TSV",
    )
    assert Path(result[0]).read_text(encoding="utf-8") == ("sample\tscore\nB\t10\nC\t10\nA\t2\n")
