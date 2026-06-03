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


def test_split_file_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["split_file"]["display_name"] == "Split File"
    assert info["split_file"]["category"] == "data_transform"
    assert info["split_file"]["output_name"] == ["chunks_dir"]
    assert info["split_file"]["output"] == ["DIRECTORY"]


@pytest.mark.asyncio
async def test_split_file_splits_tsv_by_line_count_preserving_header(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "condition": "case"},
        {"sample": "S2", "condition": "case"},
        {"sample": "S3", "condition": "control"},
    ])

    result = await _node_class("split_file")().run(
        file=str(table),
        split_mode="by_line_count",
        lines_per_chunk=2,
        has_header=True,
        output_type="TSV",
        context=_context(tmp_path, "split-lines"),
    )

    chunks = sorted(Path(result[0]).glob("samples.chunk_*.tsv"))
    assert [path.name for path in chunks] == ["samples.chunk_001.tsv", "samples.chunk_002.tsv"]
    assert chunks[0].read_text(encoding="utf-8") == (
        "sample\tcondition\n"
        "S1\tcase\n"
        "S2\tcase\n"
    )
    assert chunks[1].read_text(encoding="utf-8") == (
        "sample\tcondition\n"
        "S3\tcontrol\n"
    )


@pytest.mark.asyncio
async def test_split_file_splits_tsv_by_column_value(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    _write_table(table, [
        {"sample": "S1", "condition": "case"},
        {"sample": "S2", "condition": "control"},
        {"sample": "S3", "condition": "case"},
    ])

    result = await _node_class("split_file")().run(
        file=str(table),
        split_mode="by_column_value",
        split_column="condition",
        has_header=True,
        output_type="TSV",
        context=_context(tmp_path, "split-column"),
    )

    chunks = {path.name: path.read_text(encoding="utf-8") for path in Path(result[0]).glob("samples.*.tsv")}
    assert chunks == {
        "samples.case.tsv": "sample\tcondition\nS1\tcase\nS3\tcase\n",
        "samples.control.tsv": "sample\tcondition\nS2\tcontrol\n",
    }
