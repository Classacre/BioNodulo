"""Real runtime evidence for BED/GFF3/GTF coordinate semantics."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import bionodulo.nodes.artifact_semantics as artifact_semantics
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.artifact_semantics import (
    ArtifactValidationError,
    validate_artifact_semantics,
    write_artifact_semantic_evidence,
)
from bionodulo.nodes.builtin.workflow_enhancement_family.validate_semantic_artifact import (
    ValidateSemanticArtifactNode,
)
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.nodes.semantic_contracts import (
    Clause,
    Guarantee,
    NodeSemanticContract,
    SemanticContractLibrary,
)
from bionodulo.workflow.semantic_checks import check_workflow_semantics


def _executor(root: Path) -> WorkflowExecutor:
    registry = NodeRegistry.create_isolated()
    registry.register(ValidateSemanticArtifactNode)
    return WorkflowExecutor(
        workspace_dir=root,
        registry=registry,
        settings=SimpleNamespace(
            execution=SimpleNamespace(
                max_workers=1,
                env_isolation="off",
                content_hashing="strong",
            ),
            api_secrets={},
        ),
    )


def _workflow(path: Path, artifact_format: str, **params: object) -> dict:
    return {
        "name": "coordinate evidence fixture",
        "nodes": [
            {
                "id": "validate",
                "type": "validate_semantic_artifact",
                "params": {
                    "input_file": str(path),
                    "format": artifact_format,
                    **params,
                },
            }
        ],
        "edges": [],
    }


def test_full_bed_scan_is_immutable_and_hashes_detached_evidence(tmp_path: Path) -> None:
    bed = tmp_path / "sites.bed"
    original = b"track name=sites\nchr1\t0\t1\tone\nchr1\t5\t8\tthree\n"
    bed.write_bytes(original)

    result = validate_artifact_semantics(bed, artifact_format="bed")

    assert result.scan_scope == "full_scan"
    assert result.coordinate_system.value == "zero_based_half_open"
    assert result.coordinate_system.level == "declared"
    assert result.coordinate_validity.level == "observed"
    assert result.reference_assembly.level == "unknown"
    assert result.sequence_observations[0].total_interval_bases == 4
    assert result.sequence_observations[0].minimum_start == 0
    assert result.source_sha256 == hashlib.sha256(original).hexdigest()
    assert bed.read_bytes() == original
    with pytest.raises(FrozenInstanceError):
        result.records_scanned = 99  # type: ignore[misc]

    evidence, checksum, evidence_hash = write_artifact_semantic_evidence(
        result, tmp_path / "evidence"
    )
    assert hashlib.sha256(evidence.read_bytes()).hexdigest() == evidence_hash
    assert checksum.read_text(encoding="ascii") == (
        f"{evidence_hash}  {evidence.name}\n"
    )
    assert bed.read_bytes() == original


def test_gff3_full_scan_separates_declared_build_from_observed_intervals(
    tmp_path: Path,
) -> None:
    gff = tmp_path / "features.gff3"
    gff.write_text(
        "##gff-version 3\n"
        "##genome-build NCBI GRCh38\n"
        "##sequence-region chr1 1 10\n"
        "chr1\ttest\tgene\t1\t1\t.\t+\t.\tID=g1\n"
        "chr1\ttest\texon\t3\t5\t.\t+\t.\tID=e1;Parent=g1\n"
        "##FASTA\n>chr1\nACGTACGTAC\n",
        encoding="utf-8",
    )

    result = validate_artifact_semantics(gff, artifact_format="gff3")

    assert result.coordinate_system.value == "one_based_closed"
    assert result.sequence_observations[0].total_interval_bases == 4
    assert result.reference_region_declarations[0].end == 10
    assert result.reference_assembly.value == "GRCh38"
    assert result.reference_assembly.level == "declared"
    assert "not independently verified" in result.reference_assembly.basis


def test_gtf_one_base_interval_has_length_one(tmp_path: Path) -> None:
    gtf = tmp_path / "one.gtf"
    gtf.write_text(
        'chr2\ttest\texon\t1\t1\t.\t-\t.\tgene_id "g";\n',
        encoding="utf-8",
    )
    result = validate_artifact_semantics(gtf, artifact_format="gtf")
    assert result.sequence_observations[0].total_interval_bases == 1
    assert result.coordinate_system.value == "one_based_closed"


@pytest.mark.parametrize(
    "artifact_format,body,error",
    [
        ("bed", "chr1\t-1\t2\n", "invalid 0-based"),
        ("bed", "chr1\t3\t2\n", "invalid 0-based"),
        ("gff3", "##gff-version 3\nchr1\tx\tgene\t0\t1\t.\t+\t.\tID=x\n", "invalid 1-based"),
        ("gff3", "##gff-version 3\nchr1\tx\tgene\t-1\t1\t.\t+\t.\tID=x\n", "invalid 1-based"),
        ("gtf", 'chr1\tx\texon\t0\t1\t.\t+\t.\tgene_id "x";\n', "invalid 1-based"),
    ],
)
def test_invalid_coordinate_boundaries_fail_closed(
    tmp_path: Path, artifact_format: str, body: str, error: str
) -> None:
    path = tmp_path / f"bad.{artifact_format}"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match=error):
        validate_artifact_semantics(path, artifact_format=artifact_format)  # type: ignore[arg-type]


def test_coordinate_and_assembly_contradictions_fail_closed(tmp_path: Path) -> None:
    bed = tmp_path / "one.bed"
    bed.write_text("chr1\t0\t1\n", encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match="contradicts"):
        validate_artifact_semantics(
            bed,
            artifact_format="bed",
            declared_coordinate_system="one_based_closed",
        )

    gff = tmp_path / "one.gff3"
    gff.write_text(
        "##gff-version 3\n##genome-build NCBI GRCh38\n"
        "chr1\tx\tgene\t1\t1\t.\t+\t.\tID=x\n",
        encoding="utf-8",
    )
    with pytest.raises(ArtifactValidationError, match="assembly.*contradicts"):
        validate_artifact_semantics(
            gff, artifact_format="gff3", declared_assembly="GRCh37"
        )


def test_bounded_probe_never_claims_whole_file_validity(tmp_path: Path) -> None:
    bed = tmp_path / "prefix-only.bed"
    bed.write_text("chr1\t0\t1\nchr1\tbroken\t2\n", encoding="utf-8")

    probe = validate_artifact_semantics(
        bed, artifact_format="bed", max_records=1
    )
    assert probe.scan_scope == "bounded_probe"
    assert probe.records_scanned == 1
    assert "only the first 1" in probe.coordinate_validity.basis
    with pytest.raises(ArtifactValidationError, match="chromStart must be an integer"):
        validate_artifact_semantics(bed, artifact_format="bed")
    assert "max_records" not in ValidateSemanticArtifactNode.INPUT_TYPES()["optional"]


@pytest.mark.parametrize("invalid_cap", [True, 0, -1, 1.5, float("nan")])
def test_bounded_probe_cap_must_be_a_positive_integer(
    tmp_path: Path, invalid_cap: object
) -> None:
    bed = tmp_path / "one.bed"
    bed.write_text("chr1\t0\t1\n", encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match="positive integer"):
        validate_artifact_semantics(
            bed, artifact_format="bed", max_records=invalid_cap  # type: ignore[arg-type]
        )


def test_library_api_rejects_source_identity_change_during_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bed = tmp_path / "changing.bed"
    bed.write_text("chr1\t0\t1\n", encoding="utf-8")
    hashes = iter(("a" * 64, "b" * 64))
    monkeypatch.setattr(artifact_semantics, "_sha256", lambda _path: next(hashes))
    with pytest.raises(ArtifactValidationError, match="changed during"):
        validate_artifact_semantics(bed, artifact_format="bed")


def test_real_executor_runs_full_validator_and_preserves_source(tmp_path: Path) -> None:
    bed = tmp_path / "executor.bed"
    original = b"chr1\t0\t1\nchr1\t4\t7\n"
    bed.write_bytes(original)

    result = asyncio.run(
        _executor(tmp_path / "engine").execute(
            "semantic-bed", _workflow(bed, "bed"), force=True
        )
    )

    assert result["status"] == "completed", result
    outputs = result["outputs"]["validate"]
    assert Path(outputs["validated_artifact"]) == bed.resolve()
    evidence = json.loads(Path(outputs["evidence_json"]).read_text(encoding="utf-8"))
    assert evidence["scan_scope"] == "full_scan"
    assert evidence["records_scanned"] == 2
    assert evidence["sequence_observations"][0]["total_interval_bases"] == 4
    assert hashlib.sha256(Path(outputs["evidence_json"]).read_bytes()).hexdigest() == outputs["evidence_sha256"]
    assert bed.read_bytes() == original


def test_real_executor_rejects_malformed_gff_before_outputs(tmp_path: Path) -> None:
    gff = tmp_path / "bad.gff3"
    gff.write_text(
        "##gff-version 3\nchr1\tx\tgene\t0\t1\t.\t+\t.\tID=x\n",
        encoding="utf-8",
    )
    result = asyncio.run(
        _executor(tmp_path / "engine").execute(
            "semantic-bad", _workflow(gff, "gff3"), force=True
        )
    )
    assert result["status"] == "failed"
    assert "invalid 1-based closed GFF3 interval" in result["node_results"]["validate"]["error"]
    assert result["outputs"] == {}


def test_real_api_accepts_and_runs_registered_full_scan_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key, value in {
        "BIONODULO_ROOT": str(tmp_path / "api"),
        "BIONODULO_EDITOR_MODE": "0",
        "BIONODULO_CLOUD_MODE": "0",
        "BIONODULO_SESSION_TOKEN": "",
        "BIONODULO_PROXY_SECRET": "",
        "BIONODULO_REDIS_URL": "",
        "BIONODULO_EXECUTION_BACKEND": "local",
        "BIONODULO_EXECUTION__ON_INTERRUPT": "manual",
    }.items():
        monkeypatch.setenv(key, value)
    from server import create_app

    bed = tmp_path / "api.bed"
    original = b"chr3\t0\t1\nchr3\t10\t12\n"
    bed.write_bytes(original)
    workflow = _workflow(bed, "bed")

    with TestClient(create_app()) as client:
        validation = client.post("/api/workflow/validate", json={"workflow": workflow})
        assert validation.status_code == 200, validation.text
        assert validation.json()["valid"] is True, validation.json()
        submitted = client.post("/api/runs", json={"workflow": workflow})
        assert submitted.status_code == 200, submitted.text
        run_id = submitted.json()["run_id"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            details = client.get(f"/api/runs/{run_id}").json()
            if details["status"] not in {"queued", "pending", "running"}:
                break
            time.sleep(0.05)
        assert details["status"] == "completed", details
        outputs = details["result"]["outputs"]["validate"]
        evidence = json.loads(
            Path(outputs["evidence_json"]).read_text(encoding="utf-8")
        )
        assert evidence["scan_scope"] == "full_scan"
        assert evidence["source_sha256"] == hashlib.sha256(original).hexdigest()
        assert bed.read_bytes() == original


@pytest.mark.parametrize(
    "artifact_format,expected,opposite",
    [
        ("bed", "zero_based_half_open", "one_based_closed"),
        ("gff3", "one_based_closed", "zero_based_half_open"),
        ("gtf", "one_based_closed", "zero_based_half_open"),
    ],
)
def test_static_postcondition_has_finite_coordinate_counterexample(
    artifact_format: str, expected: str, opposite: str
) -> None:
    bundled = SemanticContractLibrary.bundled()
    consumer = NodeSemanticContract(
        node_type="coordinate_consumer",
        review_status="documentation_backed",
        inputs={
            "artifact": [
                Clause(dimension="coordinate_system", value=opposite)
            ]
        },
        outputs={"result": []},
    )
    library = SemanticContractLibrary(
        schema_version=bundled.schema_version,
        dimensions=bundled.dimensions,
        contracts=(*bundled.contracts, consumer),
        coercions=bundled.coercions,
    )
    workflow = {
        "nodes": [
            {
                "id": "validate",
                "type": "validate_semantic_artifact",
                "params": {"input_file": "fixture", "format": artifact_format},
            },
            {"id": "consume", "type": "coordinate_consumer", "params": {}},
        ],
        "edges": [
            {
                "id": "coordinates",
                "from": {"node": "validate", "output": "validated_artifact"},
                "to": {"node": "consume", "input": "artifact"},
            }
        ],
    }
    checked = check_workflow_semantics(workflow, library)
    assert checked.node_states["validate"]["validated_artifact"]["coordinate_system"] == expected
    assert not checked.ok
    assert checked.violations[0].observed_value == expected
    assert checked.violations[0].required_value == opposite
    payload = checked.to_dict()
    assert payload["checks"][0]["evidence_level"] == "declared"
    assert payload["checks"][0]["producer_contract_review"] == "runtime_validated"


@pytest.mark.parametrize(
    "paired_end_status,count_read_pairs,expected",
    [
        ("single_end", False, "assigned_reads"),
        ("single_end", True, "assigned_fragments"),
        ("PE_individual", False, "assigned_reads"),
        ("PE_individual", True, "assigned_fragments"),
        ("PE_fragments", False, "assigned_fragments"),
        ("PE_fragments", True, "assigned_fragments"),
    ],
)
def test_featurecounts_read_fragment_unit_matrix_is_exhaustive(
    paired_end_status: str,
    count_read_pairs: bool,
    expected: str,
) -> None:
    workflow = {
        "nodes": [
            {
                "id": "counts",
                "type": "featurecounts",
                "params": {
                    "paired_end_status": paired_end_status,
                    "count_read_pairs": count_read_pairs,
                    "fraction": False,
                    "multifeat": "",
                    "strand_specificity": "0",
                },
            }
        ],
        "edges": [],
    }
    checked = check_workflow_semantics(workflow)
    assert checked.node_states["counts"]["counts"]["count_unit"] == expected


@pytest.mark.parametrize(
    "fraction,multifeat,expected",
    [
        (False, "", "nonnegative_integer"),
        (False, "-M", "nonnegative_integer"),
        (False, "-O", "nonnegative_integer"),
        (False, "-O -M", "nonnegative_integer"),
        (True, "", "unknown"),
        (True, "-M", "fractional_possible"),
        (True, "-O", "fractional_possible"),
        (True, "-O -M", "fractional_possible"),
    ],
)
def test_featurecounts_value_domain_requires_effective_fraction_flag(
    fraction: bool, multifeat: str, expected: str
) -> None:
    checked = check_workflow_semantics(
        {
            "nodes": [
                {
                    "id": "counts",
                    "type": "featurecounts",
                    "params": {
                        "paired_end_status": "single_end",
                        "count_read_pairs": False,
                        "fraction": fraction,
                        "multifeat": multifeat,
                        "strand_specificity": "0",
                    },
                }
            ],
            "edges": [],
        }
    )
    assert (
        checked.node_states["counts"]["counts"]["count_value_domain"]
        == expected
    )


def test_fractional_featurecounts_and_mixed_salmon_table_do_not_satisfy_deseq2() -> None:
    for producer_type, producer_params, dimension, expected in (
        (
            "featurecounts",
            {
                "paired_end_status": "single_end",
                "count_read_pairs": False,
                "fraction": True,
                "multifeat": "-M",
                "strand_specificity": "0",
            },
            "count_value_domain",
            "fractional_possible",
        ),
        ("salmon_quant", {}, "count_unit", "mixed_abundance_columns"),
    ):
        checked = check_workflow_semantics(
            {
                "nodes": [
                    {"id": "make", "type": producer_type, "params": producer_params},
                    {"id": "de", "type": "deseq2", "params": {}},
                ],
                "edges": [
                    {
                        "id": "not-integer-count-matrix",
                        "from": {"node": "make", "output": "counts"},
                        "to": {"node": "de", "input": "count_matrix"},
                    }
                ],
            }
        )
        assert not checked.ok
        violation = next(v for v in checked.violations if v.dimension == dimension)
        assert violation.observed_value == expected
        assert violation.required_value == (
            "nonnegative_integer"
            if dimension == "count_value_domain"
            else "assigned_reads|assigned_fragments"
        )


def test_param_tuple_map_rejects_values_outside_dimension() -> None:
    bundled = SemanticContractLibrary.bundled()
    broken = NodeSemanticContract(
        node_type="broken",
        outputs={
            "out": [
                Guarantee(
                    dimension="count_unit",
                    op="param_tuple_map",
                    params=("a", "b"),
                    param_map={"x|y": "not_a_unit"},
                )
            ]
        },
    )
    with pytest.raises(ValueError, match="not a member"):
        SemanticContractLibrary(
            schema_version=bundled.schema_version,
            dimensions=bundled.dimensions,
            contracts=(broken,),
        )
