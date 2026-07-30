"""STARsolo replaces Cell Ranger, which cannot be fetched unattended.

10x distributes Cell Ranger under a click-through licence: the download URL
answers 403 to automation and no conda channel may redistribute it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.alignment_family.starsolo_count import STARsoloCountNode


def _inputs(tmp_path: Path, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "genome_dir": "/idx",
        "cdna_fastq": "/reads/R2.fastq.gz",
        "barcode_fastq": "/reads/R1.fastq.gz",
        "threads": 4,
        "output": str(tmp_path / "starsolo_count"),
    }
    base.update(overrides)
    return base


def test_the_planned_output_is_the_path_the_command_writes(tmp_path: Path) -> None:
    """The bug this guards: the runner already appends NODE_ID to `output`.

    Appending it again in render_command produced
    .../starsolo_count/starsolo_count/, so STAR exited 0 while every planned
    output was missing -- which only surfaced after a full cloud run.
    """
    inputs = _inputs(tmp_path)
    planned = STARsoloCountNode.PLAN_OUTPUTS(inputs, tmp_path)
    command = " ".join(STARsoloCountNode.render_command(inputs))

    prefix = f"{tmp_path / 'starsolo_count'}/"
    assert f"--outFileNamePrefix {prefix}" in command
    assert planned[0] == tmp_path / "starsolo_count" / "Solo.out" / "Gene" / "filtered"
    assert str(planned[0]) in command, "the gzip step must target the planned directory"
    assert "starsolo_count/starsolo_count" not in command


def test_the_cdna_read_comes_first(tmp_path: Path) -> None:
    """Reversing the reads yields an all-empty matrix rather than an error."""
    command = STARsoloCountNode.render_command(_inputs(tmp_path))
    index = command.index("--readFilesIn")

    assert command[index + 1] == "/reads/R2.fastq.gz"
    assert command[index + 2] == "/reads/R1.fastq.gz"


def test_the_matrix_is_gzipped_into_the_cell_ranger_v3_layout(tmp_path: Path) -> None:
    """scanpy's read_10x_mtx looks for matrix.mtx.gz; STARsolo writes it bare."""
    command = STARsoloCountNode.render_command(_inputs(tmp_path))

    assert "gzip" in command
    assert STARsoloCountNode.MATRIX_FILES == (
        "matrix.mtx.gz",
        "features.tsv.gz",
        "barcodes.tsv.gz",
    )
    for subdir in ("filtered", "raw"):
        for name in STARsoloCountNode.RAW_MATRIX_NAMES:
            assert any(token.endswith(f"{subdir}/{name}") for token in command)


def test_umi_start_follows_the_barcode(tmp_path: Path) -> None:
    command = STARsoloCountNode.render_command(_inputs(tmp_path, cb_length=16, umi_length=10))

    assert command[command.index("--soloCBlen") + 1] == "16"
    assert command[command.index("--soloUMIlen") + 1] == "10"
    assert command[command.index("--soloUMIstart") + 1] == "17"


def test_an_incomplete_star_index_is_named_precisely(tmp_path: Path) -> None:
    """The public cellranger-tiny-ref has star/Genome and star/SAindex but no star/SA."""
    index = tmp_path / "partial_index"
    index.mkdir()
    for name in ("Genome", "SAindex", "chrName.txt", "genomeParameters.txt"):
        (index / name).write_text("x", encoding="utf-8")

    result = STARsoloCountNode.VALIDATE_INPUTS(_inputs(tmp_path, genome_dir=str(index)))

    assert result is not True
    assert "SA" in str(result)


def test_a_geometry_outside_the_valid_range_is_rejected(tmp_path: Path) -> None:
    assert STARsoloCountNode.VALIDATE_INPUTS(_inputs(tmp_path, cb_length=0)) is not True
    assert STARsoloCountNode.VALIDATE_INPUTS(_inputs(tmp_path, umi_length=200)) is not True


def test_an_unknown_cell_filter_is_rejected(tmp_path: Path) -> None:
    result = STARsoloCountNode.VALIDATE_INPUTS(_inputs(tmp_path, cell_filter="MagicFilter"))
    assert result is not True


def test_a_zero_cell_matrix_is_rejected(tmp_path: Path) -> None:
    """An empty matrix reads as success and plots nothing."""
    import gzip

    filtered = tmp_path / "filtered"
    filtered.mkdir()
    (filtered / "matrix.mtx.gz").write_bytes(b"x")
    with gzip.open(filtered / "barcodes.tsv.gz", "wt", encoding="utf-8") as handle:
        handle.write("")

    with pytest.raises(ValueError, match="zero cells"):
        STARsoloCountNode.VERIFY_OUTPUTS({"index": "x"}, [filtered])


def test_a_missing_matrix_is_rejected(tmp_path: Path) -> None:
    filtered = tmp_path / "filtered"
    filtered.mkdir()

    with pytest.raises(ValueError, match="did not write"):
        STARsoloCountNode.VERIFY_OUTPUTS({}, [filtered])
