from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

import bionodulo.nodes.contract.evidence as evidence
import bionodulo.nodes.contract.maturity as maturity


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64
SHA_E = "sha256:" + "e" * 64
COMMIT_A = "1" * 40
COMMIT_B = "2" * 64
CAPTURE_DATE = date(2026, 7, 15)
CATALOG_PATH = "bionodulo/nodes/catalog/tools/samtools/evidence.authoring.json"
DEFAULT_CONTRACT_VALUE = "index"
DEFAULT_CONTRACT_VALUE_BYTES = b'"index"'
DEFAULT_CONTRACT_VALUE_SHA256 = "sha256:" + hashlib.sha256(DEFAULT_CONTRACT_VALUE_BYTES).hexdigest()
MAX_JSON_NUMBER_COEFFICIENT_DIGITS = 256
MAX_JSON_NUMBER_EXPONENT = 4096
MAX_JSON_INPUT_BYTES = 8 * 1024 * 1024
MAX_JSON_NESTING_DEPTH = 64
MAX_CANONICAL_JSON_BYTES = 1024 * 1024


def provenance(
    pointer: str = "/description",
    **updates: object,
) -> evidence.RetainedTextProvenance:
    values: dict[str, object] = {
        "origin": evidence.RetainedTextOrigin.CATALOG_AUTHOR,
        "catalog_path": CATALOG_PATH,
        "catalog_content_sha256": SHA_E,
        "field_pointer": pointer,
    }
    values.update(updates)
    return evidence.RetainedTextProvenance(**values)


def authored(
    value: str,
    pointer: str = "/description",
    **provenance_updates: object,
) -> evidence.RetainedText:
    return evidence.RetainedText(
        value=value,
        provenance=provenance(pointer, **provenance_updates),
    )


def byte_locator(start: int = 100, end: int = 180) -> evidence.ByteRangeLocator:
    return evidence.ByteRangeLocator(
        kind=evidence.ContentLocatorKind.BYTE_RANGE,
        start_byte=start,
        end_byte_exclusive=end,
    )


def proof(**updates: object) -> evidence.DocumentationVersionProof:
    values: dict[str, object] = {
        "proof_kind": evidence.DocumentationProofKind.DECLARED_METADATA,
        "tool_id": "samtools",
        "tool_version": "1.23.1",
        "source_url": "https://docs.example.org/releases/latest/dependencies/htslib/9.9/reference.html",
        "source_content_sha256": SHA_A,
        "locator": byte_locator(10, 40),
        "proof_content_sha256": SHA_B,
    }
    values.update(updates)
    return evidence.DocumentationVersionProof(**values)


def source(kind: evidence.SourceKind, **updates: object) -> evidence.EvidenceSource:
    values: dict[str, object] = {
        "source_id": f"samtools-{kind.value.replace('_', '-')}",
        "tool_id": "samtools",
        "kind": kind,
        "tool_version": "1.23.1",
        "retrieved_at": CAPTURE_DATE,
        "content_sha256": SHA_A,
        "content_format": (
            evidence.SourceContentFormat.JSON
            if kind is evidence.SourceKind.OFFICIAL_API_SCHEMA
            else (
                evidence.SourceContentFormat.SOURCE_CODE
                if kind is evidence.SourceKind.UPSTREAM_SOURCE
                else evidence.SourceContentFormat.TEXT
            )
        ),
        "title": authored("Samtools reference", f"/sources/{kind.value}/title"),
        "description": authored(
            "Authoritative behavior reference for the pinned tool release.",
            f"/sources/{kind.value}/description",
        ),
    }
    if kind in (evidence.SourceKind.OFFICIAL_MANUAL, evidence.SourceKind.OFFICIAL_API_SCHEMA):
        values["url"] = "https://docs.example.org/releases/latest/dependencies/htslib/9.9/reference.html"
    elif kind is evidence.SourceKind.PACKAGE_RECIPE:
        values.update(
            url=(f"https://github.com/bioconda/bioconda-recipes/blob/{COMMIT_A}/recipes/samtools/meta.yaml"),
            recipe_revision=COMMIT_A,
            recipe_path="recipes/samtools/meta.yaml",
        )
    elif kind is evidence.SourceKind.UPSTREAM_SOURCE:
        values.update(
            url=f"https://github.com/samtools/samtools/blob/{COMMIT_A}/bam_sort.c",
            commit=COMMIT_A,
            source_path="bam_sort.c",
            symbol_locator="bam_sort_core_ext",
        )
    else:
        values.update(
            environment_digest=SHA_B,
            executable_probe_id="samtools",
            argv=("--help",),
            output_sha256=SHA_A,
        )
    values.update(updates)
    if kind in (evidence.SourceKind.OFFICIAL_MANUAL, evidence.SourceKind.OFFICIAL_API_SCHEMA):
        values.setdefault(
            "documentation_proof",
            proof(
                tool_id=values["tool_id"],
                tool_version=values["tool_version"],
                source_url=values["url"],
                source_content_sha256=values["content_sha256"],
            ),
        )
    return evidence.EvidenceSource(**values)


def claim(
    claim_id: str = "output-collector",
    source_id: str = "samtools-official-manual",
    **updates: object,
) -> evidence.EvidenceClaim:
    values: dict[str, object] = {
        "claim_id": claim_id,
        "contract_pointer": "/outputs/index/collector",
        "source_id": source_id,
        "locator": byte_locator(),
        "statement": authored(
            "Default index naming is derived from the input file name.",
            f"/claims/{claim_id}/statement",
        ),
        "source_content_sha256": SHA_A,
        "excerpt_sha256": SHA_B,
        "contract_value_sha256": DEFAULT_CONTRACT_VALUE_SHA256,
    }
    values.update(updates)
    return evidence.EvidenceClaim(**values)


def verify_claim(
    asserted: evidence.EvidenceClaim,
    source_content: bytes,
    **updates: object,
) -> evidence.EvidenceClaim:
    verification: dict[str, object] = {
        "expected_contract_pointer": asserted.contract_pointer,
        "contract_value": DEFAULT_CONTRACT_VALUE,
    }
    verification.update(updates)
    return evidence.verify_evidence_claim_content(
        asserted,
        source_content=source_content,
        **verification,
    )


def verify_json_source(verifier: str, source_content: bytes) -> None:
    source_digest = "sha256:" + hashlib.sha256(source_content).hexdigest()
    selected_digest = "sha256:" + hashlib.sha256(b'"ok"').hexdigest()
    locator = evidence.JsonPointerLocator(
        kind=evidence.ContentLocatorKind.JSON_POINTER,
        pointer="/value",
    )
    if verifier == "retained_text":
        retained = authored(
            "ok",
            "/value",
            catalog_content_sha256=source_digest,
        )
        evidence.verify_retained_text_selection(
            retained,
            catalog_path=CATALOG_PATH,
            catalog_content=source_content,
            expected_field_pointer="/value",
        )
    elif verifier == "documentation_proof":
        evidence.verify_documentation_proof_content(
            proof(
                proof_kind=evidence.DocumentationProofKind.SCHEMA_FIELD,
                source_content_sha256=source_digest,
                locator=locator,
                proof_content_sha256=selected_digest,
            ),
            source_content=source_content,
        )
    elif verifier == "evidence_claim":
        verify_claim(
            claim(
                source_content_sha256=source_digest,
                locator=locator,
                excerpt_sha256=selected_digest,
            ),
            source_content,
        )
    else:
        raise AssertionError(f"unknown verifier: {verifier}")


def verification(
    evidence_id: str = "samtools-smoke-linux-amd64",
    **updates: object,
) -> evidence.VerificationEvidence:
    values: dict[str, object] = {
        "evidence_id": evidence_id,
        "tool_id": "samtools",
        "tool_version": "1.23.1",
        "kind": evidence.VerificationKind.TOOL_SMOKE,
        "outcome": evidence.VerificationOutcome.PASSED,
        "failure_code": None,
        "test_id": "samtools-index-tiny-bam-v1",
        "result_sha256": SHA_D,
        "fixture_id": "tiny-bam-v1",
        "fixture_sha256": SHA_E,
        "environment_sha256": SHA_B,
        "catalog_sha256": SHA_A,
        "platform_sha256": SHA_C,
        "release_sha256": None,
        "verified_at": CAPTURE_DATE,
        "verifier_id": "tool-verifier",
        "verifier_version": "1.0.0",
    }
    values.update(updates)
    return evidence.VerificationEvidence(**values)


_VERIFICATION_FAILURE = {
    evidence.VerificationKind.INVENTORY: evidence.FailureCode.INVENTORY_MISSING,
    evidence.VerificationKind.EVIDENCE_COVERAGE: evidence.FailureCode.EVIDENCE_MISSING,
    evidence.VerificationKind.CONTRACT_COMPILE: evidence.FailureCode.CONTRACT_INVALID,
    evidence.VerificationKind.COMMAND_FIXTURE: evidence.FailureCode.COMMAND_FIXTURE_FAILED,
    evidence.VerificationKind.ENVIRONMENT_PROBE: evidence.FailureCode.ENVIRONMENT_RESOLUTION_FAILED,
    evidence.VerificationKind.TOOL_SMOKE: evidence.FailureCode.TOOL_SMOKE_FAILED,
    evidence.VerificationKind.CLOUD_RUN: evidence.FailureCode.CLOUD_RUN_FAILED,
    evidence.VerificationKind.WORKFLOW_RUN: evidence.FailureCode.WORKFLOW_RUN_FAILED,
}

_REQUIRED_VERIFICATION_CONTEXT = {
    evidence.VerificationKind.INVENTORY: frozenset({"catalog_sha256"}),
    evidence.VerificationKind.EVIDENCE_COVERAGE: frozenset({"catalog_sha256"}),
    evidence.VerificationKind.CONTRACT_COMPILE: frozenset({"catalog_sha256"}),
    evidence.VerificationKind.COMMAND_FIXTURE: frozenset(
        {"fixture_id", "fixture_sha256", "environment_sha256", "catalog_sha256"}
    ),
    evidence.VerificationKind.ENVIRONMENT_PROBE: frozenset({"environment_sha256", "catalog_sha256", "platform_sha256"}),
    evidence.VerificationKind.TOOL_SMOKE: frozenset(
        {"fixture_id", "fixture_sha256", "environment_sha256", "catalog_sha256", "platform_sha256"}
    ),
    evidence.VerificationKind.CLOUD_RUN: frozenset(
        {
            "fixture_id",
            "fixture_sha256",
            "environment_sha256",
            "catalog_sha256",
            "platform_sha256",
            "release_sha256",
        }
    ),
    evidence.VerificationKind.WORKFLOW_RUN: frozenset(
        {
            "fixture_id",
            "fixture_sha256",
            "environment_sha256",
            "catalog_sha256",
            "platform_sha256",
            "release_sha256",
        }
    ),
}


def verification_with_minimal_context(
    kind: evidence.VerificationKind,
    outcome: evidence.VerificationOutcome = evidence.VerificationOutcome.PASSED,
) -> evidence.VerificationEvidence:
    context: dict[str, object] = {
        "fixture_id": None,
        "fixture_sha256": None,
        "environment_sha256": None,
        "catalog_sha256": None,
        "platform_sha256": None,
        "release_sha256": None,
    }
    for field in _REQUIRED_VERIFICATION_CONTEXT[kind]:
        context[field] = "fixture-v1" if field == "fixture_id" else SHA_A
    return verification(
        kind=kind,
        outcome=outcome,
        failure_code=None if outcome is evidence.VerificationOutcome.PASSED else _VERIFICATION_FAILURE[kind],
        **context,
    )


def evidence_record(**updates: object) -> evidence.EvidenceRecord:
    values: dict[str, object] = {
        "schema_version": 2,
        "tool_id": "samtools",
        "tool_version": "1.23.1",
        "sources": (source(evidence.SourceKind.OFFICIAL_MANUAL),),
        "claims": (claim(),),
        "verifications": (verification(),),
    }
    values.update(updates)
    return evidence.EvidenceRecord(**values)


_GATE_FAILURE = {
    maturity.Gate.INVENTORIED: evidence.FailureCode.INVENTORY_MISSING,
    maturity.Gate.EVIDENCE_VERIFIED: evidence.FailureCode.EVIDENCE_MISSING,
    maturity.Gate.CONTRACT_VERIFIED: evidence.FailureCode.CONTRACT_INVALID,
    maturity.Gate.COMMAND_VERIFIED: evidence.FailureCode.COMMAND_FIXTURE_FAILED,
    maturity.Gate.ENVIRONMENT_VERIFIED: evidence.FailureCode.ENVIRONMENT_RESOLUTION_FAILED,
    maturity.Gate.TOOL_SMOKE_VERIFIED: evidence.FailureCode.TOOL_SMOKE_FAILED,
    maturity.Gate.CLOUD_VERIFIED: evidence.FailureCode.CLOUD_RUN_FAILED,
    maturity.Gate.WORKFLOW_VERIFIED: evidence.FailureCode.WORKFLOW_RUN_FAILED,
}


def assessment(
    gate: maturity.Gate,
    result: maturity.GateResult = maturity.GateResult.PASSED,
    **updates: object,
) -> maturity.GateAssessment:
    values: dict[str, object] = {
        "gate": gate,
        "result": result,
        "verification_digests": (SHA_A,),
        "verified_at": CAPTURE_DATE,
        "verifier_id": "catalog-verifier",
        "verifier_version": "1.0.0",
        "failure_code": None if result is maturity.GateResult.PASSED else _GATE_FAILURE[gate],
    }
    values.update(updates)
    return maturity.GateAssessment(**values)


def passed_prefix(length: int) -> tuple[maturity.GateAssessment, ...]:
    return tuple(assessment(gate) for gate in tuple(maturity.Gate)[:length])


def maturity_record(**updates: object) -> maturity.MaturityRecord:
    values: dict[str, object] = {
        "schema_version": 2,
        "access_classes": (maturity.AccessClass.PUBLIC,),
        "assessments": (),
    }
    values.update(updates)
    return maturity.MaturityRecord(**values)


def test_schema_v2_types_are_explicit() -> None:
    assert tuple(evidence.RetainedTextOrigin) == (evidence.RetainedTextOrigin.CATALOG_AUTHOR,)
    assert tuple(item.value for item in evidence.ContentLocatorKind) == (
        "byte_range",
        "json_pointer",
        "symbol",
    )
    assert tuple(item.value for item in evidence.SourceContentFormat) == (
        "text",
        "json",
        "source_code",
    )
    assert tuple(item.value for item in evidence.DocumentationProofKind) == (
        "declared_metadata",
        "schema_field",
        "release_manifest",
    )
    assert tuple(item.value for item in evidence.VerificationKind) == (
        "inventory",
        "evidence_coverage",
        "contract_compile",
        "command_fixture",
        "environment_probe",
        "tool_smoke",
        "cloud_run",
        "workflow_run",
    )
    assert tuple(item.value for item in evidence.VerificationOutcome) == ("passed", "failed")


def test_existing_wire_enums_remain_exact() -> None:
    assert tuple(kind.value for kind in evidence.SourceKind) == (
        "official_manual",
        "official_api_schema",
        "upstream_source",
        "installed_help",
        "package_recipe",
    )
    assert tuple(item.value for item in maturity.AccessClass) == (
        "public",
        "public_rate_limited",
        "secret_required",
        "large_reference",
        "gpu_required",
        "byol",
        "service_license",
    )
    assert tuple(gate.value for gate in maturity.Gate) == (
        "inventoried",
        "evidence_verified",
        "contract_verified",
        "command_verified",
        "environment_verified",
        "tool_smoke_verified",
        "cloud_verified",
        "workflow_verified",
    )
    assert tuple(result.value for result in maturity.GateResult) == ("passed", "failed")


@pytest.mark.parametrize(
    "value",
    (
        "The password is Swordfish.",
        "The secret field accepts ordinary technical values.",
        "Captured examples may mention /home/alice/project and C:\\Users\\alice.",
        "Authorization examples belong in author-reviewed documentation prose.",
        "Resume - Unicode documentation: \u6e2c\u8a66",
    ),
)
def test_retained_text_accepts_arbitrary_authored_printable_prose(value: str) -> None:
    retained = authored(value)

    assert retained.value == value
    assert retained.provenance.origin is evidence.RetainedTextOrigin.CATALOG_AUTHOR


@pytest.mark.parametrize("value", (" text", "text ", "line\nfeed", "zero\u200bwidth", "right\u202eoverride"))
def test_retained_text_rejects_noncanonical_or_nonprintable_text(value: str) -> None:
    with pytest.raises(ValidationError):
        authored(value)


def test_runtime_or_capture_text_origin_does_not_exist() -> None:
    assert {item.value for item in evidence.RetainedTextOrigin} == {"catalog_author"}
    for origin in ("runtime_stdout", "runtime_stderr", "environment", "filesystem", "captured"):
        with pytest.raises(ValueError):
            evidence.RetainedTextOrigin(origin)
        with pytest.raises(ValidationError):
            evidence.RetainedTextProvenance.model_validate_json(
                json.dumps(
                    {
                        "origin": origin,
                        "catalog_path": CATALOG_PATH,
                        "catalog_content_sha256": SHA_E,
                        "field_pointer": "/description",
                    }
                )
            )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("catalog_path", "/home/alice/evidence.yaml"),
        ("catalog_path", "catalog/../evidence.yaml"),
        ("catalog_path", "catalog\\evidence.yaml"),
        ("catalog_path", "catalog/samtools/evidence.authoring.yaml"),
        ("catalog_path", "bionodulo/nodes/catalog/tools/samtools/evidence.yaml"),
        ("catalog_path", "bionodulo/nodes/catalog/tools/samtools/evidence.authoring.yaml"),
        ("catalog_path", "bionodulo/nodes/catalog/generated/evidence.authoring.json"),
        ("catalog_content_sha256", "a" * 64),
        ("catalog_content_sha256", "sha256:" + "A" * 64),
        ("field_pointer", "description"),
        ("field_pointer", "/../description"),
    ),
)
def test_retained_text_provenance_is_content_addressed_and_canonical(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        provenance(**{field: value})


def test_retained_text_provenance_is_strict_frozen_and_roundtrips() -> None:
    retained = authored("Ordinary authored prose.")
    rebuilt = evidence.RetainedText.model_validate_json(retained.model_dump_json())

    assert rebuilt == retained
    assert hash(rebuilt) == hash(retained)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        evidence.RetainedText(
            value="Text",
            provenance=provenance(),
            stdout="not allowed",
        )
    with pytest.raises(ValidationError, match="frozen_instance"):
        retained.value = "changed"


def test_compiler_verifies_injected_text_provenance_against_reopened_authoring_blob() -> None:
    source_bytes = b'{"description":"Ordinary authored prose."}'
    source_digest = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    retained = authored(
        "Ordinary authored prose.",
        "/description",
        catalog_content_sha256=source_digest,
    )

    assert (
        evidence.verify_retained_text_selection(
            retained,
            catalog_path=CATALOG_PATH,
            catalog_content=source_bytes,
            expected_field_pointer="/description",
        )
        == retained
    )


def test_compiler_requires_an_explicit_expected_pointer_from_the_loader() -> None:
    source_bytes = b'{"description":"Ordinary authored prose."}'
    source_digest = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    retained = authored("Ordinary authored prose.", "/description", catalog_content_sha256=source_digest)

    with pytest.raises(TypeError):
        evidence.verify_retained_text_selection(
            retained,
            catalog_path=CATALOG_PATH,
            catalog_content=source_bytes,
        )


def test_compiler_revalidates_model_constructed_text_before_accepting_provenance() -> None:
    source_bytes = b'{"description":"Ordinary authored prose."}'
    source_digest = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    forged_provenance = evidence.RetainedTextProvenance.model_construct(
        origin="runtime_stdout",
        catalog_path=CATALOG_PATH,
        catalog_content_sha256=source_digest,
        field_pointer="/description",
    )
    forged = evidence.RetainedText.model_construct(
        value="Ordinary authored prose.",
        provenance=forged_provenance,
    )

    with pytest.raises(ValidationError):
        evidence.verify_retained_text_selection(
            forged,
            catalog_path=CATALOG_PATH,
            catalog_content=source_bytes,
            expected_field_pointer="/description",
        )


def test_compiler_rejects_a_wrong_but_existing_factory_pointer() -> None:
    source_bytes = b'{"title":"Factory substitute","description":"Real description"}'
    source_digest = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    retained = authored("Factory substitute", "/title", catalog_content_sha256=source_digest)

    with pytest.raises(ValueError, match="field pointer"):
        evidence.verify_retained_text_selection(
            retained,
            catalog_path=CATALOG_PATH,
            catalog_content=source_bytes,
            expected_field_pointer="/description",
        )


def test_compiler_rejects_text_that_does_not_match_the_reopened_pointer_value() -> None:
    source_bytes = b'{"description":"Ordinary authored prose."}'
    source_digest = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    forged = authored(
        "Factory-provided substitute",
        "/description",
        catalog_content_sha256=source_digest,
    )

    with pytest.raises(ValueError, match="provenance"):
        evidence.verify_retained_text_selection(
            forged,
            catalog_path=CATALOG_PATH,
            catalog_content=source_bytes,
            expected_field_pointer="/description",
        )


@pytest.mark.parametrize(
    ("source_bytes", "pointer", "value"),
    (
        (
            b'{"description":"first","description":"Factory substitute"}',
            "/description",
            "Factory substitute",
        ),
        (
            b"base: &base\n  description: Factory substitute\ncopy:\n  <<: *base\n",
            "/copy/description",
            "Factory substitute",
        ),
        (
            b"description: !!str Factory substitute\n",
            "/description",
            "Factory substitute",
        ),
        (
            b'{"description":"Factory substitute","number":1e9999}',
            "/description",
            "Factory substitute",
        ),
    ),
)
def test_compiler_rejects_ambiguous_or_yaml_specific_authoring_content(
    source_bytes: bytes,
    pointer: str,
    value: str,
) -> None:
    source_digest = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    retained = authored(value, pointer, catalog_content_sha256=source_digest)

    with pytest.raises(ValueError, match="strict JSON"):
        evidence.verify_retained_text_selection(
            retained,
            catalog_path=CATALOG_PATH,
            catalog_content=source_bytes,
            expected_field_pointer=pointer,
        )


@pytest.mark.parametrize("pointer", ("/items/١", "/items/１", "/items/²"))
def test_compiler_rejects_non_ascii_json_array_indices(pointer: str) -> None:
    source_bytes = b'{"items":["zero","one"]}'
    source_digest = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    retained = authored("one", pointer, catalog_content_sha256=source_digest)

    with pytest.raises(ValueError, match="array index|provenance"):
        evidence.verify_retained_text_selection(
            retained,
            catalog_path=CATALOG_PATH,
            catalog_content=source_bytes,
            expected_field_pointer=pointer,
        )


@pytest.mark.parametrize(
    ("declared_updates", "verified_updates"),
    (
        ({"catalog_content_sha256": SHA_E}, {}),
        (
            {"catalog_path": "bionodulo/nodes/catalog/tools/forged/evidence.authoring.json"},
            {},
        ),
        ({}, {"expected_field_pointer": "/other"}),
    ),
)
def test_compiler_rejects_factory_self_asserted_or_mismatched_text_provenance(
    declared_updates: dict[str, object],
    verified_updates: dict[str, object],
) -> None:
    source_bytes = b'{"description":"Ordinary authored prose."}'
    source_digest = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    declared: dict[str, object] = {"catalog_content_sha256": source_digest}
    declared.update(declared_updates)
    retained = authored("Ordinary authored prose.", "/description", **declared)
    verification: dict[str, object] = {
        "catalog_path": CATALOG_PATH,
        "catalog_content": source_bytes,
        "expected_field_pointer": "/description",
    }
    verification.update(verified_updates)

    with pytest.raises(ValueError, match="provenance"):
        evidence.verify_retained_text_selection(retained, **verification)


@pytest.mark.parametrize(
    "document",
    (
        {"description": "ok", "catalog_content_sha256": SHA_A},
        {"description": "ok", "nested": {"catalog_path": CATALOG_PATH}},
        {"description": "ok", "nested": [{"field_pointer": "/description"}]},
        {"description": "ok", "nested": {"provenance": {"origin": "catalog_author"}}},
    ),
)
def test_authoring_json_rejects_reserved_compiler_provenance_fields_at_any_depth(
    document: dict[str, object],
) -> None:
    source_content = json.dumps(document, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")
    retained = authored(
        "ok",
        "/description",
        catalog_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
    )

    with pytest.raises(ValueError, match="reserved compiler field"):
        evidence.verify_retained_text_selection(
            retained,
            catalog_path=CATALOG_PATH,
            catalog_content=source_content,
            expected_field_pointer="/description",
        )


def test_authoring_prose_may_name_reserved_compiler_fields_as_text() -> None:
    value = "catalog_content_sha256 and provenance are compiler-owned fields."
    source_content = json.dumps(
        {"description": value},
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    retained = authored(
        value,
        "/description",
        catalog_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
    )

    assert (
        evidence.verify_retained_text_selection(
            retained,
            catalog_path=CATALOG_PATH,
            catalog_content=source_content,
            expected_field_pointer="/description",
        )
        == retained
    )


@pytest.mark.parametrize("kind", ("byte_range", "json_pointer", "symbol"))
def test_content_locator_variants_are_strict_frozen_and_json_roundtrip(
    kind: str,
) -> None:
    if kind == "byte_range":
        locator = byte_locator()
    elif kind == "json_pointer":
        locator = evidence.JsonPointerLocator(
            kind=evidence.ContentLocatorKind.JSON_POINTER,
            pointer="/info/version",
        )
    else:
        locator = evidence.SymbolLocator(
            kind=evidence.ContentLocatorKind.SYMBOL,
            symbol="Samtools.Index::output_name",
        )
    asserted = claim(locator=locator)
    rebuilt = evidence.EvidenceClaim.model_validate_json(asserted.model_dump_json())

    assert rebuilt.locator == locator
    assert type(rebuilt.locator) is type(locator)
    assert hash(locator) == hash(rebuilt.locator)


@pytest.mark.parametrize(
    ("start", "end"),
    ((-1, 1), (0, 0), (10, 9), (0, 1_048_577), (2**63, 2**63 + 1)),
)
def test_byte_range_locator_is_ordered_and_bounded(start: int, end: int) -> None:
    with pytest.raises(ValidationError):
        byte_locator(start, end)


def test_content_locator_variants_reject_cross_kind_fields_and_free_text() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        evidence.ByteRangeLocator(
            kind=evidence.ContentLocatorKind.BYTE_RANGE,
            start_byte=0,
            end_byte_exclusive=1,
            pointer="/version",
        )
    with pytest.raises(ValidationError):
        claim(locator="OUTPUT FILES")


@pytest.mark.parametrize("pointer", ("version", "/../version", "/a~2b", "/a//b"))
def test_json_pointer_locator_reuses_canonical_pointer_rules(pointer: str) -> None:
    with pytest.raises(ValidationError):
        evidence.JsonPointerLocator(
            kind=evidence.ContentLocatorKind.JSON_POINTER,
            pointer=pointer,
        )


@pytest.mark.parametrize("symbol", ("", " main", "main ", "main()", "src/main", "main\n"))
def test_symbol_locator_is_an_exact_identity(symbol: str) -> None:
    with pytest.raises(ValidationError):
        evidence.SymbolLocator(
            kind=evidence.ContentLocatorKind.SYMBOL,
            symbol=symbol,
        )


def test_documentation_proof_is_content_addressed_and_digest_stable() -> None:
    retained = proof()
    rebuilt = evidence.DocumentationVersionProof.model_validate_json(retained.model_dump_json())
    changed = proof(proof_content_sha256=SHA_C)

    assert retained == rebuilt
    assert retained.proof_digest() == rebuilt.proof_digest()
    assert retained.proof_digest() != changed.proof_digest()
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", retained.proof_digest())


def test_documentation_proof_verifier_recomputes_source_and_byte_range_digests() -> None:
    source_content = b"header\nsamtools 1.23.1\nfooter"
    selected = b"samtools 1.23.1"
    start = source_content.index(selected)
    retained = proof(
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=byte_locator(start, start + len(selected)),
        proof_content_sha256="sha256:" + hashlib.sha256(selected).hexdigest(),
    )

    assert evidence.verify_documentation_proof_content(retained, source_content=source_content) == retained

    with pytest.raises(ValueError, match="source content"):
        evidence.verify_documentation_proof_content(
            retained.model_copy(update={"source_content_sha256": SHA_A}),
            source_content=source_content,
        )
    with pytest.raises(ValueError, match="locator"):
        evidence.verify_documentation_proof_content(
            retained.model_copy(update={"locator": byte_locator(start, start + len(selected) + 100)}),
            source_content=source_content,
        )


def test_documentation_proof_verifier_canonicalizes_strict_json_pointer_selection() -> None:
    selected = {"tool_id": "samtools", "tool_version": "1.23.1"}
    document = {"metadata": selected}
    source_content = json.dumps(document, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")
    selected_content = json.dumps(selected, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")
    retained = proof(
        proof_kind=evidence.DocumentationProofKind.SCHEMA_FIELD,
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=evidence.JsonPointerLocator(
            kind=evidence.ContentLocatorKind.JSON_POINTER,
            pointer="/metadata",
        ),
        proof_content_sha256="sha256:" + hashlib.sha256(selected_content).hexdigest(),
    )

    assert evidence.verify_documentation_proof_content(retained, source_content=source_content) == retained


def test_evidence_claim_verifier_recomputes_source_and_byte_range_digests() -> None:
    source_content = b"header\ndefault output is input.bam.bai\nfooter"
    selected = b"default output is input.bam.bai"
    start = source_content.index(selected)
    asserted = claim(
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=byte_locator(start, start + len(selected)),
        excerpt_sha256="sha256:" + hashlib.sha256(selected).hexdigest(),
    )

    assert verify_claim(asserted, source_content) == asserted

    with pytest.raises(ValueError, match="source content"):
        verify_claim(
            asserted.model_copy(update={"source_content_sha256": SHA_A}),
            source_content,
        )
    with pytest.raises(ValueError, match="locator"):
        verify_claim(
            asserted.model_copy(update={"locator": byte_locator(start, start + len(selected) + 100)}),
            source_content,
        )
    with pytest.raises(ValueError, match="excerpt"):
        verify_claim(
            asserted.model_copy(update={"excerpt_sha256": SHA_A}),
            source_content,
        )


def test_evidence_claim_verifier_recomputes_contract_value_digest() -> None:
    source_content = b"selected"
    asserted = claim(
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=byte_locator(0, len(source_content)),
        excerpt_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        contract_value_sha256=SHA_A,
    )

    with pytest.raises(ValueError, match="contract value"):
        verify_claim(asserted, source_content)


def test_evidence_claim_verifier_requires_exact_compiler_contract_pointer() -> None:
    source_content = b"selected"
    asserted = claim(
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=byte_locator(0, len(source_content)),
        excerpt_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
    )

    with pytest.raises(ValueError, match="contract pointer"):
        verify_claim(
            asserted,
            source_content,
            expected_contract_pointer="/outputs/index/path_rule",
        )


def test_evidence_claim_verifier_requires_both_compiler_contract_arguments() -> None:
    source_content = b"selected"
    asserted = claim(
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=byte_locator(0, len(source_content)),
        excerpt_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
    )

    with pytest.raises(TypeError, match="expected_contract_pointer"):
        evidence.verify_evidence_claim_content(
            asserted,
            source_content=source_content,
            contract_value=DEFAULT_CONTRACT_VALUE,
        )
    with pytest.raises(TypeError, match="contract_value"):
        evidence.verify_evidence_claim_content(
            asserted,
            source_content=source_content,
            expected_contract_pointer=asserted.contract_pointer,
        )


def test_evidence_claim_verifier_canonicalizes_strict_json_pointer_selection() -> None:
    selected = {"collector": "index", "suffixes": [".bai", ".csi"]}
    document = {"outputs": {"index": selected}}
    source_content = json.dumps(document, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")
    selected_content = json.dumps(selected, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")
    asserted = claim(
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=evidence.JsonPointerLocator(
            kind=evidence.ContentLocatorKind.JSON_POINTER,
            pointer="/outputs/index",
        ),
        excerpt_sha256="sha256:" + hashlib.sha256(selected_content).hexdigest(),
    )

    assert verify_claim(asserted, source_content) == asserted


def test_json_number_canonicalization_distinguishes_adjacent_large_decimals() -> None:
    cases = (
        (b"9007199254740992.0", b"9.007199254740992e15"),
        (b"9007199254740993.0", b"9.007199254740993e15"),
    )
    canonical_digests: list[str] = []

    for literal, canonical in cases:
        source_content = b'{"value":' + literal + b"}"
        source_digest = "sha256:" + hashlib.sha256(source_content).hexdigest()
        selected_digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
        canonical_digests.append(selected_digest)
        retained_proof = proof(
            proof_kind=evidence.DocumentationProofKind.SCHEMA_FIELD,
            source_content_sha256=source_digest,
            locator=evidence.JsonPointerLocator(
                kind=evidence.ContentLocatorKind.JSON_POINTER,
                pointer="/value",
            ),
            proof_content_sha256=selected_digest,
        )
        asserted = claim(
            source_content_sha256=source_digest,
            locator=evidence.JsonPointerLocator(
                kind=evidence.ContentLocatorKind.JSON_POINTER,
                pointer="/value",
            ),
            excerpt_sha256=selected_digest,
            contract_value_sha256=selected_digest,
        )

        assert (
            evidence.verify_documentation_proof_content(retained_proof, source_content=source_content) == retained_proof
        )
        assert (
            verify_claim(
                asserted,
                source_content,
                contract_value=Decimal(literal.decode("ascii")),
            )
            == asserted
        )

    assert canonical_digests[0] != canonical_digests[1]


@pytest.mark.parametrize(
    ("source_literal", "contract_value"),
    (
        (b"1", 1),
        (b"1.0", Decimal("1.0")),
        (b"1e0", Decimal("1e0")),
    ),
)
def test_equivalent_json_number_spellings_share_one_canonical_form(
    source_literal: bytes,
    contract_value: int | Decimal,
) -> None:
    source_content = b'{"value":' + source_literal + b"}"
    source_digest = "sha256:" + hashlib.sha256(source_content).hexdigest()
    canonical_digest = "sha256:" + hashlib.sha256(b"1").hexdigest()
    asserted = claim(
        source_content_sha256=source_digest,
        locator=evidence.JsonPointerLocator(
            kind=evidence.ContentLocatorKind.JSON_POINTER,
            pointer="/value",
        ),
        excerpt_sha256=canonical_digest,
        contract_value_sha256=canonical_digest,
    )

    assert verify_claim(asserted, source_content, contract_value=contract_value) == asserted


def test_contract_decimal_canonicalization_ignores_ambient_context() -> None:
    contract_value = Decimal("123456789.987654321")
    canonical = b"1.23456789987654321e8"
    source_content = b"selected"
    asserted = claim(
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=byte_locator(0, len(source_content)),
        excerpt_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        contract_value_sha256="sha256:" + hashlib.sha256(canonical).hexdigest(),
    )

    with localcontext() as context:
        context.prec = 3
        assert verify_claim(asserted, source_content, contract_value=contract_value) == asserted


@pytest.mark.parametrize(
    "number",
    (
        "1" + "2" * (MAX_JSON_NUMBER_COEFFICIENT_DIGITS - 1),
        f"1e{MAX_JSON_NUMBER_EXPONENT}",
        f"1e-{MAX_JSON_NUMBER_EXPONENT}",
        f"9.9e{MAX_JSON_NUMBER_EXPONENT}",
        f"0.1e-{MAX_JSON_NUMBER_EXPONENT - 1}",
    ),
)
def test_strict_json_accepts_numbers_at_repository_owned_limits(number: str) -> None:
    source_content = f'{{"description":"ok","number":{number}}}'.encode("ascii")
    retained = authored(
        "ok",
        "/description",
        catalog_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
    )

    assert (
        evidence.verify_retained_text_selection(
            retained,
            catalog_path=CATALOG_PATH,
            catalog_content=source_content,
            expected_field_pointer="/description",
        )
        == retained
    )


@pytest.mark.parametrize(
    "number",
    (
        "1" + "2" * MAX_JSON_NUMBER_COEFFICIENT_DIGITS,
        f"1e{MAX_JSON_NUMBER_EXPONENT + 1}",
        f"1e-{MAX_JSON_NUMBER_EXPONENT + 1}",
        f"99e{MAX_JSON_NUMBER_EXPONENT}",
        f"0.1e-{MAX_JSON_NUMBER_EXPONENT}",
    ),
)
def test_strict_json_rejects_numbers_beyond_repository_owned_limits(number: str) -> None:
    source_content = f'{{"description":"ok","number":{number}}}'.encode("ascii")
    retained = authored(
        "ok",
        "/description",
        catalog_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
    )

    with pytest.raises(ValueError, match="JSON number"):
        evidence.verify_retained_text_selection(
            retained,
            catalog_path=CATALOG_PATH,
            catalog_content=source_content,
            expected_field_pointer="/description",
        )


def test_json_integer_policy_is_independent_of_python_digit_limit() -> None:
    script = f"""
import hashlib
from bionodulo.nodes.contract.evidence import (
    RetainedText,
    RetainedTextOrigin,
    RetainedTextProvenance,
    verify_retained_text_selection,
)

content = b'{{"description":"ok","number":' + b'1' * 700 + b'}}'
retained = RetainedText(
    value="ok",
    provenance=RetainedTextProvenance(
        origin=RetainedTextOrigin.CATALOG_AUTHOR,
        catalog_path={CATALOG_PATH!r},
        catalog_content_sha256="sha256:" + hashlib.sha256(content).hexdigest(),
        field_pointer="/description",
    ),
)
try:
    verify_retained_text_selection(
        retained,
        catalog_path={CATALOG_PATH!r},
        catalog_content=content,
        expected_field_pointer="/description",
    )
except Exception as error:
    print(type(error).__name__ + ":" + str(error))
else:
    print("accepted")
"""
    outputs: list[str] = []
    project_root = Path(__file__).parents[2]
    for digit_limit in ("640", "0"):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=project_root,
            env={**os.environ, "PYTHONINTMAXSTRDIGITS": digit_limit},
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout.strip())

    assert outputs[0] == outputs[1]
    assert "JSON number coefficient may have at most 256 digits" in outputs[0]


@pytest.mark.parametrize(
    "verifier",
    ("retained_text", "documentation_proof", "evidence_claim"),
)
def test_json_verifiers_enforce_exact_input_byte_bound(verifier: str) -> None:
    payload = b'{"value":"ok"}'
    at_limit = b" " * (MAX_JSON_INPUT_BYTES - len(payload)) + payload
    beyond_limit = b" " + at_limit

    verify_json_source(verifier, at_limit)
    with pytest.raises(ValueError, match=f"at most {MAX_JSON_INPUT_BYTES} bytes"):
        verify_json_source(verifier, beyond_limit)


@pytest.mark.parametrize(
    "verifier",
    ("retained_text", "documentation_proof", "evidence_claim"),
)
def test_json_verifiers_enforce_exact_structural_nesting_bound(verifier: str) -> None:
    def nested_source(depth: int) -> bytes:
        nested_arrays = depth - 1
        return b'{"value":"ok","nested":' + b"[" * nested_arrays + b"null" + b"]" * nested_arrays + b"}"

    verify_json_source(verifier, nested_source(MAX_JSON_NESTING_DEPTH))
    with pytest.raises(ValueError, match=f"nesting depth may be at most {MAX_JSON_NESTING_DEPTH}"):
        verify_json_source(verifier, nested_source(MAX_JSON_NESTING_DEPTH + 1))


def test_json_nesting_scanner_ignores_structural_characters_and_escapes_inside_strings() -> None:
    source_content = json.dumps(
        {
            "value": "ok",
            "text": "[" * 65 + "{" * 65 + 'escaped quote: " and slash: \\',
        },
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")

    verify_json_source("retained_text", source_content)


def test_json_decoder_recursion_error_is_controlled(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_recursion_error(*_args: object, **_kwargs: object) -> object:
        raise RecursionError("decoder recursion")

    monkeypatch.setattr(evidence.json, "loads", raise_recursion_error)

    with pytest.raises(ValueError, match="strict JSON"):
        verify_json_source("retained_text", b'{"value":"ok"}')


@pytest.mark.parametrize("target", ("selected_value", "contract_value"))
def test_canonical_json_output_is_bounded_for_selected_and_contract_values(target: str) -> None:
    def verify_value(value: str) -> None:
        canonical = b'"' + value.encode("ascii") + b'"'
        selected_digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
        if target == "selected_value":
            source_content = json.dumps(
                {"value": value},
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode("ascii")
            evidence.verify_documentation_proof_content(
                proof(
                    proof_kind=evidence.DocumentationProofKind.SCHEMA_FIELD,
                    source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
                    locator=evidence.JsonPointerLocator(
                        kind=evidence.ContentLocatorKind.JSON_POINTER,
                        pointer="/value",
                    ),
                    proof_content_sha256=selected_digest,
                ),
                source_content=source_content,
            )
        else:
            source_content = b"selected"
            verify_claim(
                claim(
                    source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
                    locator=byte_locator(0, len(source_content)),
                    excerpt_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
                    contract_value_sha256=selected_digest,
                ),
                source_content,
                contract_value=value,
            )

    verify_value("x" * (MAX_CANONICAL_JSON_BYTES - 2))
    with pytest.raises(ValueError, match=f"canonical JSON may be at most {MAX_CANONICAL_JSON_BYTES} bytes"):
        verify_value("x" * (MAX_CANONICAL_JSON_BYTES - 1))


def test_compiler_contract_value_enforces_independent_nesting_bound() -> None:
    def nested_value(depth: int) -> tuple[list[object], bytes]:
        value: object = None
        for _ in range(depth):
            value = [value]
        assert isinstance(value, list)
        canonical = b"[" * depth + b"null" + b"]" * depth
        return value, canonical

    source_content = b"selected"
    at_limit, at_limit_canonical = nested_value(MAX_JSON_NESTING_DEPTH)
    at_limit_claim = claim(
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=byte_locator(0, len(source_content)),
        excerpt_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        contract_value_sha256="sha256:" + hashlib.sha256(at_limit_canonical).hexdigest(),
    )
    assert verify_claim(at_limit_claim, source_content, contract_value=at_limit) == at_limit_claim

    beyond_limit, beyond_limit_canonical = nested_value(MAX_JSON_NESTING_DEPTH + 1)
    beyond_limit_claim = at_limit_claim.model_copy(
        update={
            "contract_value_sha256": "sha256:" + hashlib.sha256(beyond_limit_canonical).hexdigest(),
        }
    )
    with pytest.raises(ValueError, match=f"nesting depth may be at most {MAX_JSON_NESTING_DEPTH}"):
        verify_claim(beyond_limit_claim, source_content, contract_value=beyond_limit)


@pytest.mark.parametrize("container_kind", ("list", "dict"))
def test_compiler_contract_value_rejects_container_cycles_cleanly(container_kind: str) -> None:
    if container_kind == "list":
        contract_value: object = []
        assert isinstance(contract_value, list)
        contract_value.append(contract_value)
    else:
        contract_value = {}
        assert isinstance(contract_value, dict)
        contract_value["self"] = contract_value

    source_content = b"selected"
    asserted = claim(
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=byte_locator(0, len(source_content)),
        excerpt_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
    )
    with pytest.raises(ValueError, match="container cycles"):
        verify_claim(asserted, source_content, contract_value=contract_value)


@pytest.mark.parametrize(
    "source_content",
    (
        b'{"outputs":{"index":"first","index":"second"}}',
        b'{"outputs":{"index":"value"},"number":NaN}',
        b'\xff{"outputs":{"index":"value"}}',
    ),
)
def test_evidence_claim_verifier_rejects_ambiguous_json_pointer_sources(source_content: bytes) -> None:
    asserted = claim(
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=evidence.JsonPointerLocator(
            kind=evidence.ContentLocatorKind.JSON_POINTER,
            pointer="/outputs/index",
        ),
    )

    with pytest.raises(ValueError, match="strict JSON"):
        verify_claim(asserted, source_content)


def test_evidence_claim_verifier_requires_a_trusted_symbol_selector() -> None:
    source_content = b"static int bam_sort_core_ext(void) { return 0; }"
    selected = b"int bam_sort_core_ext(void) { return 0; }"
    asserted = claim(
        source_id="samtools-upstream-source",
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=evidence.SymbolLocator(
            kind=evidence.ContentLocatorKind.SYMBOL,
            symbol="bam_sort_core_ext",
        ),
        excerpt_sha256="sha256:" + hashlib.sha256(selected).hexdigest(),
    )
    calls: list[tuple[bytes, str]] = []

    def trusted_selector(content: bytes, symbol: str) -> bytes:
        calls.append((content, symbol))
        return selected

    with pytest.raises(ValueError, match="trusted language-aware symbol selector"):
        verify_claim(asserted, source_content)

    assert (
        verify_claim(
            asserted,
            source_content,
            symbol_selector=trusted_selector,
        )
        == asserted
    )
    assert calls == [(source_content, "bam_sort_core_ext")]

    with pytest.raises(ValueError, match="excerpt"):
        verify_claim(
            asserted,
            source_content,
            symbol_selector=lambda _content, _symbol: b"different symbol bytes",
        )
    with pytest.raises(TypeError, match="exact bytes"):
        verify_claim(
            asserted,
            source_content,
            symbol_selector=lambda _content, _symbol: "not bytes",  # type: ignore[return-value]
        )


@pytest.mark.parametrize(
    "forged_update",
    (
        {"contract_pointer": "not-a-pointer"},
        {"contract_value_sha256": "not-a-digest"},
    ),
)
def test_evidence_claim_verifier_revalidates_constructed_claims_and_exact_bytes(
    forged_update: dict[str, object],
) -> None:
    source_content = b"selected"
    valid = claim(
        source_content_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
        locator=byte_locator(0, len(source_content)),
        excerpt_sha256="sha256:" + hashlib.sha256(source_content).hexdigest(),
    )
    forged = evidence.EvidenceClaim.model_construct(
        **(valid.model_dump() | forged_update),
    )

    with pytest.raises(ValidationError):
        verify_claim(forged, source_content)
    with pytest.raises(TypeError, match="exact captured bytes"):
        verify_claim(
            claim(),
            bytearray(source_content),  # type: ignore[arg-type]
        )


def test_documentation_proof_rejects_unresolvable_symbol_locator() -> None:
    with pytest.raises(ValidationError):
        proof(
            locator=evidence.SymbolLocator(
                kind=evidence.ContentLocatorKind.SYMBOL,
                symbol="Samtools.Index::version",
            )
        )


def test_json_pointer_documentation_proof_requires_json_source_content() -> None:
    pointer_proof = proof(
        proof_kind=evidence.DocumentationProofKind.SCHEMA_FIELD,
        locator=evidence.JsonPointerLocator(
            kind=evidence.ContentLocatorKind.JSON_POINTER,
            pointer="/metadata/version",
        ),
    )

    with pytest.raises(ValidationError, match="content format"):
        source(
            evidence.SourceKind.OFFICIAL_MANUAL,
            content_format=evidence.SourceContentFormat.TEXT,
            documentation_proof=pointer_proof,
        )

    captured = source(
        evidence.SourceKind.OFFICIAL_MANUAL,
        content_format=evidence.SourceContentFormat.JSON,
        documentation_proof=pointer_proof,
    )
    assert captured.documentation_proof == pointer_proof


@pytest.mark.parametrize("content_format", tuple(evidence.SourceContentFormat))
def test_byte_range_documentation_proof_is_valid_for_each_official_source_format(
    content_format: evidence.SourceContentFormat,
) -> None:
    captured = source(
        evidence.SourceKind.OFFICIAL_MANUAL,
        content_format=content_format,
        documentation_proof=proof(locator=byte_locator(10, 40)),
    )

    assert isinstance(captured.documentation_proof.locator, evidence.ByteRangeLocator)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("tool_id", "bcftools"),
        ("tool_version", "9.9"),
        ("source_url", "https://docs.example.org/other/reference.html"),
        ("source_content_sha256", SHA_C),
    ),
)
def test_official_documentation_proof_must_match_enclosing_source(field: str, value: str) -> None:
    captured = source(evidence.SourceKind.OFFICIAL_MANUAL)
    assert captured.documentation_proof is not None
    mismatched = captured.documentation_proof.model_copy(update={field: value})

    with pytest.raises(ValidationError, match="documentation proof"):
        captured.model_copy(update={"documentation_proof": mismatched})


@pytest.mark.parametrize("kind", (evidence.SourceKind.OFFICIAL_MANUAL, evidence.SourceKind.OFFICIAL_API_SCHEMA))
def test_official_documentation_requires_an_explicit_version_proof(kind: evidence.SourceKind) -> None:
    with pytest.raises(ValidationError, match="documentation_proof"):
        source(kind, documentation_proof=None)


def test_url_path_versions_and_moving_segments_never_infer_document_ownership() -> None:
    url = "https://docs.example.org/api/99.7/latest/dependencies/other-tool/3.4/reference.html"
    captured = source(
        evidence.SourceKind.OFFICIAL_MANUAL,
        url=url,
        documentation_proof=proof(source_url=url),
    )

    assert captured.tool_id == "samtools"
    assert captured.tool_version == "1.23.1"
    assert captured.url == url


@pytest.mark.parametrize(
    "url",
    (
        "http://docs.example.org/manual.html",
        "https://user@docs.example.org/manual.html",
        "https://docs.example.org/manual.html?version=1.23.1",
        "https://DOCS.example.org/manual.html",
        "https://docs.example.org/a/../manual.html",
        "https://docs.example.org/manual path.html",
    ),
)
def test_source_urls_remain_canonical_credential_free_https(url: str) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.OFFICIAL_MANUAL, url=url)


@pytest.mark.parametrize("kind", tuple(evidence.SourceKind))
def test_each_source_kind_has_a_valid_minimal_immutable_json_roundtrip(kind: evidence.SourceKind) -> None:
    captured = source(kind)
    rebuilt = evidence.EvidenceSource.model_validate_json(captured.model_dump_json())

    assert rebuilt == captured
    assert hash(rebuilt) == hash(captured)
    assert rebuilt.kind is kind


@pytest.mark.parametrize(
    ("kind", "field"),
    (
        (evidence.SourceKind.OFFICIAL_MANUAL, "url"),
        (evidence.SourceKind.OFFICIAL_MANUAL, "documentation_proof"),
        (evidence.SourceKind.OFFICIAL_API_SCHEMA, "url"),
        (evidence.SourceKind.OFFICIAL_API_SCHEMA, "documentation_proof"),
        (evidence.SourceKind.PACKAGE_RECIPE, "url"),
        (evidence.SourceKind.PACKAGE_RECIPE, "recipe_revision"),
        (evidence.SourceKind.PACKAGE_RECIPE, "recipe_path"),
        (evidence.SourceKind.UPSTREAM_SOURCE, "url"),
        (evidence.SourceKind.UPSTREAM_SOURCE, "commit"),
        (evidence.SourceKind.UPSTREAM_SOURCE, "source_path"),
        (evidence.SourceKind.INSTALLED_HELP, "environment_digest"),
        (evidence.SourceKind.INSTALLED_HELP, "executable_probe_id"),
        (evidence.SourceKind.INSTALLED_HELP, "argv"),
        (evidence.SourceKind.INSTALLED_HELP, "output_sha256"),
    ),
)
def test_source_kinds_fail_closed_when_required_kind_fields_are_missing(
    kind: evidence.SourceKind,
    field: str,
) -> None:
    with pytest.raises(ValidationError):
        source(kind).model_copy(update={field: None})


@pytest.mark.parametrize(
    ("kind", "updates"),
    (
        (evidence.SourceKind.OFFICIAL_MANUAL, {"commit": COMMIT_A}),
        (evidence.SourceKind.OFFICIAL_API_SCHEMA, {"recipe_revision": COMMIT_A}),
        (evidence.SourceKind.PACKAGE_RECIPE, {"documentation_proof": "present"}),
        (evidence.SourceKind.UPSTREAM_SOURCE, {"documentation_proof": "present"}),
        (evidence.SourceKind.INSTALLED_HELP, {"url": "https://docs.example.org/help"}),
    ),
)
def test_source_kinds_reject_irrelevant_cross_kind_fields(
    kind: evidence.SourceKind,
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        source(kind).model_copy(update=updates)


@pytest.mark.parametrize(
    "path",
    ("bam_sort.c", "src/samtools.c", "include/htslib/sam.h", "src/_internal.py", ".github/schema.json"),
)
def test_repository_source_paths_are_canonical_relative_posix(path: str) -> None:
    captured = source(
        evidence.SourceKind.UPSTREAM_SOURCE,
        source_path=path,
        url=f"https://github.com/samtools/samtools/blob/{COMMIT_A}/{path}",
    )

    assert captured.source_path == path


@pytest.mark.parametrize(
    "path",
    ("/src/main.c", "src/../main.c", "src//main.c", "src\\main.c", "src/main file.c", "src/main.c/"),
)
def test_repository_source_paths_reject_absolute_host_and_noncanonical_forms(path: str) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.UPSTREAM_SOURCE, source_path=path)


@pytest.mark.parametrize(
    ("url", "path"),
    (
        (f"https://github.com/samtools/samtools/blob/{COMMIT_A}x/src/main.c", "src/main.c"),
        (f"https://github.com/samtools/samtools/blob/prefix-{COMMIT_A}/src/main.c", "src/main.c"),
        (f"https://github.com/samtools/samtools/blob/{COMMIT_A}/src/other.c", "src/main.c"),
    ),
)
def test_upstream_url_binding_compares_exact_parsed_path_segments(url: str, path: str) -> None:
    with pytest.raises(ValidationError, match="commit and source path"):
        source(evidence.SourceKind.UPSTREAM_SOURCE, url=url, source_path=path)


@pytest.mark.parametrize(
    "argv",
    (("--help",), ("-h",), ("view", "--help"), ("help", "view")),
)
def test_installed_help_retains_literal_structured_argv(argv: tuple[str, ...]) -> None:
    assert source(evidence.SourceKind.INSTALLED_HELP, argv=argv).argv == argv


@pytest.mark.parametrize(
    "argv",
    (
        ("tool --help",),
        ("/usr/bin/tool", "--help"),
        ("--token", "Swordfish"),
        ("--help;env",),
        ["--help"],
    ),
)
def test_installed_help_rejects_commands_paths_credentials_and_collection_coercion(argv: object) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.INSTALLED_HELP, argv=argv)


def test_installed_help_output_digest_equals_source_content_digest() -> None:
    with pytest.raises(ValidationError, match="output digest"):
        source(evidence.SourceKind.INSTALLED_HELP, output_sha256=SHA_C)


def test_evidence_record_binds_claims_to_known_source_content() -> None:
    with pytest.raises(ValidationError, match="missing source"):
        evidence_record(claims=(claim(source_id="missing"),))
    with pytest.raises(ValidationError, match="source content digest"):
        evidence_record(claims=(claim(source_content_sha256=SHA_D),))


@pytest.mark.parametrize("field", ("sources", "claims"))
def test_evidence_record_requires_sources_and_claims(field: str) -> None:
    with pytest.raises(ValidationError):
        evidence_record(**{field: ()})


def test_package_recipe_claims_are_limited_to_environment_packages() -> None:
    recipe = source(evidence.SourceKind.PACKAGE_RECIPE)
    accepted = claim(
        source_id=recipe.source_id,
        contract_pointer="/environment/packages/0/constraint",
    )
    assert evidence_record(sources=(recipe,), claims=(accepted,)).claims == (accepted,)

    rejected = accepted.model_copy(update={"contract_pointer": "/outputs/index"})
    with pytest.raises(ValidationError, match="package"):
        evidence_record(sources=(recipe,), claims=(rejected,))


@pytest.mark.parametrize(
    ("kind", "content_format", "locator"),
    (
        (evidence.SourceKind.OFFICIAL_MANUAL, "text", byte_locator()),
        (evidence.SourceKind.OFFICIAL_API_SCHEMA, "json", byte_locator()),
        (
            evidence.SourceKind.OFFICIAL_API_SCHEMA,
            "json",
            evidence.JsonPointerLocator(kind=evidence.ContentLocatorKind.JSON_POINTER, pointer="/version"),
        ),
        (evidence.SourceKind.UPSTREAM_SOURCE, "source_code", byte_locator()),
        (
            evidence.SourceKind.UPSTREAM_SOURCE,
            "source_code",
            evidence.SymbolLocator(
                kind=evidence.ContentLocatorKind.SYMBOL,
                symbol="bam_sort_core_ext",
            ),
        ),
        (
            evidence.SourceKind.UPSTREAM_SOURCE,
            "json",
            evidence.JsonPointerLocator(kind=evidence.ContentLocatorKind.JSON_POINTER, pointer="/version"),
        ),
        (evidence.SourceKind.INSTALLED_HELP, "text", byte_locator()),
        (
            evidence.SourceKind.INSTALLED_HELP,
            "json",
            evidence.JsonPointerLocator(kind=evidence.ContentLocatorKind.JSON_POINTER, pointer="/version"),
        ),
        (evidence.SourceKind.PACKAGE_RECIPE, "text", byte_locator()),
        (
            evidence.SourceKind.PACKAGE_RECIPE,
            "json",
            evidence.JsonPointerLocator(kind=evidence.ContentLocatorKind.JSON_POINTER, pointer="/package/version"),
        ),
    ),
)
def test_claim_locator_compatibility_table_accepts_only_resolvable_source_forms(
    kind: evidence.SourceKind,
    content_format: str,
    locator: evidence.ContentLocator,
) -> None:
    source_updates: dict[str, object] = {"content_format": evidence.SourceContentFormat(content_format)}
    if kind is evidence.SourceKind.UPSTREAM_SOURCE and content_format != "source_code":
        source_updates["symbol_locator"] = None
    captured = source(kind, **source_updates)
    asserted = claim(
        source_id=captured.source_id,
        source_content_sha256=captured.content_sha256,
        contract_pointer=(
            "/environment/packages/0" if kind is evidence.SourceKind.PACKAGE_RECIPE else "/outputs/index"
        ),
        locator=locator,
    )

    assert evidence_record(sources=(captured,), claims=(asserted,)).claims == (asserted,)


@pytest.mark.parametrize(
    ("kind", "content_format", "locator"),
    (
        (
            evidence.SourceKind.OFFICIAL_MANUAL,
            "text",
            evidence.JsonPointerLocator(kind=evidence.ContentLocatorKind.JSON_POINTER, pointer="/version"),
        ),
        (
            evidence.SourceKind.UPSTREAM_SOURCE,
            "source_code",
            evidence.JsonPointerLocator(kind=evidence.ContentLocatorKind.JSON_POINTER, pointer="/version"),
        ),
        (
            evidence.SourceKind.INSTALLED_HELP,
            "text",
            evidence.JsonPointerLocator(kind=evidence.ContentLocatorKind.JSON_POINTER, pointer="/version"),
        ),
        (
            evidence.SourceKind.PACKAGE_RECIPE,
            "text",
            evidence.JsonPointerLocator(kind=evidence.ContentLocatorKind.JSON_POINTER, pointer="/version"),
        ),
        (
            evidence.SourceKind.OFFICIAL_MANUAL,
            "text",
            evidence.SymbolLocator(kind=evidence.ContentLocatorKind.SYMBOL, symbol="Fake::symbol"),
        ),
        (
            evidence.SourceKind.OFFICIAL_API_SCHEMA,
            "json",
            evidence.SymbolLocator(kind=evidence.ContentLocatorKind.SYMBOL, symbol="Fake::symbol"),
        ),
        (
            evidence.SourceKind.INSTALLED_HELP,
            "text",
            evidence.SymbolLocator(kind=evidence.ContentLocatorKind.SYMBOL, symbol="Fake::symbol"),
        ),
        (
            evidence.SourceKind.PACKAGE_RECIPE,
            "text",
            evidence.SymbolLocator(kind=evidence.ContentLocatorKind.SYMBOL, symbol="Fake::symbol"),
        ),
        (
            evidence.SourceKind.UPSTREAM_SOURCE,
            "source_code",
            evidence.SymbolLocator(kind=evidence.ContentLocatorKind.SYMBOL, symbol="different_symbol"),
        ),
    ),
)
def test_claim_locator_compatibility_table_rejects_unresolvable_source_forms(
    kind: evidence.SourceKind,
    content_format: str,
    locator: evidence.ContentLocator,
) -> None:
    captured = source(kind, content_format=evidence.SourceContentFormat(content_format))
    asserted = claim(
        source_id=captured.source_id,
        source_content_sha256=captured.content_sha256,
        contract_pointer=(
            "/environment/packages/0" if kind is evidence.SourceKind.PACKAGE_RECIPE else "/outputs/index"
        ),
        locator=locator,
    )

    with pytest.raises(ValidationError, match="locator"):
        evidence_record(sources=(captured,), claims=(asserted,))


def test_sources_claims_and_verifications_are_unique_and_canonically_ordered() -> None:
    manual = source(evidence.SourceKind.OFFICIAL_MANUAL, source_id="a-manual")
    upstream = source(evidence.SourceKind.UPSTREAM_SOURCE, source_id="z-source")
    manual_claim = claim(claim_id="a-claim", source_id=manual.source_id)
    upstream_claim = claim(
        claim_id="z-claim",
        source_id=upstream.source_id,
        contract_pointer="/outputs/index/path",
    )
    first = verification("a-verification")
    second = verification("z-verification", test_id="samtools-view-tiny-bam-v1")
    accepted = evidence_record(
        sources=(manual, upstream),
        claims=(manual_claim, upstream_claim),
        verifications=(first, second),
    )
    assert len(accepted.sources) == 2

    for updates in (
        {"claims": (upstream_claim, manual_claim)},
        {"verifications": (second, first)},
        {"claims": (manual_claim, manual_claim)},
        {"verifications": (first, first)},
    ):
        with pytest.raises(ValidationError):
            evidence_record(sources=(manual, upstream), **updates)


def test_sources_use_authoritative_kind_precedence_then_source_id_order() -> None:
    manual = source(evidence.SourceKind.OFFICIAL_MANUAL)
    upstream = source(evidence.SourceKind.UPSTREAM_SOURCE)
    asserted = claim(source_id=manual.source_id)

    assert evidence_record(sources=(manual, upstream), claims=(asserted,)).sources == (manual, upstream)
    with pytest.raises(ValidationError, match="precedence"):
        evidence_record(sources=(upstream, manual), claims=(asserted,))


def test_duplicate_and_conflicting_source_capture_provenance_is_rejected() -> None:
    original = source(evidence.SourceKind.OFFICIAL_MANUAL, source_id="a-manual")
    alias = source(
        evidence.SourceKind.OFFICIAL_MANUAL,
        source_id="z-manual",
        title=authored("Renamed manual", "/sources/z/title"),
        retrieved_at=date(2026, 7, 16),
    )

    with pytest.raises(ValidationError, match="duplicate source capture"):
        evidence_record(sources=(original, alias), claims=(claim(source_id=original.source_id),))

    conflicting = alias.model_copy(
        update={
            "content_sha256": SHA_D,
            "documentation_proof": proof(source_content_sha256=SHA_D),
        }
    )
    with pytest.raises(ValidationError, match="conflicting source capture"):
        evidence_record(sources=(original, conflicting), claims=(claim(source_id=original.source_id),))


def test_duplicate_and_conflicting_documentation_proofs_are_rejected() -> None:
    original = source(evidence.SourceKind.OFFICIAL_MANUAL, source_id="a-manual")
    duplicate = source(evidence.SourceKind.OFFICIAL_API_SCHEMA, source_id="z-schema")
    asserted = claim(source_id=original.source_id)

    with pytest.raises(ValidationError, match="duplicate documentation proof"):
        evidence_record(sources=(original, duplicate), claims=(asserted,))

    assert duplicate.documentation_proof is not None
    conflicting = duplicate.model_copy(
        update={"documentation_proof": duplicate.documentation_proof.model_copy(update={"proof_content_sha256": SHA_C})}
    )
    with pytest.raises(ValidationError, match="conflicting documentation proof"):
        evidence_record(sources=(original, conflicting), claims=(asserted,))


def test_claim_bindings_reject_conflicts_and_duplicate_sources() -> None:
    manual = source(evidence.SourceKind.OFFICIAL_MANUAL)
    upstream = source(evidence.SourceKind.UPSTREAM_SOURCE)
    original = claim()
    independent = claim(
        claim_id="upstream-output-collector",
        source_id=upstream.source_id,
        excerpt_sha256=SHA_D,
    )
    assert len(evidence_record(sources=(manual, upstream), claims=(original, independent)).claims) == 2

    same_source = claim(claim_id="same-source", excerpt_sha256=SHA_D)
    with pytest.raises(ValidationError, match="distinct sources"):
        evidence_record(claims=(original, same_source))

    conflicting_value = independent.model_copy(update={"contract_value_sha256": SHA_D})
    with pytest.raises(ValidationError, match="conflicting contract values"):
        evidence_record(sources=(manual, upstream), claims=(original, conflicting_value))


def test_verification_outcome_and_failure_code_are_structured_and_kind_compatible() -> None:
    failed = verification(
        outcome=evidence.VerificationOutcome.FAILED,
        failure_code=evidence.FailureCode.TOOL_SMOKE_FAILED,
    )
    assert failed.failure_code is evidence.FailureCode.TOOL_SMOKE_FAILED

    with pytest.raises(ValidationError, match="failure code"):
        verification(failure_code=evidence.FailureCode.TOOL_SMOKE_FAILED)
    with pytest.raises(ValidationError, match="failure code"):
        verification(outcome=evidence.VerificationOutcome.FAILED, failure_code=None)
    with pytest.raises(ValidationError, match="failure code"):
        verification(
            outcome=evidence.VerificationOutcome.FAILED,
            failure_code=evidence.FailureCode.CLOUD_RUN_FAILED,
        )


@pytest.mark.parametrize("kind", tuple(evidence.VerificationKind))
@pytest.mark.parametrize("outcome", tuple(evidence.VerificationOutcome))
def test_each_verification_kind_requires_its_minimal_context_for_pass_and_failure(
    kind: evidence.VerificationKind,
    outcome: evidence.VerificationOutcome,
) -> None:
    retained = verification_with_minimal_context(kind, outcome)
    assert retained.kind is kind
    assert retained.outcome is outcome

    for field in _REQUIRED_VERIFICATION_CONTEXT[kind]:
        with pytest.raises(ValidationError, match="required context"):
            retained.model_copy(update={field: None})


@pytest.mark.parametrize(
    ("kind", "updates"),
    (
        (evidence.VerificationKind.INVENTORY, {"environment_sha256": SHA_A}),
        (
            evidence.VerificationKind.ENVIRONMENT_PROBE,
            {"fixture_id": "fixture-v1", "fixture_sha256": SHA_A},
        ),
        (evidence.VerificationKind.TOOL_SMOKE, {"release_sha256": SHA_A}),
    ),
)
def test_verification_kinds_reject_semantically_irrelevant_context(
    kind: evidence.VerificationKind,
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="irrelevant context"):
        verification_with_minimal_context(kind).model_copy(update=updates)


def test_verification_ui_text_is_computed_from_codes_and_not_serialized() -> None:
    passed = verification()
    failed = verification(
        outcome=evidence.VerificationOutcome.FAILED,
        failure_code=evidence.FailureCode.TOOL_SMOKE_FAILED,
    )

    assert passed.ui_summary == "Tool smoke verification passed"
    assert passed.ui_reason is None
    assert failed.ui_summary == "Tool smoke verification failed"
    assert failed.ui_reason == "Pinned tool smoke verification failed"
    for dumped in (passed.model_dump(), failed.model_dump()):
        assert not {"summary", "reason", "ui_summary", "ui_reason"} & dumped.keys()


def test_verification_fixture_identity_is_all_or_nothing_and_digest_stable() -> None:
    retained = verification()
    rebuilt = evidence.VerificationEvidence.model_validate_json(retained.model_dump_json())

    assert retained.verification_digest() == rebuilt.verification_digest()
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", retained.verification_digest())
    with pytest.raises(ValidationError):
        verification(fixture_id=None)
    with pytest.raises(ValidationError):
        verification(fixture_sha256=None)


@pytest.mark.parametrize("field", ("summary", "reason", "stdout", "stderr", "environment", "host_path"))
def test_verification_schema_has_no_raw_or_free_text_capture_fields(field: str) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        verification(**{field: "Swordfish from /home/alice"})


def test_verification_provenance_rejects_duplicate_and_conflicting_results() -> None:
    original = verification("a-smoke")
    alias = verification("z-smoke", verified_at=date(2026, 7, 16))

    with pytest.raises(ValidationError, match="duplicate verification capture"):
        evidence_record(verifications=(original, alias))

    conflicting = alias.model_copy(update={"result_sha256": SHA_C})
    with pytest.raises(ValidationError, match="conflicting verification capture"):
        evidence_record(verifications=(original, conflicting))


@pytest.mark.parametrize(
    "updates",
    ({"tool_id": "bcftools"}, {"tool_version": "2.0"}),
)
def test_evidence_record_rejects_verification_for_another_tool(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="verification tool"):
        evidence_record(verifications=(verification(**updates),))


def test_evidence_digest_is_canonical_and_sensitive_to_proof_and_author_provenance() -> None:
    original = evidence_record()
    rebuilt = evidence.EvidenceRecord.model_validate_json(original.model_dump_json())
    changed_proof_source = source(
        evidence.SourceKind.OFFICIAL_MANUAL,
        documentation_proof=proof(proof_content_sha256=SHA_C),
    )
    changed_proof = evidence_record(sources=(changed_proof_source,))
    changed_statement = evidence_record(
        claims=(
            claim(
                statement=authored(
                    "Default index naming is documented.",
                    "/claims/output-collector/statement",
                )
            ),
        )
    )
    changed_provenance = evidence_record(
        claims=(
            claim(
                statement=authored(
                    "Default index naming is derived from the input file name.",
                    "/claims/output-collector/statement",
                    catalog_content_sha256=SHA_D,
                )
            ),
        )
    )

    assert original == rebuilt
    assert (
        len(
            {
                original.evidence_digest(),
                changed_proof.evidence_digest(),
                changed_statement.evidence_digest(),
                changed_provenance.evidence_digest(),
            }
        )
        == 4
    )
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", original.evidence_digest())


def test_evidence_schema_version_is_required_and_legacy_fields_are_rejected() -> None:
    dumped = evidence_record().model_dump(mode="python")
    dumped.pop("schema_version")
    with pytest.raises(ValidationError):
        evidence.EvidenceRecord(**dumped)
    with pytest.raises(ValidationError, match="literal_error"):
        evidence_record(schema_version=1)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        source(evidence.SourceKind.OFFICIAL_MANUAL, version_locator="1.23.1 reference")
    with pytest.raises(ValidationError):
        claim(statement="legacy free text", locator="OUTPUT FILES")


def test_evidence_json_contains_only_schema_v2_declarative_state() -> None:
    record = evidence_record()
    dumped = json.loads(record.model_dump_json())

    assert tuple(dumped) == ("schema_version", "tool_id", "tool_version", "sources", "claims", "verifications")
    serialized = record.model_dump_json()
    for forbidden in ("summary", "reason", "stdout", "stderr", "host_path", "version_locator"):
        assert f'"{forbidden}"' not in serialized


@pytest.mark.parametrize(
    "model",
    (
        "RetainedTextProvenance",
        "RetainedText",
        "ByteRangeLocator",
        "JsonPointerLocator",
        "SymbolLocator",
        "DocumentationVersionProof",
        "EvidenceSource",
        "EvidenceClaim",
        "VerificationEvidence",
        "EvidenceRecord",
    ),
)
def test_evidence_models_share_strict_frozen_validated_copy_contract(model: str) -> None:
    model_type = getattr(evidence, model)
    assert model_type.model_config["extra"] == "forbid"
    assert model_type.model_config["frozen"] is True
    assert model_type.model_config["strict"] is True
    assert model_type.model_config["validate_default"] is True
    assert model_type.model_config["revalidate_instances"] == "always"


def test_evidence_construct_and_copy_revalidate_nested_forgery() -> None:
    valid = source(evidence.SourceKind.OFFICIAL_MANUAL)
    invalid = evidence.EvidenceSource.model_construct(
        **{
            **valid.model_dump(mode="python"),
            "url": "http://docs.example.org/manual.html",
        }
    )
    forged = evidence.EvidenceRecord.model_construct(
        **{
            **evidence_record().model_dump(mode="python"),
            "sources": (invalid,),
        }
    )

    with pytest.raises(ValidationError):
        evidence.EvidenceRecord.model_validate(forged)
    with pytest.raises(ValidationError):
        forged.model_copy()


def test_gate_assessment_requires_verification_for_pass_and_failure() -> None:
    assert assessment(maturity.Gate.INVENTORIED).verification_digests == (SHA_A,)
    assert assessment(maturity.Gate.INVENTORIED, maturity.GateResult.FAILED).verification_digests == (SHA_A,)

    with pytest.raises(ValidationError, match="verification"):
        assessment(maturity.Gate.INVENTORIED, verification_digests=())
    with pytest.raises(ValidationError, match="verification"):
        assessment(maturity.Gate.INVENTORIED, maturity.GateResult.FAILED, verification_digests=())


def test_gate_assessment_failure_code_is_required_for_failure_and_forbidden_for_pass() -> None:
    failed = assessment(maturity.Gate.TOOL_SMOKE_VERIFIED, maturity.GateResult.FAILED)
    assert failed.failure_code is evidence.FailureCode.TOOL_SMOKE_FAILED

    with pytest.raises(ValidationError, match="failure code"):
        assessment(maturity.Gate.INVENTORIED, failure_code=evidence.FailureCode.INVENTORY_MISSING)
    with pytest.raises(ValidationError, match="failure code"):
        assessment(maturity.Gate.INVENTORIED, maturity.GateResult.FAILED, failure_code=None)
    with pytest.raises(ValidationError, match="failure code"):
        assessment(
            maturity.Gate.TOOL_SMOKE_VERIFIED,
            maturity.GateResult.FAILED,
            failure_code=evidence.FailureCode.CLOUD_RUN_FAILED,
        )


def test_gate_ui_text_is_computed_from_codes_and_not_serialized() -> None:
    passed = assessment(maturity.Gate.CONTRACT_VERIFIED)
    failed = assessment(maturity.Gate.TOOL_SMOKE_VERIFIED, maturity.GateResult.FAILED)

    assert passed.ui_summary == "Contract verification passed"
    assert passed.ui_reason is None
    assert failed.ui_summary == "Tool smoke verification failed"
    assert failed.ui_reason == "Pinned tool smoke verification failed"
    for dumped in (passed.model_dump(), failed.model_dump()):
        assert not {"summary", "reason", "ui_summary", "ui_reason"} & dumped.keys()
    with pytest.raises(ValidationError, match="extra_forbidden"):
        assessment(maturity.Gate.INVENTORIED, summary="legacy")
    with pytest.raises(ValidationError, match="extra_forbidden"):
        assessment(maturity.Gate.INVENTORIED, maturity.GateResult.FAILED, reason="legacy")


def test_each_gate_declares_the_required_verification_kind_for_node_spec_binding() -> None:
    assert tuple(assessment(gate).verification_kind for gate in maturity.Gate) == tuple(evidence.VerificationKind)


def test_assessment_verification_is_unique_ordered_and_verifier_identity_is_exact() -> None:
    retained = assessment(maturity.Gate.INVENTORIED, verification_digests=(SHA_A, SHA_B))
    assert retained.verification_digests == (SHA_A, SHA_B)

    for updates in (
        {"verification_digests": (SHA_B, SHA_A)},
        {"verification_digests": (SHA_A, SHA_A)},
        {"verifier_id": "Catalog Verifier"},
        {"verifier_version": "latest"},
        {"verified_at": "2026-07-15"},
    ):
        with pytest.raises(ValidationError):
            retained.model_copy(update=updates)


def test_empty_assessments_are_uninventoried_and_quarantined() -> None:
    record = maturity_record()

    assert record.passed == ()
    assert record.blocking_gate is None
    assert record.next_gate is maturity.Gate.INVENTORIED
    assert record.released is False
    assert record.quarantined is True
    assert record.release_block_reason == "Inventory verification has not passed"


@pytest.mark.parametrize(
    "access_classes",
    (
        (maturity.AccessClass.PUBLIC,),
        (
            maturity.AccessClass.PUBLIC,
            maturity.AccessClass.LARGE_REFERENCE,
            maturity.AccessClass.GPU_REQUIRED,
        ),
        (maturity.AccessClass.PUBLIC_RATE_LIMITED,),
        (
            maturity.AccessClass.PUBLIC_RATE_LIMITED,
            maturity.AccessClass.SECRET_REQUIRED,
            maturity.AccessClass.GPU_REQUIRED,
        ),
        (maturity.AccessClass.SECRET_REQUIRED, maturity.AccessClass.BYOL),
        (
            maturity.AccessClass.SECRET_REQUIRED,
            maturity.AccessClass.LARGE_REFERENCE,
            maturity.AccessClass.GPU_REQUIRED,
            maturity.AccessClass.BYOL,
            maturity.AccessClass.SERVICE_LICENSE,
        ),
    ),
)
def test_access_classes_accept_canonical_overlapping_dimensions(
    access_classes: tuple[maturity.AccessClass, ...],
) -> None:
    assert maturity_record(access_classes=access_classes).access_classes == access_classes


@pytest.mark.parametrize(
    "access_classes",
    (
        (),
        (maturity.AccessClass.GPU_REQUIRED,),
        (maturity.AccessClass.LARGE_REFERENCE,),
        (maturity.AccessClass.PUBLIC, maturity.AccessClass.PUBLIC),
        (maturity.AccessClass.GPU_REQUIRED, maturity.AccessClass.LARGE_REFERENCE),
        (maturity.AccessClass.PUBLIC, maturity.AccessClass.PUBLIC_RATE_LIMITED),
        (maturity.AccessClass.PUBLIC, maturity.AccessClass.SECRET_REQUIRED),
        (maturity.AccessClass.PUBLIC, maturity.AccessClass.BYOL),
        (maturity.AccessClass.PUBLIC, maturity.AccessClass.SERVICE_LICENSE),
    ),
)
def test_access_classes_reject_noncanonical_or_incoherent_combinations(
    access_classes: tuple[maturity.AccessClass, ...],
) -> None:
    with pytest.raises(ValidationError):
        maturity_record(access_classes=access_classes)


@pytest.mark.parametrize(
    ("access_classes", "permits", "permits_required", "requires"),
    (
        ((maturity.AccessClass.PUBLIC,), False, False, False),
        ((maturity.AccessClass.PUBLIC_RATE_LIMITED,), True, False, False),
        ((maturity.AccessClass.SECRET_REQUIRED,), True, True, True),
        ((maturity.AccessClass.BYOL,), True, True, False),
        ((maturity.AccessClass.SERVICE_LICENSE,), True, True, False),
        (
            (maturity.AccessClass.SECRET_REQUIRED, maturity.AccessClass.BYOL),
            True,
            True,
            True,
        ),
    ),
)
def test_access_classes_expose_secret_policy_for_node_spec_validation(
    access_classes: tuple[maturity.AccessClass, ...],
    permits: bool,
    permits_required: bool,
    requires: bool,
) -> None:
    record = maturity_record(access_classes=access_classes)

    assert record.permits_secrets is permits
    assert record.permits_required_secrets is permits_required
    assert record.requires_secret is requires


@pytest.mark.parametrize("length", range(9))
def test_each_passing_prefix_derives_progress_and_release(length: int) -> None:
    gates = tuple(maturity.Gate)
    record = maturity_record(assessments=passed_prefix(length))

    assert record.passed == gates[:length]
    assert record.next_gate is (gates[length] if length < len(gates) else None)
    assert record.released is (length == len(gates))
    assert record.quarantined is (length != len(gates))


@pytest.mark.parametrize("failed_gate", tuple(maturity.Gate))
def test_each_failed_gate_stops_progress_and_uses_generated_reason(failed_gate: maturity.Gate) -> None:
    gates = tuple(maturity.Gate)
    index = gates.index(failed_gate)
    failed = assessment(failed_gate, maturity.GateResult.FAILED)
    record = maturity_record(assessments=(*passed_prefix(index), failed))

    assert record.passed == gates[:index]
    assert record.blocking_gate is failed_gate
    assert record.next_gate is failed_gate
    assert record.released is False
    assert record.release_block_reason == failed.ui_reason


@pytest.mark.parametrize(
    "gate_specs",
    (
        ((maturity.Gate.EVIDENCE_VERIFIED, maturity.GateResult.PASSED),),
        (
            (maturity.Gate.INVENTORIED, maturity.GateResult.PASSED),
            (maturity.Gate.CONTRACT_VERIFIED, maturity.GateResult.PASSED),
        ),
        (
            (maturity.Gate.INVENTORIED, maturity.GateResult.PASSED),
            (maturity.Gate.INVENTORIED, maturity.GateResult.PASSED),
        ),
        (
            (maturity.Gate.INVENTORIED, maturity.GateResult.FAILED),
            (maturity.Gate.EVIDENCE_VERIFIED, maturity.GateResult.PASSED),
        ),
    ),
)
def test_assessments_are_contiguous_and_stop_on_failure(
    gate_specs: tuple[tuple[maturity.Gate, maturity.GateResult], ...],
) -> None:
    assessments = tuple(assessment(gate, result) for gate, result in gate_specs)
    with pytest.raises(ValidationError):
        maturity_record(assessments=assessments)


@pytest.mark.parametrize(
    "access_classes",
    (
        (maturity.AccessClass.PUBLIC,),
        (maturity.AccessClass.PUBLIC, maturity.AccessClass.GPU_REQUIRED),
        (maturity.AccessClass.PUBLIC, maturity.AccessClass.LARGE_REFERENCE),
        (maturity.AccessClass.PUBLIC_RATE_LIMITED,),
        (maturity.AccessClass.SECRET_REQUIRED,),
        (maturity.AccessClass.BYOL,),
        (maturity.AccessClass.SERVICE_LICENSE,),
        (maturity.AccessClass.SECRET_REQUIRED, maturity.AccessClass.BYOL),
    ),
)
def test_full_technical_gates_release_only_nonmanual_access(
    access_classes: tuple[maturity.AccessClass, ...],
) -> None:
    record = maturity_record(access_classes=access_classes, assessments=passed_prefix(len(maturity.Gate)))
    manual = bool({maturity.AccessClass.BYOL, maturity.AccessClass.SERVICE_LICENSE} & set(access_classes))

    assert record.released is not manual
    assert record.quarantined is manual
    assert record.manual_approval_required is manual
    if manual:
        manual_names = ", ".join(
            item.value
            for item in access_classes
            if item in (maturity.AccessClass.BYOL, maturity.AccessClass.SERVICE_LICENSE)
        )
        assert record.release_block_reason == f"{manual_names} requires manual approval"
    else:
        assert record.release_block_reason is None


def test_maturity_schema_version_is_required_and_legacy_state_is_rejected() -> None:
    with pytest.raises(ValidationError):
        maturity.MaturityRecord(access_classes=(maturity.AccessClass.PUBLIC,))
    with pytest.raises(ValidationError, match="literal_error"):
        maturity_record(schema_version=1)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        maturity_record(access=maturity.AccessClass.PUBLIC)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        assessment(maturity.Gate.INVENTORIED, evidence_digests=(SHA_A,))
    for field in ("released", "quarantined", "passed", "next_gate", "blocking_gate"):
        with pytest.raises(ValidationError, match="extra_forbidden"):
            maturity_record(**{field: True})


def test_maturity_digest_roundtrip_is_stable_and_json_is_authoritative_only() -> None:
    original = maturity_record(assessments=passed_prefix(2))
    rebuilt = maturity.MaturityRecord.model_validate_json(original.model_dump_json())
    changed = maturity_record(
        assessments=(
            assessment(maturity.Gate.INVENTORIED, verification_digests=(SHA_B,)),
            assessment(maturity.Gate.EVIDENCE_VERIFIED),
        )
    )
    dumped = json.loads(original.model_dump_json())

    assert original == rebuilt
    assert hash(original) == hash(rebuilt)
    assert original.maturity_digest() == rebuilt.maturity_digest()
    assert original.maturity_digest() != changed.maturity_digest()
    assert tuple(dumped) == ("schema_version", "access_classes", "assessments")
    assert not {"released", "summary", "reason", "ui_summary", "ui_reason"} & dumped.keys()


@pytest.mark.parametrize("model", (maturity.GateAssessment, maturity.MaturityRecord))
def test_maturity_models_are_strict_frozen_and_revalidate_copies(model: type) -> None:
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["frozen"] is True
    assert model.model_config["strict"] is True
    assert model.model_config["validate_default"] is True
    assert model.model_config["revalidate_instances"] == "always"

    record = maturity_record()
    with pytest.raises(ValidationError, match="frozen_instance"):
        record.access_classes = (maturity.AccessClass.GPU_REQUIRED,)
    with pytest.raises(ValidationError):
        record.model_copy(update={"assessments": (assessment(maturity.Gate.WORKFLOW_VERIFIED),)})


def test_contract_modules_are_declarative_and_contain_no_legacy_semantic_text_parser() -> None:
    forbidden_import_roots = {
        "aiohttp",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "urllib.request",
    }
    forbidden_legacy_names = (
        "_validate_retained_secrets",
        "_CAPTURE_HOST_PATH_RES",
        "_DOCUMENT_VERSION_SCAN_RE",
        "_tool_adjacent_document_versions",
        "_validate_official_documentation_binding",
    )

    for module in (evidence, maturity):
        path = Path(module.__file__)
        source_text = path.read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.add(node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"now", "today", "utcnow"}

        assert not forbidden_import_roots & imports
        assert not any(name in source_text for name in forbidden_legacy_names)
        for forbidden_text in (
            "bionodulo.nodes.legacy",
            "legacy.executor",
            "os.system",
            "shell=True",
            "compile_catalog",
            "build_catalog_ledger",
        ):
            assert forbidden_text not in source_text
