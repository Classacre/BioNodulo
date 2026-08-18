"""Focused table conversion, FASTA serialization, field setting, and deduplication."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.builtin.data_transform_family import (
    DeduplicateNode,
    FormatConverterNode,
    SetFieldsNode,
    TSVToFastaNode,
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
async def test_format_converter_is_table_only_and_preserves_header_only_tables(tmp_path: Path) -> None:
    csv_path = tmp_path / "records.csv"
    csv_path.write_text("id,value\nA,2\n", encoding="utf-8")
    result = await FormatConverterNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        input_file=str(csv_path),
        output_format="json",
    )
    assert json.loads(Path(result[0]).read_text(encoding="utf-8")) == [{"id": "A", "value": "2"}]

    header_only = tmp_path / "empty.csv"
    header_only.write_text("id,value\n", encoding="utf-8")
    converted = await FormatConverterNode().run(
        context=SimpleNamespace(node_dir=tmp_path / "header"),
        input_file=str(header_only),
        output_format="tsv",
    )
    assert Path(converted[0]).read_text(encoding="utf-8") == "id\tvalue\n"
    assert (
        FormatConverterNode.VALIDATE_INPUTS({"input_file": "reads.fastq", "output_format": "FASTA"})
        == "Input 'output_format' must be one of: csv, tsv, json, jsonl"
    )


@pytest.mark.asyncio
async def test_tsv_to_fasta_normalizes_ids_and_wraps_sequences(tmp_path: Path) -> None:
    table = tmp_path / "sequences.tsv"
    write_table(table, [{"id": "sample one", "sequence": "ac gt ac"}])
    result = await TSVToFastaNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        table=str(table),
        id_column="id",
        seq_column="sequence",
        line_width=4,
    )
    assert Path(result[0]).read_text(encoding="utf-8") == ">sample_one\nACGT\nAC\n"


@pytest.mark.asyncio
async def test_set_fields_applies_direct_placeholders_and_rejects_format_directives(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    write_table(table, [{"sample": "S1", "condition": "case"}])
    result = await SetFieldsNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        table=str(table),
        assignments='{"label":"{sample}_{condition}","batch":2}',
        field_order="sample,label,batch",
    )
    assert read_table(result[0]) == [{"sample": "S1", "label": "S1_case", "batch": "2"}]

    with pytest.raises(ValueError, match="only support direct"):
        await SetFieldsNode().run(
            context=SimpleNamespace(node_dir=tmp_path / "bad"),
            table=str(table),
            assignments='{"label":"{sample!r}"}',
        )


@pytest.mark.asyncio
async def test_deduplicate_table_always_writes_retained_and_duplicate_artifacts(tmp_path: Path) -> None:
    table = tmp_path / "variants.tsv"
    write_table(
        table,
        [
            {"id": "v1", "sample": "A"},
            {"id": "v1", "sample": "B"},
            {"id": "v2", "sample": "C"},
        ],
    )
    retained, duplicates = await DeduplicateNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        table=str(table),
        subset_columns="id",
        keep="first",
    )
    assert read_table(retained) == [
        {"id": "v1", "sample": "A"},
        {"id": "v2", "sample": "C"},
    ]
    assert read_table(duplicates) == [{"id": "v1", "sample": "B"}]
    assert Path(retained) != Path(duplicates)


@pytest.mark.asyncio
async def test_deduplicate_fasta_uses_uppercase_sequence_identity(tmp_path: Path) -> None:
    fasta = tmp_path / "contigs.fasta"
    fasta.write_text(">a\nacgt\n>b\nACGT\n>c\nTTAA\n", encoding="utf-8")
    retained, duplicates = await DeduplicateNode().run(
        context=SimpleNamespace(node_dir=tmp_path),
        table=str(fasta),
        keep="first",
    )
    assert Path(retained).read_text(encoding="utf-8") == ">a\nACGT\n>c\nTTAA\n"
    assert Path(duplicates).read_text(encoding="utf-8") == ">b\nACGT\n"


@pytest.mark.asyncio
async def test_format_converter_jsonl_roundtrip_preserves_records(tmp_path: Path) -> None:
    source = tmp_path / "rows.tsv"
    source.write_text("id\tarm\tk_deg\nm1\tdeg_Mg_pH10\t0.5\nm2\tdeg_Mg_pH10\t1.5\n", encoding="utf-8")

    jsonl_path, = await FormatConverterNode().run(
        input_file=str(source), output_format="jsonl", context=SimpleNamespace(node_dir=tmp_path)
    )
    lines = Path(jsonl_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first == {"id": "m1", "arm": "deg_Mg_pH10", "k_deg": "0.5"}

    back_path, = await FormatConverterNode().run(
        input_file=jsonl_path, output_format="tsv", context=SimpleNamespace(node_dir=tmp_path / "back")
    )
    assert Path(back_path).read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
