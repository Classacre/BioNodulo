from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.macs2_family.adapter import (
    MACS2_GIT_COMMIT,
    MACS2_PACKAGE_CONSTRAINT,
    MACS2_SOURCE_ROOT,
)
from bionodulo.nodes.builtin.macs2_family.bdgpeakcall import MACS2BdgPeakNode
from bionodulo.nodes.builtin.macs2_family.callpeak import MACS2CallpeakNode


MACS2_NODES = (MACS2CallpeakNode, MACS2BdgPeakNode)


@pytest.fixture(autouse=True)
def _materialize_macs2_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for filename in ("chip.bam", "score.bdg", "signed-score.bdg"):
        Path(filename).write_bytes(b"synthetic input\n")


@pytest.mark.parametrize("node_class", MACS2_NODES, ids=lambda node: node.NODE_ID)
def test_macs2_nodes_pin_source_and_environment_identity(node_class: type) -> None:
    assert node_class.VERSION == "2.2.9.1"
    assert node_class.GIT_TAG == "v2.2.9.1"
    assert node_class.GIT_COMMIT == MACS2_GIT_COMMIT
    assert node_class.SOURCE_REVISION == MACS2_GIT_COMMIT
    assert node_class.SOURCE_REF == f"tag v2.2.9.1 at {MACS2_GIT_COMMIT}"
    assert node_class.REQUIRED_EXECUTABLES == ["macs2"]
    assert node_class.REQUIRED_CONDA_PACKAGES == ["macs2"]
    assert node_class.ENVIRONMENT == {"type": "pixi", "name": "macs2"}
    assert node_class.CONDA_PACKAGE_CONSTRAINTS == {"macs2": "2.2.9.1"}
    assert node_class.PACKAGE_CONSTRAINTS == (MACS2_PACKAGE_CONSTRAINT,)
    assert node_class.PACKAGE_CONSTRAINT == "macs2==2.2.9.1"
    assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert "non-zero" in node_class.EXIT_SEMANTICS

    assert node_class.SOURCE_PATHS[0] == "README.md"
    assert "bin/macs2" in node_class.SOURCE_PATHS
    assert node_class.SOURCE_URLS == tuple(f"{MACS2_SOURCE_ROOT}/{path}" for path in node_class.SOURCE_PATHS)


def test_callpeak_defaults_and_native_filenames_match_v2291(tmp_path: Path) -> None:
    inputs = MACS2CallpeakNode.INPUT_TYPES()

    assert MACS2CallpeakNode.RETURN_TYPES == (
        "NARROW_PEAK",
        "BEDGRAPH",
        "TSV",
        "BED",
        "BEDGRAPH",
        "FILE",
    )
    assert MACS2CallpeakNode.RETURN_NAMES == (
        "peaks",
        "signal",
        "peak_table",
        "summits",
        "control_lambda",
        "model_script",
    )
    assert inputs["required"]["name"][1]["default"] == "NA"
    assert inputs["required"]["genome_size"][1]["default"] == "hs"
    assert inputs["optional"]["format"][1]["default"] == "AUTO"
    assert inputs["optional"]["qvalue"][1]["default"] == 0.05
    assert inputs["optional"]["pvalue"][1]["default"] is None

    command_inputs = {
        "treatment": "chip.bam",
        "name": "NA",
        "genome_size": "hs",
        "format": "AUTO",
        "qvalue": 0.05,
        "output": str(tmp_path / "macs2_callpeak"),
    }
    assert MACS2CallpeakNode.render_command(command_inputs) == [
        "macs2",
        "callpeak",
        "-t",
        "chip.bam",
        "-f",
        "AUTO",
        "-g",
        "hs",
        "-n",
        "NA",
        "--outdir",
        str(tmp_path / "macs2_callpeak"),
        "--bdg",
        "-q",
        "0.05",
    ]
    assert MACS2CallpeakNode.PLAN_OUTPUTS(command_inputs, tmp_path) == [
        tmp_path / "macs2_callpeak" / "NA_peaks.narrowPeak",
        tmp_path / "macs2_callpeak" / "NA_treat_pileup.bdg",
        tmp_path / "macs2_callpeak" / "NA_peaks.xls",
        tmp_path / "macs2_callpeak" / "NA_summits.bed",
        tmp_path / "macs2_callpeak" / "NA_control_lambda.bdg",
        tmp_path / "macs2_callpeak" / "NA_model.r",
    ]


def test_callpeak_bampe_skips_source_conditional_model_script(tmp_path: Path) -> None:
    inputs = {
        "treatment": "chip.bam",
        "name": "paired",
        "genome_size": "hs",
        "format": "BAMPE",
        "output": str(tmp_path / "macs2_callpeak"),
    }

    outputs = MACS2CallpeakNode.PLAN_OUTPUTS(inputs, tmp_path)

    assert len(outputs) == 5
    assert all(path.name != "paired_model.r" for path in outputs)
    command = MACS2CallpeakNode.render_command(inputs)
    assert command[:10] == [
        "macs2",
        "callpeak",
        "-t",
        "chip.bam",
        "-f",
        "BAMPE",
        "-g",
        "hs",
        "-n",
        "paired",
    ]


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_callpeak_rejects_nonfinite_effective_genome_size(value: str) -> None:
    validation = MACS2CallpeakNode.VALIDATE_INPUTS(
        {"treatment": "chip.bam", "name": "peaks", "genome_size": value}
    )

    assert validation == "genome_size must be hs, mm, ce, dm, or a positive number"


def test_callpeak_rejects_legacy_broad_mode_instead_of_silently_calling_narrow_peaks() -> None:
    inputs = {
        "treatment": "chip.bam",
        "name": "peaks",
        "genome_size": "hs",
        "broad": True,
    }

    validation = MACS2CallpeakNode.VALIDATE_INPUTS(inputs)

    assert "legacy broad=True is not supported" in str(validation)
    with pytest.raises(ValueError, match="legacy broad=True is not supported"):
        MACS2CallpeakNode.render_command(inputs)


def test_bdgpeakcall_uses_upstream_defaults_without_invented_numeric_bounds(tmp_path: Path) -> None:
    inputs = MACS2BdgPeakNode.INPUT_TYPES()["optional"]
    assert inputs["cutoff"][1] == {"default": 5.0}
    assert inputs["min_length"][1] == {"default": 200}
    assert inputs["max_gap"][1] == {"default": 30}

    command_inputs = {
        "treatment_bdg": "signed-score.bdg",
        "cutoff": -2.5,
        "min_length": 0,
        "max_gap": -1,
        "name": "signed peaks",
        "output": str(tmp_path / "macs2_bdgpeak"),
    }
    assert MACS2BdgPeakNode.VALIDATE_INPUTS(command_inputs) is True
    assert MACS2BdgPeakNode.render_command(command_inputs) == [
        "macs2",
        "bdgpeakcall",
        "-i",
        "signed-score.bdg",
        "-c",
        "-2.5",
        "-l",
        "0",
        "-g",
        "-1",
        "--outdir",
        str(tmp_path / "macs2_bdgpeak"),
        "-o",
        "signed_peaks.narrowPeak",
    ]


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        ({"cutoff": True}, "cutoff must be a number"),
        ({"min_length": 2.5}, "Input 'min_length' must be an integer"),
        ({"max_gap": False}, "max_gap must be an integer"),
    ),
)
def test_bdgpeakcall_preserves_argparse_numeric_types(
    updates: dict[str, object],
    message: str,
) -> None:
    validation = MACS2BdgPeakNode.VALIDATE_INPUTS(
        {
            "treatment_bdg": "score.bdg",
            **updates,
        }
    )

    assert validation == message


@pytest.mark.parametrize(
    ("node_class", "key", "filename"),
    (
        (MACS2CallpeakNode, "treatment", "missing.bam"),
        (MACS2CallpeakNode, "control", "empty-control.bam"),
        (MACS2BdgPeakNode, "treatment_bdg", "empty-score.bdg"),
    ),
    ids=("missing-treatment", "empty-control", "empty-bedgraph"),
)
def test_macs2_inputs_must_be_nonempty_materialized_files(
    node_class: type,
    key: str,
    filename: str,
) -> None:
    base_inputs: dict[str, object]
    if node_class is MACS2CallpeakNode:
        base_inputs = {
            "treatment": "chip.bam",
            "name": "peaks",
            "genome_size": "hs",
        }
    else:
        base_inputs = {"treatment_bdg": "score.bdg"}
    if not filename.startswith("missing"):
        Path(filename).touch()
    base_inputs[key] = filename

    validation = node_class.VALIDATE_INPUTS(base_inputs)

    expected = "not a materialized file" if filename.startswith("missing") else "is empty"
    assert expected in str(validation)
