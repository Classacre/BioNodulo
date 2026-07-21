from __future__ import annotations

import errno
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.samtools_family.faidx import SamtoolsFaidxNode
from bionodulo.nodes.registry import NodeRegistry


def test_faidx_is_a_pinned_focused_reference_sidecar_producer() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get("samtools_faidx")

    assert node_class is SamtoolsFaidxNode
    assert node_class.__module__ == "bionodulo.nodes.builtin.samtools_family.faidx"
    assert node_class.VERSION == "1.23.1"
    assert node_class.GIT_COMMIT == "6efb9b6da35224cf804921dedecf9fb8f411365d"
    assert node_class.UPSTREAM_MANPAGE == "doc/samtools-faidx.1"
    assert node_class.UPSTREAM_SOURCE == "faidx.c"
    assert node_class.UPSTREAM_DICT_MANPAGE == "doc/samtools-dict.1"
    assert node_class.UPSTREAM_DICT_SOURCE == "dict.c"
    assert node_class.RETURN_TYPES == (
        "FASTA",
        "FASTA_INDEX",
        "SEQUENCE_DICTIONARY",
    )
    assert node_class.RETURN_NAMES == (
        "reference",
        "fai_index",
        "sequence_dictionary",
    )


def test_faidx_plans_and_renders_colocated_reference_sidecars(tmp_path: Path) -> None:
    outputs = SamtoolsFaidxNode.PLAN_OUTPUTS(
        {"reference": "/data/reference.fna", "threads": 1},
        tmp_path,
    )
    node_out = tmp_path / "samtools_faidx"

    assert outputs == [
        node_out / "reference.fa",
        node_out / "reference.fa.fai",
        node_out / "reference.dict",
    ]
    assert SamtoolsFaidxNode.render_command(
        {
            "reference": str(outputs[0]),
            "threads": 1,
            "output": str(node_out),
        }
    ) == [
        "samtools",
        "faidx",
        "-@",
        "0",
        "--fai-idx",
        str(outputs[1]),
        str(outputs[0]),
        "&&",
        "samtools",
        "dict",
        "-u",
        "file:reference.fa",
        "-o",
        str(outputs[2]),
        str(outputs[0]),
    ]


def test_faidx_preparation_stages_reference_beside_outputs(tmp_path: Path) -> None:
    source = tmp_path / "source.fna"
    source.write_text(">chr1\nACGT\n", encoding="ascii")
    outputs = SamtoolsFaidxNode.PLAN_OUTPUTS(
        {"reference": source, "threads": 1},
        tmp_path / "run",
    )
    inputs: dict[str, Any] = {"reference": source, "threads": 1}

    SamtoolsFaidxNode.PREPARE_EXECUTION(inputs, outputs)

    assert inputs["reference"] == str(outputs[0])
    assert outputs[0].read_bytes() == source.read_bytes()
    assert outputs[0].stat().st_ino == source.stat().st_ino


def test_faidx_preparation_copies_only_for_supported_link_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.fa"
    source.write_text(">chr1\nACGT\n", encoding="ascii")
    outputs = SamtoolsFaidxNode.PLAN_OUTPUTS(
        {"reference": source, "threads": 1},
        tmp_path / "run",
    )
    inputs: dict[str, Any] = {"reference": source, "threads": 1}

    def cross_device_link(_source: object, _target: object) -> None:
        raise OSError(errno.EXDEV, "cross-device link")

    monkeypatch.setattr("bionodulo.nodes.builtin.samtools_family.faidx.os.link", cross_device_link)
    SamtoolsFaidxNode.PREPARE_EXECUTION(inputs, outputs)

    assert outputs[0].read_bytes() == source.read_bytes()
    assert outputs[0].stat().st_ino != source.stat().st_ino


@pytest.mark.parametrize(
    "inputs",
    [
        {"reference": "", "threads": 1},
        {"reference": 42, "threads": 1},
        {"reference": "reference.fa", "threads": -1},
        {"reference": "reference.fa", "threads": True},
        {"reference": "reference.fa.gz", "threads": 1},
        {"reference": "reference.BGZF", "threads": 1},
    ],
)
def test_faidx_rejects_invalid_reference_and_threads(inputs: dict[str, Any]) -> None:
    assert SamtoolsFaidxNode.VALIDATE_INPUTS(inputs) is not True


def test_faidx_accepts_source_supported_thread_counts() -> None:
    assert SamtoolsFaidxNode.VALIDATE_INPUTS({"reference": "reference.fa", "threads": 128}) is True
