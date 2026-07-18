from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.environments.constants import PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


REFERENCE_INDEX_CONSUMERS = {
    "gatk_haplotype_caller",
    "freebayes",
    "manta",
    "manta_call",
    "delly",
    "delly_call",
}

AUTHORITIES = {
    "gatk_haplotype_caller": (
        "4.6.2.0",
        "76edc75c26504da94bbaee66584e107e76ee15de",
        "src/main/java/org/broadinstitute/hellbender/engine/ReferenceDataSource.java",
    ),
    "freebayes": (
        "1.3.10",
        "b0d8efd9fa7f6612c883ec5ff79e4d17a0c29993",
        "src/FBFasta.cpp",
    ),
    "manta": (
        "1.6.0",
        "ab9f5502985a29ec74cfafb4963179b9cc185e55",
        "src/python/bin/configManta.py",
    ),
    "delly": (
        "1.2.6",
        "e6246dbb18b7f6df2b7b381d542cdeaea6be8c82",
        "src/delly.h",
    ),
}


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None
    return node_class


def _valid_inputs(tmp_path: Path) -> dict[str, Any]:
    reference = tmp_path / "reference.fa"
    bam = tmp_path / "sample.bam"
    return {
        "reference": reference,
        "reference_index": Path(f"{reference}.fai"),
        "sequence_dictionary": reference.with_suffix(".dict"),
        "bam": bam,
        "bam_index": Path(f"{bam}.bai"),
        "threads": 4,
        "mode": "call",
    }


def test_reference_sidecar_contracts_pin_exact_upstream_authorities() -> None:
    for node_id, (version, commit, source) in AUTHORITIES.items():
        node_class = _node_class(node_id)
        assert node_class.VERSION == version
        assert node_class.GIT_COMMIT == commit
        assert node_class.UPSTREAM_SOURCE == source

    manta = _node_class("manta")
    assert manta.UPSTREAM_REFERENCE_SOURCE == "src/python/lib/mantaOptions.py"
    assert manta.UPSTREAM_BAM_INDEX_SOURCE == "src/python/lib/configureUtil.py"


def test_reference_sidecar_tools_use_exact_runtime_package_versions() -> None:
    assert PACKAGE_MIN_VERSIONS["gatk4"] == "4.6.2.0"
    assert PACKAGE_MIN_VERSIONS["freebayes"] == "1.3.10"
    assert PACKAGE_MIN_VERSIONS["manta"] == "1.6.0"
    assert PACKAGE_MIN_VERSIONS["delly"] == "1.2.6"


def test_callers_declare_only_the_reference_sidecars_their_tools_consume() -> None:
    for node_id in REFERENCE_INDEX_CONSUMERS:
        required = _node_class(node_id).INPUT_TYPES()["required"]
        assert required["reference_index"][0] == "FASTA_INDEX"

    gatk_required = _node_class("gatk_haplotype_caller").INPUT_TYPES()["required"]
    assert gatk_required["sequence_dictionary"][0] == "SEQUENCE_DICTIONARY"

    for node_id in REFERENCE_INDEX_CONSUMERS - {"gatk_haplotype_caller"}:
        assert "sequence_dictionary" not in _node_class(node_id).INPUT_TYPES()["required"]


@pytest.mark.parametrize("node_id", sorted(REFERENCE_INDEX_CONSUMERS))
def test_callers_accept_exact_colocated_reference_sidecars(
    node_id: str,
    tmp_path: Path,
) -> None:
    assert _node_class(node_id).VALIDATE_INPUTS(_valid_inputs(tmp_path)) is True


@pytest.mark.parametrize("node_id", sorted(REFERENCE_INDEX_CONSUMERS))
def test_callers_reject_non_colocated_reference_index(
    node_id: str,
    tmp_path: Path,
) -> None:
    inputs = _valid_inputs(tmp_path)
    inputs["reference_index"] = tmp_path / "other.fa.fai"

    result = _node_class(node_id).VALIDATE_INPUTS(inputs)

    assert result is not True
    assert "reference_index" in str(result)


def test_gatk_rejects_non_colocated_sequence_dictionary(tmp_path: Path) -> None:
    inputs = _valid_inputs(tmp_path)
    inputs["sequence_dictionary"] = tmp_path / "reference.fa.dict"

    result = _node_class("gatk_haplotype_caller").VALIDATE_INPUTS(inputs)

    assert result is not True
    assert "sequence_dictionary" in str(result)
    assert str(tmp_path / "reference.dict") in str(result)


@pytest.mark.parametrize("node_id", ["manta", "manta_call"])
def test_manta_requires_colocated_normal_index_only_with_normal_bam(
    node_id: str,
    tmp_path: Path,
) -> None:
    node_class = _node_class(node_id)
    inputs = _valid_inputs(tmp_path)
    normal_bam = tmp_path / "normal.bam"
    inputs["normal_bam"] = normal_bam

    missing = node_class.VALIDATE_INPUTS(inputs)
    assert missing is not True
    assert "normal_bam_index" in str(missing)

    inputs["normal_bam_index"] = Path(f"{normal_bam}.bai")
    assert node_class.VALIDATE_INPUTS(inputs) is True

    inputs["normal_bam_index"] = tmp_path / "wrong.bai"
    mismatched = node_class.VALIDATE_INPUTS(inputs)
    assert mismatched is not True
    assert "normal_bam_index" in str(mismatched)


@pytest.mark.parametrize("node_id", ["manta", "manta_call"])
def test_manta_rejects_orphan_normal_index(node_id: str, tmp_path: Path) -> None:
    inputs = _valid_inputs(tmp_path)
    inputs["normal_bam_index"] = tmp_path / "normal.bam.bai"

    result = _node_class(node_id).VALIDATE_INPUTS(inputs)

    assert result is not True
    assert "normal_bam" in str(result)


@pytest.mark.parametrize("node_id", ["manta", "manta_call"])
def test_manta_renders_documented_tumor_normal_roles(node_id: str) -> None:
    command = _node_class(node_id).render_command(
        {
            "bam": "tumor.bam",
            "normal_bam": "normal.bam",
            "reference": "reference.fa",
            "threads": 4,
            "output": f"/tmp/{node_id}",
        }
    )

    assert command[:7] == [
        "configManta.py",
        "--normalBam",
        "normal.bam",
        "--tumorBam",
        "tumor.bam",
        "--referenceFasta",
        "reference.fa",
    ]
    assert "--bam" not in command


@pytest.mark.parametrize("node_id", ["manta", "manta_call"])
def test_manta_keeps_documented_bam_alias_for_single_sample(node_id: str) -> None:
    command = _node_class(node_id).render_command(
        {
            "bam": "sample.bam",
            "reference": "reference.fa",
            "threads": 4,
            "output": f"/tmp/{node_id}",
        }
    )

    assert command[:5] == [
        "configManta.py",
        "--bam",
        "sample.bam",
        "--referenceFasta",
        "reference.fa",
    ]
