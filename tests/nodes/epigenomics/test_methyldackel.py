from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.builtin.epigenomics_family.methyldackel import MethylDackelNode


def _inputs(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "bam": "sample.bam",
        "bam_index": "sample.bam.bai",
        "reference": "reference.fa",
        "reference_index": "reference.fa.fai",
        "output_prefix": "case sample",
        "output": "/tmp/run/methyldackel",
    }
    values.update(updates)
    return values


def test_contract_matches_pinned_release_defaults_and_outputs() -> None:
    optional = MethylDackelNode.INPUT_TYPES()["optional"]

    assert MethylDackelNode.VERSION == "0.6.1"
    assert MethylDackelNode.GIT_COMMIT == "b6db120e96ec8cf9ab44e1b1074d2aa7af876932"
    assert MethylDackelNode.REQUIRED_EXECUTABLES == ["MethylDackel"]
    assert MethylDackelNode.PACKAGE_CONSTRAINTS == ("methyldackel==0.6.1",)
    assert optional["threads"][1] == {"default": 1, "min": 1}
    assert optional["merge_context"][1]["default"] is False
    assert optional["min_depth"][1]["default"] == 1
    assert MethylDackelNode.PLAN_OUTPUTS(_inputs(), "/tmp/run") == [
        Path("/tmp/run/methyldackel/case_sample_CpG.bedGraph"),
        Path("/tmp/run/methyldackel/case_sample_mbias.tsv"),
    ]


def test_default_command_keeps_upstream_per_cytosine_mode() -> None:
    command = MethylDackelNode.render_command(_inputs())

    assert command[:9] == [
        "MethylDackel",
        "mbias",
        "--noSVG",
        "-@",
        "1",
        "reference.fa",
        "sample.bam",
        ">",
        "/tmp/run/methyldackel/case_sample_mbias.tsv",
    ]
    assert "--mergeContext" not in command
    assert command[-6:] == [
        "-o",
        "/tmp/run/methyldackel/case_sample",
        "--minDepth",
        "1",
        "reference.fa",
        "sample.bam",
    ]


def test_merge_context_is_explicit_and_min_depth_is_forwarded() -> None:
    command = MethylDackelNode.render_command(_inputs(threads=8, merge_context=True, min_depth=5))

    assert command[0:7] == [
        "MethylDackel",
        "mbias",
        "--noSVG",
        "-@",
        "8",
        "reference.fa",
        "sample.bam",
    ]
    assert command[-7:] == [
        "-o",
        "/tmp/run/methyldackel/case_sample",
        "--mergeContext",
        "--minDepth",
        "5",
        "reference.fa",
        "sample.bam",
    ]


def test_index_inputs_must_be_the_colocated_siblings_discovered_by_htslib() -> None:
    assert MethylDackelNode.VALIDATE_INPUTS(_inputs()) is True
    assert "exact colocated index" in str(MethylDackelNode.VALIDATE_INPUTS(_inputs(bam_index="sample.bai")))
    assert "exact colocated index" in str(MethylDackelNode.VALIDATE_INPUTS(_inputs(reference_index="other.fa.fai")))


def test_integer_validation_rejects_boolean_and_nonpositive_values() -> None:
    assert MethylDackelNode.VALIDATE_INPUTS(_inputs(threads=True)) == "threads must be an integer"
    assert MethylDackelNode.VALIDATE_INPUTS(_inputs(threads=0)) == "threads must be at least 1"
    assert MethylDackelNode.VALIDATE_INPUTS(_inputs(min_depth=False)) == "min_depth must be an integer"
    assert MethylDackelNode.VALIDATE_INPUTS(_inputs(min_depth=0)) == "min_depth must be at least 1"


def test_prepare_execution_stages_explicit_sidecars_as_canonical_siblings(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for name in ("sample.bam", "sample.bam.bai", "reference.fa", "reference.fa.fai"):
        (source / name).write_text(name, encoding="ascii")

    inputs = _inputs(
        bam=source / "sample.bam",
        bam_index=source / "sample.bam.bai",
        reference=source / "reference.fa",
        reference_index=source / "reference.fa.fai",
    )
    outputs = MethylDackelNode.PLAN_OUTPUTS(inputs, tmp_path / "run")
    MethylDackelNode.PREPARE_EXECUTION(inputs, outputs)

    staged_bam = Path(str(inputs["bam"]))
    staged_reference = Path(str(inputs["reference"]))
    assert staged_bam.name == "alignment.bam"
    assert Path(f"{staged_bam}.bai").read_text(encoding="ascii") == "sample.bam.bai"
    assert staged_reference.name == "reference.fa"
    assert Path(f"{staged_reference}.fai").read_text(encoding="ascii") == "reference.fa.fai"
