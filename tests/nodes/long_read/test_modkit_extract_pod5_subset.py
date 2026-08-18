"""Focused contracts for modkit_extract argv/validation and pod5_subset selection."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.builtin.long_read_family import (
    ModkitExtractNode,
    Pod5SubsetNode,
)


def test_modkit_extract_pins_modkit_064_source_and_package() -> None:
    assert ModkitExtractNode.PACKAGE_CONSTRAINT == "ont-modkit = 0.6.4"
    assert ModkitExtractNode.REQUIRED_CONDA_PACKAGES == ["ont-modkit"]
    assert ModkitExtractNode.REQUIRED_EXECUTABLES == ["modkit"]
    assert ModkitExtractNode.GIT_COMMIT == "cd85862f71d3bfc289f12adc1052a2e574c95e0f"
    assert ModkitExtractNode.SOURCE_TAG == "v0.6.4"
    assert ModkitExtractNode.DOCUMENTATION_URL == "https://nanoporetech.github.io/modkit/intro_extract.html"
    assert ModkitExtractNode.SHELL is False
    assert ModkitExtractNode.REQUIRED_PATH_INPUTS == ("bam", "bam_index")
    assert ModkitExtractNode.OUTPUT_FILENAMES == ("extracted.tsv",)


def test_modkit_extract_renders_calls_mode_with_documented_filters() -> None:
    command = ModkitExtractNode.render_command(
        {
            "bam": "/data/calls.sorted.bam",
            "bam_index": "/data/calls.sorted.bam.bai",
            "mode": "calls",
            "threads": 8,
            "region": "chr20",
            "num_reads": 1000,
            "filter_threshold": "A:0.8",
            "mod_threshold": "a:0.9",
            "output": "/tmp/run/modkit_extract",
        }
    )
    assert command == [
        "modkit",
        "extract",
        "calls",
        "/data/calls.sorted.bam",
        "/tmp/run/modkit_extract/extracted.tsv",
        "--threads",
        "8",
        "--num-reads",
        "1000",
        "--region",
        "chr20",
        "--filter-threshold",
        "A:0.8",
        "--mod-threshold",
        "a:0.9",
    ]


def test_modkit_extract_renders_full_mode_defaults_without_optional_flags() -> None:
    command = ModkitExtractNode.render_command(
        {
            "bam": "/data/calls.sorted.bam",
            "bam_index": "/data/calls.sorted.bam.bai",
            "output": "/tmp/run/modkit_extract",
        }
    )
    assert command == [
        "modkit",
        "extract",
        "full",
        "/data/calls.sorted.bam",
        "/tmp/run/modkit_extract/extracted.tsv",
        "--threads",
        "4",
    ]


def test_modkit_extract_renders_repeated_motif_pairs_with_reference() -> None:
    command = ModkitExtractNode.render_command(
        {
            "bam": "/data/calls.sorted.bam",
            "bam_index": "/data/calls.sorted.bam.bai",
            "motif": "CG,0;DRACH,2",
            "cpg": True,
            "reference": "/refs/reference.fa",
            "reference_index": "/refs/reference.fa.fai",
            "output": "/tmp/run/modkit_extract",
        }
    )
    assert command == [
        "modkit",
        "extract",
        "full",
        "/data/calls.sorted.bam",
        "/tmp/run/modkit_extract/extracted.tsv",
        "--threads",
        "4",
        "--reference",
        "/refs/reference.fa",
        "--motif",
        "CG",
        "0",
        "--motif",
        "DRACH",
        "2",
        "--cpg",
    ]


def test_modkit_extract_validates_colocated_sidecars_and_mode_gating() -> None:
    base = {
        "bam": "/data/calls.sorted.bam",
        "bam_index": "/data/calls.sorted.bam.bai",
    }
    assert ModkitExtractNode.VALIDATE_INPUTS(base) is True
    mismatch = ModkitExtractNode.VALIDATE_INPUTS({**base, "bam_index": "/data/calls.bai"})
    assert mismatch.startswith(
        "Input 'bam_index' must be the exact colocated index for input 'bam'"
    )
    assert "calls.sorted.bam.bai" in str(mismatch)
    assert ModkitExtractNode.VALIDATE_INPUTS({**base, "cpg": True}) == (
        "Inputs 'reference' and 'reference_index' are required for motif annotation"
    )
    assert ModkitExtractNode.VALIDATE_INPUTS({**base, "motif": "CG,0"}) == (
        "Inputs 'reference' and 'reference_index' are required for motif annotation"
    )
    assert ModkitExtractNode.VALIDATE_INPUTS({**base, "filter_threshold": "0.7"}).startswith(
        "Input 'filter_threshold' is only valid with mode 'calls'"
    )
    assert ModkitExtractNode.VALIDATE_INPUTS({**base, "mode": "read-stats"}).startswith(
        "Input 'mode' must be one of"
    )
    assert ModkitExtractNode.VALIDATE_INPUTS({**base, "motif": "CG"}).startswith(
        "Input 'motif' must be motif:offset pairs"
    )
    with_reference = {
        **base,
        "reference": "/refs/reference.fa",
        "reference_index": "/refs/reference.1.fai",
    }
    reference_mismatch = ModkitExtractNode.VALIDATE_INPUTS(with_reference)
    assert reference_mismatch.startswith(
        "Input 'reference_index' must be the exact colocated index for input 'reference'"
    )
    assert "reference.fa.fai" in str(reference_mismatch)


def test_modkit_extract_prepares_bam_and_reference_sibling_pairs(tmp_path: Path) -> None:
    bam = tmp_path / "source" / "calls.sorted.bam"
    bam_index = Path(f"{bam}.bai")
    reference = tmp_path / "source" / "reference.fa"
    reference_index = Path(f"{reference}.fai")
    for path in (bam, bam_index, reference, reference_index):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.name, encoding="utf-8")

    inputs = {
        "bam": str(bam),
        "bam_index": str(bam_index),
        "reference": str(reference),
        "reference_index": str(reference_index),
        "motif": "CG,0",
    }
    output = tmp_path / "run" / "modkit_extract" / "extracted.tsv"
    ModkitExtractNode.PREPARE_EXECUTION(inputs, [output])

    assert inputs["bam"] == str(tmp_path / "run" / "modkit_extract" / "inputs" / "bam" / bam.name)
    assert inputs["bam_index"] == f"{inputs['bam']}.bai"
    assert inputs["reference"] == str(
        tmp_path / "run" / "modkit_extract" / "inputs" / "reference" / reference.name
    )
    assert inputs["reference_index"] == f"{inputs['reference']}.fai"
    assert Path(inputs["bam_index"]).read_text(encoding="utf-8") == bam_index.name


def test_pod5_subset_pinned_package_and_validation_contract() -> None:
    assert Pod5SubsetNode.REQUIRES_EXTERNAL_TOOLS is False
    assert Pod5SubsetNode.REQUIRED_CONDA_PACKAGES == ["pod5"]
    assert Pod5SubsetNode.PACKAGE_CONSTRAINT == "pod5 = 0.3.44"
    assert Pod5SubsetNode.GIT_COMMIT == "23346e11be006f8f7c4047172d10e542172b7af6"
    assert Pod5SubsetNode.VALIDATE_INPUTS({"pod5_path": "reads.pod5", "num_reads": 10, "seed": 1}) is True
    assert Pod5SubsetNode.VALIDATE_INPUTS(
        {"pod5_path": "reads.pod5", "num_reads": 50_000_001}
    ) == "Input 'num_reads' must be at most 50000000"
    assert Pod5SubsetNode.VALIDATE_INPUTS({"pod5_path": "reads.pod5", "seed": -1}) == (
        "Input 'seed' must be at least 0"
    )
    assert Pod5SubsetNode.VALIDATE_INPUTS({"pod5_path": "reads.pod5", "num_reads": True}).startswith(
        "Input 'num_reads' must be an integer"
    )
    assert Pod5SubsetNode.VALIDATE_INPUTS({"pod5_path": "reads.pod5", "output_name": "../escape.pod5"}).startswith(
        "Input 'output_name' must be a plain file name"
    )


def test_pod5_subset_index_selection_is_deterministic() -> None:
    first = Pod5SubsetNode.selected_indices(1000, 100, 42)
    second = Pod5SubsetNode.selected_indices(1000, 100, 42)
    assert first == second == sorted(first)
    assert len(first) == 100 == len(set(first))
    assert Pod5SubsetNode.selected_indices(1000, 100, 43) != first
    assert Pod5SubsetNode.selected_indices(10, 10 ** 9, 5) == list(range(10))
    assert Pod5SubsetNode.selected_indices(0, 10, 5) == []
    assert Pod5SubsetNode.selected_indices(1, 1_000_000, 0) == [0]


def _write_tiny_pod5(path: Path, n_reads: int) -> None:
    import datetime
    import uuid

    import numpy as np
    import pod5 as p5

    now = datetime.datetime.now(datetime.timezone.utc)
    run_info = p5.RunInfo(
        acquisition_id="acq",
        acquisition_start_time=now,
        adc_max=4095,
        adc_min=-4096,
        context_tags={},
        experiment_name="exp",
        flow_cell_id="fc",
        flow_cell_product_code="FLO",
        protocol_name="prot",
        protocol_run_id="pr",
        protocol_start_time=now,
        sample_id="s",
        sample_rate=4000,
        sequencing_kit="kit",
        sequencer_position="pos",
        sequencer_position_type="type",
        software="sw",
        system_name="sys",
        system_type="grid",
        tracking_id={},
    )
    with p5.Writer(str(path)) as writer:
        for index in range(n_reads):
            writer.add_read(
                p5.Read(
                    read_id=uuid.UUID(int=index),
                    pore=p5.Pore(channel=index + 1, well=1, pore_type="p"),
                    calibration=p5.Calibration(offset=0.0, scale=1.0),
                    read_number=index,
                    start_sample=0,
                    median_before=180.0,
                    end_reason=p5.EndReason(reason=p5.EndReasonEnum.SIGNAL_POSITIVE, forced=False),
                    run_info=run_info,
                    signal=np.array([100 + index, 200, 300], dtype=np.int16),
                )
            )


@pytest.mark.asyncio
async def test_pod5_subset_writes_seeded_subset_and_summary(tmp_path: Path) -> None:
    p5 = pytest.importorskip("pod5", reason="pod5 wheel not installed in this dev environment")
    source = tmp_path / "reads.pod5"
    _write_tiny_pod5(source, 5)
    with p5.Reader(str(source)) as reader:
        source_ids = list(reader.read_ids)
    expected_ids = {source_ids[index] for index in (1, 2, 3)}

    node = Pod5SubsetNode()
    context = SimpleNamespace(node_dir=tmp_path)
    subset_path, summary_path = await node.run(
        pod5_path=str(source), num_reads=3, seed=7, context=context
    )

    with p5.Reader(subset_path) as reader:
        assert reader.num_reads == 3
        assert set(reader.read_ids) == expected_ids

    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["n_input_reads"] == 5
    assert summary["n_output_reads"] == 3
    assert summary["seed"] == 7
    assert len(summary["sha256"]) == 64

    _, rerun_summary = await node.run(pod5_path=str(source), num_reads=3, seed=7, context=context)
    with p5.Reader(str(Path(summary_path).parent / "subset.pod5")) as reader:
        assert set(reader.read_ids) == expected_ids
    assert json.loads(Path(rerun_summary).read_text(encoding="utf-8"))["n_output_reads"] == 3

    other_path, other_summary = await node.run(pod5_path=str(source), num_reads=3, seed=8, context=context)
    other = json.loads(Path(other_summary).read_text(encoding="utf-8"))
    assert other["n_output_reads"] == 3
    with p5.Reader(other_path) as reader:
        assert set(reader.read_ids) != expected_ids


@pytest.mark.asyncio
async def test_pod5_subset_rejects_missing_input(tmp_path: Path) -> None:
    node = Pod5SubsetNode()
    context = SimpleNamespace(node_dir=tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        await node.run(pod5_path=str(tmp_path / "missing.pod5"), context=context)
