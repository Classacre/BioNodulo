from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.single_cell_spatial_family.cellranger_count import (
    CellRangerCountNode,
)


PINNED_REQUIRED_FILES = (
    "reference.json",
    "fasta/genome.fa",
    "star/chrLength.txt",
    "star/chrNameLength.txt",
    "star/chrName.txt",
    "star/chrStart.txt",
    "star/Genome",
    "star/genomeParameters.txt",
    "star/SA",
    "star/SAindex",
)
PINNED_GTF_FILES = ("genes/genes.gtf", "genes/genes.gtf.gz")


def _materialize_reference(root: Path, *, compressed_gtf: bool = False) -> Path:
    root.mkdir(parents=True)
    for relative in CellRangerCountNode.REFERENCE_REQUIRED_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic")
    gtf = root / ("genes/genes.gtf.gz" if compressed_gtf else "genes/genes.gtf")
    gtf.parent.mkdir(parents=True, exist_ok=True)
    gtf.write_bytes(b"synthetic")
    return root


def test_reference_preflight_pins_exact_cellranger_9_0_1_sibling_set() -> None:
    assert CellRangerCountNode.REFERENCE_REQUIRED_FILES == PINNED_REQUIRED_FILES
    assert CellRangerCountNode.REFERENCE_GTF_FILES == PINNED_GTF_FILES
    assert "lib/python/cellranger/preflight.py:check_refdata" in CellRangerCountNode.UPSTREAM_SOURCE
    assert "lib/python/cellranger/constants.py" in (
        CellRangerCountNode.SOURCE_AUTHORITIES["reference_preflight"]
    )


@pytest.mark.parametrize("compressed_gtf", [False, True])
def test_reference_preflight_accepts_pinned_sibling_layout(
    tmp_path: Path, compressed_gtf: bool
) -> None:
    reference = _materialize_reference(tmp_path / "ref", compressed_gtf=compressed_gtf)

    CellRangerCountNode.PREPARE_EXECUTION({"transcriptome": str(reference)}, [])


@pytest.mark.parametrize(
    "missing",
    PINNED_REQUIRED_FILES,
)
def test_reference_preflight_rejects_missing_required_file(
    tmp_path: Path, missing: str
) -> None:
    reference = _materialize_reference(tmp_path / "ref")
    (reference / missing).unlink()

    with pytest.raises(ValueError, match=rf"{missing.replace('/', r'[/]')}"):
        CellRangerCountNode.PREPARE_EXECUTION({"transcriptome": str(reference)}, [])


def test_reference_preflight_requires_one_gene_annotation_variant(tmp_path: Path) -> None:
    reference = _materialize_reference(tmp_path / "ref")
    (reference / "genes/genes.gtf").unlink()

    with pytest.raises(ValueError, match=r"genes/genes\.gtf or genes/genes\.gtf\.gz"):
        CellRangerCountNode.PREPARE_EXECUTION({"transcriptome": str(reference)}, [])


def test_reference_preflight_rejects_materialized_non_directory(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    reference.write_bytes(b"not a directory")

    with pytest.raises(ValueError, match="must be a directory"):
        CellRangerCountNode.PREPARE_EXECUTION({"transcriptome": str(reference)}, [])
