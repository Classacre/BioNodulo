from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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


def _read_lines(path: str | Path) -> list[str]:
    return Path(path).read_text(encoding="utf-8").splitlines()


def test_sample_subset_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["sample_subset"]["display_name"] == "Sample Subset"
    assert info["sample_subset"]["category"] == "data_transform"
    assert info["sample_subset"]["output_name"] == ["subset_file"]
    assert info["sample_subset"]["output"] == ["FILE"]
    assert info["sample_subset"]["python_class"] == (
        "bionodulo.nodes.builtin.sample_subset.SampleSubsetNode"
    )


@pytest.mark.asyncio
async def test_sample_subset_random_tsv_is_deterministic_and_preserves_header(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    table.write_text(
        "sample\tcondition\n"
        "s1\tcontrol\n"
        "s2\ttreated\n"
        "s3\tcontrol\n"
        "s4\ttreated\n"
        "s5\tcontrol\n",
        encoding="utf-8",
    )

    node_class = _node_class("sample_subset")
    first = await node_class().run(
        file=str(table),
        n=3,
        mode="random",
        seed=7,
        context=_context(tmp_path, "first"),
    )
    second = await node_class().run(
        file=str(table),
        n=3,
        mode="random",
        seed=7,
        context=_context(tmp_path, "second"),
    )

    first_path = Path(first[0])
    assert first_path == tmp_path / "first" / "sample_subset" / "samples.subset.tsv"
    assert _read_lines(first_path)[0] == "sample\tcondition"
    assert _read_lines(first_path) == _read_lines(second[0])
    assert len(_read_lines(first_path)) == 4


@pytest.mark.asyncio
async def test_sample_subset_first_n_fasta_records(tmp_path: Path) -> None:
    fasta = tmp_path / "reads.fa"
    fasta.write_text(">r1\nAAAA\n>r2\nCCCC\n>r3\nGGGG\n", encoding="utf-8")

    result = await _node_class("sample_subset")().run(
        file=str(fasta),
        n=2,
        mode="first_n",
        context=_context(tmp_path, "fasta"),
    )

    output_path = Path(result[0])
    assert output_path == tmp_path / "fasta" / "sample_subset" / "reads.subset.fa"
    assert _read_lines(output_path) == [">r1", "AAAA", ">r2", "CCCC"]


@pytest.mark.asyncio
async def test_sample_subset_first_n_fastq_records(tmp_path: Path) -> None:
    fastq = tmp_path / "reads.fastq"
    fastq.write_text(
        "@r1\nAAAA\n+\n!!!!\n"
        "@r2\nCCCC\n+\n####\n"
        "@r3\nGGGG\n+\n$$$$\n",
        encoding="utf-8",
    )

    result = await _node_class("sample_subset")().run(
        file=str(fastq),
        n=2,
        mode="first_n",
        context=_context(tmp_path, "fastq"),
    )

    output_path = Path(result[0])
    assert output_path == tmp_path / "fastq" / "sample_subset" / "reads.subset.fastq"
    assert _read_lines(output_path) == [
        "@r1", "AAAA", "+", "!!!!",
        "@r2", "CCCC", "+", "####",
    ]


@pytest.mark.asyncio
async def test_sample_subset_every_nth_fasta_records(tmp_path: Path) -> None:
    fasta = tmp_path / "proteins.fasta"
    fasta.write_text(
        ">p1\nAAA\n"
        ">p2\nCCC\n"
        ">p3\nGGG\n"
        ">p4\nTTT\n"
        ">p5\nNNN\n",
        encoding="utf-8",
    )

    result = await _node_class("sample_subset")().run(
        file=str(fasta),
        n=99,
        mode="every_nth",
        every_n=2,
        context=_context(tmp_path, "every"),
    )

    output_path = Path(result[0])
    assert output_path == tmp_path / "every" / "sample_subset" / "proteins.subset.fasta"
    assert _read_lines(output_path) == [">p2", "CCC", ">p4", "TTT"]


@pytest.mark.asyncio
async def test_sample_subset_stratified_table_sampling_and_output_type(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    table.write_text(
        "sample\tcondition\n"
        "s1\tcase\n"
        "s2\tcase\n"
        "s3\tcase\n"
        "s4\tcontrol\n"
        "s5\tcontrol\n"
        "s6\tcontrol\n",
        encoding="utf-8",
    )

    result = await _node_class("sample_subset")().run(
        file=str(table),
        n=4,
        mode="stratified",
        stratify_column="condition",
        seed=11,
        output_type="CSV",
        context=_context(tmp_path, "stratified"),
    )

    output_path = Path(result[0])
    assert output_path == tmp_path / "stratified" / "sample_subset" / "samples.subset.csv"
    lines = _read_lines(output_path)
    assert lines[0] == "sample,condition"
    assert sum(line.endswith(",case") for line in lines[1:]) == 2
    assert sum(line.endswith(",control") for line in lines[1:]) == 2
