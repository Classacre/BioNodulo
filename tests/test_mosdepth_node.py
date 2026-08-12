from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.qc_family.mosdepth import MosdepthNode


def test_mosdepth_is_source_pinned_and_requires_an_alignment_index() -> None:
    assert MosdepthNode.VERSION == "0.3.14"
    assert MosdepthNode.GIT_COMMIT == "821fddb12860d024fef4cf0bfe86918f2413d4e4"
    assert MosdepthNode.REQUIRED_EXECUTABLES == ["mosdepth"]
    assert MosdepthNode.REQUIRED_CONDA_PACKAGES == ["mosdepth"]
    assert MosdepthNode.PACKAGE_CONSTRAINTS == ("mosdepth==0.3.14",)
    assert MosdepthNode.UPSTREAM_SOURCE_SHA256 == (
        "48ff35449367c03b9abbaf20ae4d01ba891c449d29516d0bca27182dfa1e0899"
    )
    assert MosdepthNode.DEFAULT_EXCLUDE_FLAG == 1796
    required = MosdepthNode.INPUT_TYPES()["required"]
    assert set(required) == {"input_alignment", "alignment_index"}
    validation = str(MosdepthNode.VALIDATE_INPUTS({"input_alignment": "/data/a.bam"}))
    assert "alignment_index" in validation
    assert "missing" in validation
    assert MosdepthNode.VALIDATE_INPUTS(
        {"input_alignment": "/data/a.bam", "alignment_index": "/data/a.bam.bai"}
    ) is True


def test_mosdepth_default_command_preserves_native_summary_outputs(tmp_path: Path) -> None:
    inputs = {
        "input_alignment": "sample.bam",
        "alignment_index": "sample.bam.bai",
        "threads": 4,
        "per_base_coverage": False,
        "window_mode": "no",
        "output": tmp_path / "mosdepth",
    }
    assert MosdepthNode.render_command(inputs) == [
        "mosdepth",
        "--threads",
        "4",
        "--no-per-base",
        "--flag",
        "1796",
        str(tmp_path / "mosdepth" / "output"),
        "sample.bam",
    ]
    assert MosdepthNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "mosdepth" / "output.mosdepth.global.dist.txt",
        tmp_path / "mosdepth" / "output.mosdepth.summary.txt",
    ]


def test_mosdepth_conditional_tracks_keep_bgzf_and_csi_pairs(tmp_path: Path) -> None:
    inputs = {
        "input_alignment": "sample.bam",
        "alignment_index": "sample.bam.bai",
        "per_base_coverage": True,
        "window_mode": "bed",
        "region_file": "targets.bed",
        "thresholds": "10,20",
        "quantize_depths": "0:1:20:",
    }
    planned = MosdepthNode.PLAN_OUTPUTS(inputs, tmp_path)
    assert [path.name for path in planned] == [
        "output.mosdepth.global.dist.txt",
        "output.mosdepth.summary.txt",
        "output.mosdepth.region.dist.txt",
        "output.per-base.bed.gz",
        "output.per-base.bed.gz.csi",
        "output.regions.bed.gz",
        "output.regions.bed.gz.csi",
        "output.quantized.bed.gz",
        "output.quantized.bed.gz.csi",
        "output.thresholds.bed.gz",
        "output.thresholds.bed.gz.csi",
    ]
    assert MosdepthNode.MAP_PLANNED_OUTPUTS(planned) == {
        "global_distribution": planned[0],
        "summary": planned[1],
        "region_distribution": planned[2],
        "per_base_depth": planned[3],
        "per_base_depth_index": planned[4],
        "regions_bed": planned[5],
        "regions_bed_index": planned[6],
        "quantized_bed": planned[7],
        "quantized_bed_index": planned[8],
        "thresholds_bed": planned[9],
        "thresholds_bed_index": planned[10],
    }


def test_mosdepth_can_explicitly_disable_default_exclude_mask() -> None:
    command = MosdepthNode.render_command(
        {
            "input_alignment": "sample.bam",
            "alignment_index": "sample.bam.bai",
            "exclude_flag": 0,
        }
    )
    assert ["--flag", "0"] == command[command.index("--flag") : command.index("--flag") + 2]


def test_cram_requires_and_stages_reference_fai_and_crai(tmp_path: Path) -> None:
    cram = tmp_path / "source" / "sample.cram"
    cram.parent.mkdir()
    cram.write_bytes(b"cram")
    crai = Path(f"{cram}.crai")
    crai.write_bytes(b"crai")
    reference = tmp_path / "source" / "reference.fa"
    reference.write_text(">chr1\nACGT\n", encoding="ascii")
    fai = Path(f"{reference}.fai")
    fai.write_text("chr1\t4\t6\t4\t5\n", encoding="ascii")
    inputs: dict[str, Any] = {
        "input_alignment": cram,
        "alignment_index": crai,
        "reference": reference,
        "reference_index": fai,
    }
    assert MosdepthNode.VALIDATE_INPUTS(inputs) is True
    outputs = MosdepthNode.PLAN_OUTPUTS(inputs, tmp_path / "run")
    MosdepthNode.PREPARE_EXECUTION(inputs, outputs)

    staged_cram = tmp_path / "run" / "mosdepth" / "input" / "alignment.cram"
    staged_reference = tmp_path / "run" / "mosdepth" / "reference" / "reference.fa"
    assert inputs["input_alignment"] == str(staged_cram)
    assert inputs["alignment_index"] == f"{staged_cram}.crai"
    assert inputs["reference"] == str(staged_reference)
    assert inputs["reference_index"] == f"{staged_reference}.fai"
    command = MosdepthNode.render_command({**inputs, "output": outputs[0].parent})
    assert ["--fasta", str(staged_reference)] == command[command.index("--fasta") : command.index("--fasta") + 2]


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"input_alignment": "/data/a.bam", "alignment_index": "/other/a.bam.bai"}, "colocated"),
        ({"input_alignment": "/data/a.cram", "alignment_index": "/data/a.cram.crai"}, "reference"),
        (
            {"input_alignment": "/data/a.bam", "alignment_index": "/data/a.bam.bai", "thresholds": "10"},
            "thresholds require",
        ),
        (
            {"input_alignment": "/data/a.bam", "alignment_index": "/data/a.bam.bai", "window_mode": "bed"},
            "region_file",
        ),
        (
            {
                "input_alignment": "/data/a.bam",
                "alignment_index": "/data/a.bam.bai",
                "fast_mode": True,
                "fragment_mode": True,
            },
            "cannot both",
        ),
        (
            {
                "input_alignment": "/data/a.bam",
                "alignment_index": "/data/a.bam.bai",
                "min_frag_len": 500,
                "max_frag_len": 100,
            },
            "max_frag_len",
        ),
    ],
)
def test_mosdepth_invalid_contracts_fail_closed(inputs: dict[str, Any], message: str) -> None:
    validation = MosdepthNode.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)


@pytest.mark.asyncio
async def test_mosdepth_fake_execution_returns_explicit_output_mapping(tmp_path: Path) -> None:
    alignment = tmp_path / "source" / "a.bam"
    alignment.parent.mkdir()
    alignment.write_bytes(b"bam")
    alignment_index = Path(f"{alignment}.bai")
    alignment_index.write_bytes(b"bai")
    inputs = {
        "input_alignment": alignment,
        "alignment_index": alignment_index,
        "per_base_coverage": True,
        "window_mode": "window",
        "window_size": 500,
    }

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, _command: str, **_kwargs: Any) -> dict[str, Any]:
            for path in MosdepthNode.PLAN_OUTPUTS(inputs, self.node_dir):
                path.write_bytes(b"synthetic")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await MosdepthNode().run(context=Context(), **inputs)
    outputs = result["outputs"]
    assert outputs["global_distribution"].endswith("output.mosdepth.global.dist.txt")
    assert outputs["per_base_depth"].endswith("output.per-base.bed.gz")
    assert outputs["per_base_depth_index"].endswith("output.per-base.bed.gz.csi")
    assert outputs["regions_bed_index"].endswith("output.regions.bed.gz.csi")
