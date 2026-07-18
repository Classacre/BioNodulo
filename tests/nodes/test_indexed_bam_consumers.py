from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.builtin._bam_index import validate_colocated_bam_index
from bionodulo.nodes.builtin.epigenomics import DeepToolsBamCoverageNode
from bionodulo.nodes.builtin.variant import (
    DellyCallNode,
    DellyNode,
    FreeBayesNode,
    GatkHaplotypeCallerNode,
    MantaCallNode,
    MantaNode,
)
from bionodulo.nodes.builtin.visualization import CoveragePlotNode


CLI_NODES = {
    node.NODE_ID: node
    for node in (
        GatkHaplotypeCallerNode,
        FreeBayesNode,
        MantaNode,
        MantaCallNode,
        DellyNode,
        DellyCallNode,
        DeepToolsBamCoverageNode,
    )
}


def _cli_inputs(node_id: str, tmp_path: Path) -> dict[str, Any]:
    bam = tmp_path / "sample.bam"
    inputs: dict[str, Any] = {
        "bam": bam,
        "bam_index": Path(f"{bam}.bai"),
        "output": str(tmp_path / node_id),
    }
    if node_id != "deeptools_bamcoverage":
        inputs["reference"] = tmp_path / "reference.fa"
    if node_id in {"gatk_haplotype_caller", "manta", "manta_call"}:
        inputs["threads"] = 4
    if node_id in {"delly", "delly_call"}:
        inputs["mode"] = "call"
    if node_id == "deeptools_bamcoverage":
        inputs.update({"threads": 4, "normalize_using": "CPM"})
    return inputs


@pytest.mark.parametrize("node_id", tuple(CLI_NODES))
def test_cli_indexed_bam_consumers_require_bai_port(node_id: str) -> None:
    required = CLI_NODES[node_id].INPUT_TYPES()["required"]

    assert required["bam_index"][0] == "BAI"


def test_coverage_plot_exposes_optional_bai_port() -> None:
    optional = CoveragePlotNode.INPUT_TYPES()["optional"]

    assert optional["alignment_index"][0] == "BAI"


@pytest.mark.parametrize("node_id", tuple(CLI_NODES))
def test_cli_indexed_bam_consumers_accept_exact_colocated_pair(
    node_id: str,
    tmp_path: Path,
) -> None:
    assert CLI_NODES[node_id].VALIDATE_INPUTS(_cli_inputs(node_id, tmp_path)) is True


@pytest.mark.parametrize("node_id", tuple(CLI_NODES))
@pytest.mark.parametrize(
    "bad_index",
    [
        None,
        "sample.bai",
        "other/sample.bam.bai",
        "index.bai",
        "unrelated.bam.bai",
    ],
)
def test_cli_indexed_bam_consumers_reject_missing_or_non_colocated_index(
    node_id: str,
    bad_index: str | None,
    tmp_path: Path,
) -> None:
    inputs = _cli_inputs(node_id, tmp_path)
    if bad_index is None:
        inputs.pop("bam_index")
    else:
        inputs["bam_index"] = tmp_path / bad_index

    result = CLI_NODES[node_id].VALIDATE_INPUTS(inputs)

    assert result is not True
    assert "bam_index" in str(result)
    if bad_index is not None:
        assert str(Path(f"{inputs['bam']}.bai")) in str(result)


def test_colocated_validator_normalizes_relative_syntax_lexically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert validate_colocated_bam_index(
        {"bam": "runs/../sample.bam", "bam_index": "./sample.bam.bai"}
    ) is True


def test_colocated_validator_does_not_dereference_symlinks(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    alias_dir = tmp_path / "alias"
    alias_dir.symlink_to(real_dir, target_is_directory=True)
    bam = alias_dir / "sample.bam"

    assert validate_colocated_bam_index(
        {"bam": bam, "bam_index": Path(f"{bam}.bai")}
    ) is True

    result = validate_colocated_bam_index(
        {"bam": bam, "bam_index": real_dir / "sample.bam.bai"}
    )
    assert result is not True
    assert str(Path(f"{bam}.bai")) in str(result)


@pytest.mark.parametrize(
    ("inputs", "expected_key"),
    [
        ({"bam": None, "bam_index": "sample.bam.bai"}, "bam"),
        ({"bam": "", "bam_index": "sample.bam.bai"}, "bam"),
        ({"bam": "sample.bam", "bam_index": ""}, "bam_index"),
        ({"bam": "sample.bam", "bam_index": 42}, "bam_index"),
    ],
)
def test_colocated_validator_rejects_empty_or_non_path_values(
    inputs: dict[str, Any],
    expected_key: str,
) -> None:
    result = validate_colocated_bam_index(inputs)

    assert result is not True
    assert expected_key in str(result)


@pytest.mark.parametrize(
    ("alias", "base"),
    [(MantaCallNode, MantaNode), (DellyCallNode, DellyNode)],
)
def test_alias_classes_inherit_index_contract_and_validation(
    alias: type,
    base: type,
    tmp_path: Path,
) -> None:
    assert alias.INPUT_TYPES() == base.INPUT_TYPES()
    assert "VALIDATE_INPUTS" not in alias.__dict__
    inputs = _cli_inputs(alias.NODE_ID, tmp_path)
    assert alias.VALIDATE_INPUTS(inputs) is True
    inputs["bam_index"] = tmp_path / "sample.bai"
    assert alias.VALIDATE_INPUTS(inputs) is not True


@pytest.mark.parametrize("node_id", tuple(CLI_NODES))
def test_cli_rendered_argv_omits_declared_bai(node_id: str, tmp_path: Path) -> None:
    inputs = _cli_inputs(node_id, tmp_path)
    bam_index = str(inputs["bam_index"])

    command = CLI_NODES[node_id].render_command(inputs)

    assert isinstance(command, list)
    assert str(inputs["bam"]) in command
    assert bam_index not in command


def _install_fake_pysam(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[tuple[str, str, dict[str, Any]]],
) -> None:
    class FakeAlignment:
        def __enter__(self) -> FakeAlignment:
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def pileup(self, *_args: Any, **_kwargs: Any) -> tuple[()]:
            return ()

    fake_pysam = ModuleType("pysam")

    def alignment_file(path: str, mode: str, **kwargs: Any) -> FakeAlignment:
        calls.append((path, mode, kwargs))
        return FakeAlignment()

    fake_pysam.AlignmentFile = alignment_file  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pysam", fake_pysam)


@pytest.mark.asyncio
async def test_coverage_plot_passes_exact_bam_index_to_pysam(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, Any]]] = []
    _install_fake_pysam(monkeypatch, calls)
    bam = tmp_path / "sample.bam"
    bam.write_bytes(b"BAM")
    bam_index = tmp_path / "indexes" / "custom.bai"
    context = SimpleNamespace(node_dir=tmp_path)

    result = await CoveragePlotNode().run(
        alignment=bam,
        alignment_index=bam_index,
        region="chr1:1-11",
        window_size=5,
        format="svg",
        context=context,
    )

    assert calls == [(str(bam), "rb", {"index_filename": str(bam_index)})]
    assert Path(result["outputs"]["coverage_image"]).exists()


@pytest.mark.asyncio
async def test_coverage_plot_rejects_bam_without_index_before_opening_pysam(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_pysam = ModuleType("pysam")

    def unexpected_alignment_file(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("pysam must not be opened without alignment_index")

    fake_pysam.AlignmentFile = unexpected_alignment_file  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pysam", fake_pysam)
    bam = tmp_path / "sample.BAM"
    bam.write_bytes(b"BAM")

    with pytest.raises(ValueError, match="alignment_index.*BAM"):
        await CoveragePlotNode().run(alignment=bam, region="chr1:1-11")


@pytest.mark.asyncio
async def test_coverage_plot_preserves_cram_index_autodiscovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, Any]]] = []
    _install_fake_pysam(monkeypatch, calls)
    cram = tmp_path / "sample.CRAM"
    cram.write_bytes(b"CRAM")

    await CoveragePlotNode().run(
        alignment=cram,
        region="chr1:1-11",
        format="svg",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    assert calls == [(str(cram), "rb", {})]


@pytest.mark.asyncio
async def test_coverage_plot_ignores_bai_port_for_cram(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, Any]]] = []
    _install_fake_pysam(monkeypatch, calls)
    cram = tmp_path / "sample.cram"
    cram.write_bytes(b"CRAM")

    await CoveragePlotNode().run(
        alignment=cram,
        alignment_index=tmp_path / "not-a-cram-index.bai",
        region="chr1:1-11",
        format="svg",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    assert calls == [(str(cram), "rb", {})]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("sample.bedgraph", "chr1\t1\t11\t4\n"),
        ("sample.tsv", "chromosome\tstart\tend\tcoverage\nchr1\t1\t11\t4\n"),
    ],
)
async def test_coverage_plot_non_bam_tables_do_not_require_index(
    filename: str,
    content: str,
    tmp_path: Path,
) -> None:
    alignment = tmp_path / filename
    alignment.write_text(content, encoding="utf-8")

    result = await CoveragePlotNode().run(
        alignment=alignment,
        region="chr1:1-11",
        format="svg",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    assert Path(result["outputs"]["coverage_image"]).exists()


@pytest.mark.asyncio
async def test_coverage_plot_bigwig_does_not_require_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeBigWig:
        def stats(self, *_args: Any, **_kwargs: Any) -> list[float]:
            return [3.0]

        def close(self) -> None:
            return None

    fake_bigwig = ModuleType("pyBigWig")
    fake_bigwig.open = lambda _path: FakeBigWig()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyBigWig", fake_bigwig)
    bigwig = tmp_path / "sample.bw"
    bigwig.write_bytes(b"BW")

    result = await CoveragePlotNode().run(
        alignment=bigwig,
        region="chr1:1-11",
        format="svg",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    assert Path(result["outputs"]["coverage_image"]).exists()


def test_generated_catalog_exposes_indexed_bam_contracts() -> None:
    root = Path(__file__).resolve().parents[2]
    index = json.loads((root / "bionodulo/nodes/node_index.json").read_text())
    metadata = json.loads((root / "bionodulo/nodes/node_metadata.json").read_text())

    assert len(index) == 943
    assert metadata["samtools_index"]["output"] == ["BAM", "BAI"]
    assert metadata["samtools_index"]["output_name"] == ["indexed_bam", "bai"]
    for node_id in CLI_NODES:
        assert metadata[node_id]["input"]["required"]["bam_index"][0] == "BAI"
    assert metadata["coverage_plot"]["input"]["optional"]["alignment_index"][0] == "BAI"
