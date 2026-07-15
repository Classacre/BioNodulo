from __future__ import annotations

import ast
import json
import re
from datetime import date
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


def source(kind: evidence.SourceKind, **updates: object) -> evidence.EvidenceSource:
    values: dict[str, object] = {
        "source_id": f"samtools-{kind.value.replace('_', '-')}",
        "kind": kind,
        "tool_version": "1.23.1",
        "retrieved_at": CAPTURE_DATE,
        "content_sha256": SHA_A,
        "title": "Samtools 1.23.1 reference",
        "description": "Authoritative behavior reference for the pinned tool release.",
    }
    if kind in (evidence.SourceKind.OFFICIAL_MANUAL, evidence.SourceKind.OFFICIAL_API_SCHEMA):
        values.update(
            url="https://docs.example.org/samtools/1.23.1/reference.html",
            version_locator="1.23.1 reference",
        )
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
        "locator": "OUTPUT FILES",
        "statement": "Default index naming is derived from the input file name.",
        "source_content_sha256": SHA_A,
        "excerpt_sha256": SHA_B,
        "contract_value_sha256": SHA_C,
    }
    values.update(updates)
    return evidence.EvidenceClaim(**values)


def verification(
    evidence_id: str = "samtools-smoke-linux-amd64",
    **updates: object,
) -> evidence.VerificationEvidence:
    values: dict[str, object] = {
        "evidence_id": evidence_id,
        "kind": "tool-smoke",
        "test_id": "samtools-index-tiny-bam-v1",
        "result_sha256": SHA_D,
        "fixture_id": "tiny-bam-v1",
        "fixture_sha256": SHA_E,
        "environment_sha256": SHA_B,
        "catalog_sha256": None,
        "platform_sha256": SHA_C,
        "release_sha256": None,
        "verified_at": CAPTURE_DATE,
        "summary": "Pinned samtools completed the retained tiny BAM fixture.",
    }
    values.update(updates)
    return evidence.VerificationEvidence(**values)


def evidence_record(**updates: object) -> evidence.EvidenceRecord:
    values: dict[str, object] = {
        "tool_id": "samtools",
        "tool_version": "1.23.1",
        "sources": (source(evidence.SourceKind.OFFICIAL_MANUAL),),
        "claims": (claim(),),
        "verifications": (verification(),),
    }
    values.update(updates)
    return evidence.EvidenceRecord(**values)


def assessment(
    gate: maturity.Gate,
    result: maturity.GateResult = maturity.GateResult.PASSED,
    **updates: object,
) -> maturity.GateAssessment:
    values: dict[str, object] = {
        "gate": gate,
        "result": result,
        "evidence_digests": (SHA_A,) if result is maturity.GateResult.PASSED else (),
        "verified_at": CAPTURE_DATE,
        "verifier_id": "catalog-verifier",
        "verifier_version": "1.0.0",
        "summary": f"Retained assessment for {gate.value}.",
        "reason": None if result is maturity.GateResult.PASSED else f"{gate.value} fixture failed",
    }
    values.update(updates)
    return maturity.GateAssessment(**values)


def passed_prefix(length: int) -> tuple[maturity.GateAssessment, ...]:
    return tuple(assessment(gate) for gate in tuple(maturity.Gate)[:length])


def test_source_kind_wire_values_are_exact_and_authoritative_only() -> None:
    assert tuple(kind.value for kind in evidence.SourceKind) == (
        "official_manual",
        "official_api_schema",
        "upstream_source",
        "installed_help",
        "package_recipe",
    )
    assert not {"bionodulo", "galaxy", "blog"} & {kind.value for kind in evidence.SourceKind}


def test_access_and_gate_wire_values_and_order_are_exact() -> None:
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


@pytest.mark.parametrize("kind", tuple(evidence.SourceKind))
def test_each_source_kind_has_a_valid_minimal_immutable_json_roundtrip(
    kind: evidence.SourceKind,
) -> None:
    captured = source(kind)
    rebuilt = evidence.EvidenceSource.model_validate_json(captured.model_dump_json())

    assert rebuilt == captured
    assert hash(rebuilt) == hash(captured)
    assert rebuilt.kind is kind


@pytest.mark.parametrize(
    ("kind", "field"),
    (
        (evidence.SourceKind.OFFICIAL_MANUAL, "url"),
        (evidence.SourceKind.OFFICIAL_MANUAL, "version_locator"),
        (evidence.SourceKind.OFFICIAL_API_SCHEMA, "url"),
        (evidence.SourceKind.OFFICIAL_API_SCHEMA, "version_locator"),
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
    captured = source(kind)

    with pytest.raises(ValidationError):
        captured.model_copy(update={field: None})


@pytest.mark.parametrize(
    ("kind", "updates"),
    (
        (evidence.SourceKind.OFFICIAL_MANUAL, {"commit": COMMIT_A}),
        (evidence.SourceKind.OFFICIAL_API_SCHEMA, {"recipe_revision": COMMIT_A}),
        (evidence.SourceKind.PACKAGE_RECIPE, {"version_locator": "1.23.1 docs"}),
        (evidence.SourceKind.PACKAGE_RECIPE, {"source_path": "recipes/samtools/meta.yaml"}),
        (evidence.SourceKind.UPSTREAM_SOURCE, {"version_locator": "1.23.1 source"}),
        (evidence.SourceKind.UPSTREAM_SOURCE, {"recipe_revision": COMMIT_A}),
        (evidence.SourceKind.UPSTREAM_SOURCE, {"environment_digest": SHA_B}),
        (evidence.SourceKind.INSTALLED_HELP, {"url": "https://docs.example.org/tool/help"}),
        (evidence.SourceKind.INSTALLED_HELP, {"commit": COMMIT_A}),
        (evidence.SourceKind.INSTALLED_HELP, {"symbol_locator": "main"}),
    ),
)
def test_source_kinds_reject_irrelevant_cross_kind_fields(
    kind: evidence.SourceKind,
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        source(kind).model_copy(update=updates)


@pytest.mark.parametrize(
    "url",
    (
        "http://docs.example.org/tool/manual.html",
        "HTTPS://docs.example.org/tool/manual.html",
        "https://user:password@docs.example.org/tool/manual.html",
        "https://docs.example.org/tool/manual.html?token=secret",
        "https://docs.example.org/tool/manual.html?",
        "https://docs.example.org/tool/manual.html#section",
        "https://docs.example.org/tool/manual.html#",
        "https://DOCS.example.org/tool/manual.html",
        "https://docs.example.org:443/tool/manual.html",
        "https://docs.example.org:08443/tool/manual.html",
        "https://docs.example.org/tool/%6danual.html",
        "https://docs.example.org/tool/manual path.html",
        "https://docs.example.org/tool/manual.html\n",
        "https://docs.example.org",
        "https://docs.example.org/",
        "https://docs.example.org//tool/manual.html",
        "https://docs.example.org/tool/../manual.html",
        "https://docs.example.org/tool\\manual.html",
    ),
)
def test_document_and_recipe_urls_require_one_canonical_credential_free_https_spelling(
    url: str,
) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(update={"url": url})


def test_canonical_nondefault_https_port_is_retained() -> None:
    captured = source(evidence.SourceKind.OFFICIAL_API_SCHEMA).model_copy(
        update={"url": "https://api.example.org:8443/schema/1.23.1.json"}
    )

    assert captured.url == "https://api.example.org:8443/schema/1.23.1.json"


@pytest.mark.parametrize("version", ("", "latest", "main", "1.*", ">=1.2", " 1.2", "1.2 ", "1.2\n"))
def test_sources_and_records_require_exact_tool_versions(version: str) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(update={"tool_version": version})
    with pytest.raises(ValidationError):
        evidence_record().model_copy(update={"tool_version": version})


@pytest.mark.parametrize("revision", (COMMIT_A, COMMIT_B, "1.2.3", "samtools-1.23.1-0"))
def test_package_recipe_revision_is_an_exact_bounded_identity(revision: str) -> None:
    updates = {
        "recipe_revision": revision,
        "url": f"https://github.com/bioconda/bioconda-recipes/blob/{revision}/recipes/samtools/meta.yaml",
    }
    recipe = source(evidence.SourceKind.PACKAGE_RECIPE).model_copy(update=updates)

    assert recipe.recipe_revision == revision


@pytest.mark.parametrize(
    "updates",
    (
        {"url": "https://github.com/bioconda/bioconda-recipes/blob/main/recipes/samtools/meta.yaml"},
        {"url": (f"https://github.com/bioconda/bioconda-recipes/blob/{COMMIT_A}/recipes/bcftools/meta.yaml")},
        {"recipe_path": "recipes/bcftools/meta.yaml"},
        {
            "recipe_revision": "1.2.3",
            "url": "https://github.com/bioconda/bioconda-recipes/blob/main/recipes/samtools/meta.yaml",
        },
    ),
)
def test_package_recipe_revision_and_path_must_be_bound_in_its_url(
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="revision"):
        source(evidence.SourceKind.PACKAGE_RECIPE).model_copy(update=updates)


@pytest.mark.parametrize(
    "revision",
    ("", "latest", "main", "master", "1.*", "revision with spaces", "v1.2?token=secret", "v1.2\n"),
)
def test_package_recipe_rejects_moving_or_unsafe_revisions(revision: str) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.PACKAGE_RECIPE).model_copy(update={"recipe_revision": revision})


@pytest.mark.parametrize("commit", (COMMIT_A, COMMIT_B))
def test_upstream_source_accepts_exact_lowercase_git_object_ids(commit: str) -> None:
    captured = source(evidence.SourceKind.UPSTREAM_SOURCE).model_copy(
        update={
            "commit": commit,
            "url": f"https://github.com/samtools/samtools/blob/{commit}/src/samtools.c",
            "source_path": "src/samtools.c",
        }
    )

    assert captured.commit == commit


@pytest.mark.parametrize(
    "commit",
    ("1" * 39, "1" * 41, "A" * 40, "g" * 40, "latest", "main", "1" * 40 + "\n"),
)
def test_upstream_source_rejects_noncanonical_git_object_ids(commit: str) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.UPSTREAM_SOURCE).model_copy(update={"commit": commit})


@pytest.mark.parametrize(
    "source_path",
    ("bam_sort.c", "src/samtools.c", "include/htslib/sam.h", "src/_internal.py", ".github/schema.json"),
)
def test_upstream_source_path_is_repository_relative_and_url_bound(source_path: str) -> None:
    captured = source(evidence.SourceKind.UPSTREAM_SOURCE).model_copy(
        update={
            "source_path": source_path,
            "url": f"https://github.com/samtools/samtools/blob/{COMMIT_A}/{source_path}",
        }
    )

    assert captured.source_path == source_path


@pytest.mark.parametrize(
    "source_path",
    (
        "",
        "/src/samtools.c",
        "../src/samtools.c",
        "src/../samtools.c",
        "src/./samtools.c",
        "src//samtools.c",
        "src\\samtools.c",
        "src/samtools.c/",
        "src/samtools.c\n",
    ),
)
def test_upstream_source_rejects_noncanonical_paths(source_path: str) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.UPSTREAM_SOURCE).model_copy(update={"source_path": source_path})


@pytest.mark.parametrize(
    ("url", "source_path"),
    (
        ("https://github.com/samtools/samtools/blob/main/bam_sort.c", "bam_sort.c"),
        (f"https://github.com/samtools/samtools/blob/{COMMIT_A}/src/other.c", "bam_sort.c"),
        (f"https://github.com/samtools/samtools/tree/{COMMIT_A}", "bam_sort.c"),
        (f"https://github.com/samtools/samtools/blob/{COMMIT_A}/bam_sort.c", "src/bam_sort.c"),
    ),
)
def test_upstream_url_must_bind_the_commit_and_exact_source_path(url: str, source_path: str) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.UPSTREAM_SOURCE).model_copy(update={"url": url, "source_path": source_path})


@pytest.mark.parametrize("symbol", (None, "main", "bam_sort_core_ext", "Samtools.Sort::run"))
def test_upstream_symbol_locator_is_optional_but_exact(symbol: str | None) -> None:
    captured = source(evidence.SourceKind.UPSTREAM_SOURCE).model_copy(update={"symbol_locator": symbol})

    assert captured.symbol_locator == symbol


@pytest.mark.parametrize("symbol", ("", " main", "main ", "main()", "src/main", "main\n"))
def test_upstream_symbol_locator_rejects_ambiguous_forms(symbol: str) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.UPSTREAM_SOURCE).model_copy(update={"symbol_locator": symbol})


@pytest.mark.parametrize("argv", (("--help",), ("help",), ("view", "--help")))
def test_installed_help_retains_literal_immutable_argv(argv: tuple[str, ...]) -> None:
    captured = source(evidence.SourceKind.INSTALLED_HELP).model_copy(update={"argv": argv})

    assert captured.argv == argv
    assert type(captured.argv) is tuple


@pytest.mark.parametrize(
    "argv",
    (
        (),
        ["--help"],
        "--help",
        ("",),
        ("samtools --help",),
        ("--help;id",),
        ("$(id)",),
        ("`id`",),
        ("--token=secret",),
        ("view", "input.bam"),
        ("input.bam", "--help"),
        ("--help", "input.bam"),
        ("--help", "view"),
        ("view", "input.bam", "--help"),
        ("view", "--help", "input.bam"),
        ("--help", "--format=json"),
        ("/usr/bin/samtools", "--help"),
        ("--config=/tmp/config",),
        ("--help\n",),
    ),
)
def test_installed_help_rejects_shell_strings_paths_secrets_and_coercions(argv: object) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.INSTALLED_HELP).model_copy(update={"argv": argv})


def test_installed_help_output_digest_must_equal_common_captured_content() -> None:
    with pytest.raises(ValidationError, match="output"):
        source(evidence.SourceKind.INSTALLED_HELP).model_copy(update={"output_sha256": SHA_C})


@pytest.mark.parametrize("pointer", ("/outputs/0/collector", "/a~1b/~0schema", "/metadata/%2E/value"))
def test_claim_accepts_canonical_json_pointers(pointer: str) -> None:
    asserted = claim(contract_pointer=pointer)

    assert asserted.contract_pointer == pointer


@pytest.mark.parametrize(
    "pointer",
    (
        "",
        "outputs.index.collector",
        "/",
        "//",
        "/outputs/",
        "/outputs//collector",
        "/.",
        "/..",
        "/outputs/../collector",
        "/outputs/./collector",
        "/outputs/~",
        "/outputs/~2",
        "/outputs/raw~tilde",
        "/outputs/ collector",
        "/outputs/collector ",
        "/outputs/collector\n",
        "/outputs/collector\x7f",
        "/" + "/".join("segment" for _ in range(65)),
        "/" + "a" * 2048,
    ),
)
def test_claim_rejects_dotted_empty_traversing_overdeep_or_noncanonical_pointers(
    pointer: str,
) -> None:
    with pytest.raises(ValidationError):
        claim(contract_pointer=pointer)


def test_claim_locator_is_bounded_single_line_and_statement_is_nonempty() -> None:
    redacted = claim(statement="Use --token=<TOKEN> only when the official service requires authentication.")

    assert redacted.statement.startswith("Use --token=<TOKEN>")
    with pytest.raises(ValidationError):
        claim(locator="")
    with pytest.raises(ValidationError):
        claim(locator="OUTPUT\nFILES")
    with pytest.raises(ValidationError):
        claim(locator="x" * 513)
    with pytest.raises(ValidationError):
        claim(statement="")
    with pytest.raises(ValidationError):
        claim(statement=" statement with outer whitespace ")
    with pytest.raises(ValidationError, match="secret"):
        claim(statement="Use --token=retained-secret-value for authentication.")


def test_evidence_record_binds_claims_to_known_source_content() -> None:
    record = evidence_record()

    assert record.claims[0].source_id == record.sources[0].source_id
    assert record.claims[0].source_content_sha256 == record.sources[0].content_sha256

    with pytest.raises(ValidationError, match="missing source"):
        evidence_record(claims=(claim(source_id="missing-source"),))
    with pytest.raises(ValidationError, match="content"):
        evidence_record(claims=(claim(source_content_sha256=SHA_D),))


@pytest.mark.parametrize("field", ("sources", "claims"))
def test_evidence_verified_record_requires_sources_and_claims(field: str) -> None:
    with pytest.raises(ValidationError):
        evidence_record(**{field: ()})


def test_evidence_sources_claims_and_verifications_are_unique_and_canonically_ordered() -> None:
    manual = source(evidence.SourceKind.OFFICIAL_MANUAL)
    upstream = source(evidence.SourceKind.UPSTREAM_SOURCE)
    manual_claim = claim()
    upstream_claim = claim(
        claim_id="upstream-output-collector",
        source_id=upstream.source_id,
        excerpt_sha256=SHA_D,
    )
    first_verification = verification("a-smoke")
    second_verification = verification("z-workflow", kind="workflow", test_id="workflow-v1")

    valid = evidence_record(
        sources=(manual, upstream),
        claims=(manual_claim, upstream_claim),
        verifications=(first_verification, second_verification),
    )
    assert valid.sources == (manual, upstream)

    for updates in (
        {"sources": (upstream, manual)},
        {"sources": (manual, manual)},
        {"claims": (upstream_claim, manual_claim), "sources": (manual, upstream)},
        {"claims": (manual_claim, manual_claim)},
        {"verifications": (second_verification, first_verification)},
        {"verifications": (first_verification, first_verification)},
    ):
        with pytest.raises(ValidationError):
            evidence_record(**updates)


def test_same_pointer_may_have_independent_claims_only_from_distinct_sources() -> None:
    manual = source(evidence.SourceKind.OFFICIAL_MANUAL)
    upstream = source(evidence.SourceKind.UPSTREAM_SOURCE)
    independent = claim(
        claim_id="upstream-output-collector",
        source_id=upstream.source_id,
        excerpt_sha256=SHA_D,
    )
    accepted = evidence_record(sources=(manual, upstream), claims=(claim(), independent))

    assert len(accepted.claims) == 2

    same_source = claim(
        claim_id="second-manual-claim",
        locator="OPTIONS",
        excerpt_sha256=SHA_D,
    )
    with pytest.raises(ValidationError, match="pointer"):
        evidence_record(claims=(claim(), same_source))


def test_duplicate_exact_claim_bindings_are_rejected_even_with_new_claim_ids() -> None:
    duplicate = claim(claim_id="same-binding-new-id")

    with pytest.raises(ValidationError, match="duplicate"):
        evidence_record(claims=(claim(), duplicate))


def test_verification_fixture_identity_is_all_or_nothing_and_digest_stable() -> None:
    retained = verification()
    rebuilt = evidence.VerificationEvidence.model_validate_json(retained.model_dump_json())

    assert retained.verification_digest() == rebuilt.verification_digest()
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", retained.verification_digest())

    with pytest.raises(ValidationError):
        verification(fixture_id=None)
    with pytest.raises(ValidationError):
        verification(fixture_sha256=None)


def test_evidence_digest_is_canonical_and_sensitive_to_every_claim_binding() -> None:
    original = evidence_record()
    rebuilt = evidence.EvidenceRecord.model_validate_json(original.model_dump_json())
    changed_pointer = evidence_record(claims=(claim(contract_pointer="/outputs/index/path"),))
    changed_value = evidence_record(claims=(claim(contract_value_sha256=SHA_D),))
    changed_excerpt = evidence_record(claims=(claim(excerpt_sha256=SHA_D),))
    changed_source = evidence_record(
        sources=(source(evidence.SourceKind.OFFICIAL_MANUAL, content_sha256=SHA_D),),
        claims=(claim(source_content_sha256=SHA_D),),
    )

    assert original.evidence_digest() == rebuilt.evidence_digest()
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", original.evidence_digest())
    assert (
        len(
            {
                original.evidence_digest(),
                changed_pointer.evidence_digest(),
                changed_value.evidence_digest(),
                changed_excerpt.evidence_digest(),
                changed_source.evidence_digest(),
            }
        )
        == 5
    )


@pytest.mark.parametrize(
    "model",
    (
        evidence.EvidenceSource,
        evidence.EvidenceClaim,
        evidence.VerificationEvidence,
        evidence.EvidenceRecord,
        maturity.GateAssessment,
        maturity.MaturityRecord,
    ),
)
def test_evidence_and_maturity_models_share_strict_frozen_validated_copy_contract(model: type) -> None:
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["frozen"] is True
    assert model.model_config["strict"] is True
    assert model.model_config["validate_default"] is True
    assert model.model_config["revalidate_instances"] == "always"


def test_evidence_models_reject_extras_mutation_and_python_collection_coercions() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        source(evidence.SourceKind.OFFICIAL_MANUAL, released=True)
    with pytest.raises(ValidationError):
        evidence_record(sources=[source(evidence.SourceKind.OFFICIAL_MANUAL)])
    with pytest.raises(ValidationError):
        evidence_record(claims=[claim()])

    record = evidence_record()
    with pytest.raises(ValidationError, match="frozen_instance"):
        record.tool_id = "bcftools"


def test_evidence_copy_and_construct_revalidate_nested_forgery() -> None:
    invalid_source = evidence.EvidenceSource.model_construct(
        **{
            **source(evidence.SourceKind.OFFICIAL_MANUAL).model_dump(mode="python"),
            "url": "http://docs.example.org/tool/manual.html",
        }
    )
    forged = evidence.EvidenceRecord.model_construct(
        **{
            **evidence_record().model_dump(mode="python"),
            "sources": (invalid_source,),
        }
    )

    with pytest.raises(ValidationError):
        evidence.EvidenceRecord.model_validate(forged)
    with pytest.raises(ValidationError):
        forged.model_copy()
    with pytest.raises(ValidationError):
        evidence_record().model_copy(update={"claims": ()})


def test_evidence_json_dump_contains_only_declarative_state() -> None:
    record = evidence_record()
    dumped = json.loads(record.model_dump_json())

    assert tuple(dumped) == ("tool_id", "tool_version", "sources", "claims", "verifications")
    assert "released" not in dumped
    assert "passed" not in dumped
    assert evidence.EvidenceRecord.model_validate_json(record.model_dump_json()) == record


def test_gate_assessment_pass_requires_retained_evidence_and_failure_requires_reason() -> None:
    passed = assessment(maturity.Gate.INVENTORIED)
    failed = assessment(maturity.Gate.INVENTORIED, maturity.GateResult.FAILED)

    assert passed.evidence_digests == (SHA_A,)
    assert failed.reason == "inventoried fixture failed"

    with pytest.raises(ValidationError, match="evidence"):
        assessment(maturity.Gate.INVENTORIED, evidence_digests=())
    with pytest.raises(ValidationError, match="reason"):
        assessment(maturity.Gate.INVENTORIED, maturity.GateResult.FAILED, reason=None)
    with pytest.raises(ValidationError, match="reason"):
        assessment(maturity.Gate.INVENTORIED, maturity.GateResult.FAILED, reason="")
    with pytest.raises(ValidationError, match="reason"):
        assessment(maturity.Gate.INVENTORIED, reason="not applicable to a pass")


def test_failed_gate_may_retain_evidence_and_assessment_evidence_is_unique_ordered() -> None:
    retained = assessment(
        maturity.Gate.TOOL_SMOKE_VERIFIED,
        maturity.GateResult.FAILED,
        evidence_digests=(SHA_A, SHA_B),
    )

    assert retained.evidence_digests == (SHA_A, SHA_B)
    with pytest.raises(ValidationError):
        retained.model_copy(update={"evidence_digests": (SHA_B, SHA_A)})
    with pytest.raises(ValidationError):
        retained.model_copy(update={"evidence_digests": (SHA_A, SHA_A)})


def test_assessment_text_and_verifier_identity_are_exact_and_bounded() -> None:
    for updates in (
        {"summary": ""},
        {"summary": " summary "},
        {"summary": "summary\n"},
        {"verifier_id": "Catalog Verifier"},
        {"verifier_version": "latest"},
        {"verified_at": "2026-07-15"},
    ):
        with pytest.raises(ValidationError):
            assessment(maturity.Gate.INVENTORIED).model_copy(update=updates)


def test_empty_assessments_are_uninventoried_and_quarantined() -> None:
    record = maturity.MaturityRecord(access=maturity.AccessClass.PUBLIC)

    assert record.passed == ()
    assert record.blocking_gate is None
    assert record.next_gate is maturity.Gate.INVENTORIED
    assert record.released is False
    assert record.quarantined is True
    assert record.manual_approval_required is False
    assert "inventoried" in record.release_block_reason


@pytest.mark.parametrize("length", range(9))
def test_each_passing_prefix_derives_ordered_progress_and_next_gate(length: int) -> None:
    gates = tuple(maturity.Gate)
    record = maturity.MaturityRecord(
        access=maturity.AccessClass.PUBLIC,
        assessments=passed_prefix(length),
    )

    assert record.passed == gates[:length]
    assert record.blocking_gate is None
    assert record.next_gate is (gates[length] if length < len(gates) else None)
    assert record.released is (length == len(gates))
    assert record.quarantined is (length != len(gates))
    if length == len(gates):
        assert record.release_block_reason is None
    else:
        assert gates[length].value in record.release_block_reason


@pytest.mark.parametrize("failed_gate", tuple(maturity.Gate))
def test_each_failed_gate_stops_progress_and_identifies_exact_blocker(
    failed_gate: maturity.Gate,
) -> None:
    gates = tuple(maturity.Gate)
    index = gates.index(failed_gate)
    reason = f"retained failure at {failed_gate.value}"
    assessments = (*passed_prefix(index), assessment(failed_gate, maturity.GateResult.FAILED, reason=reason))
    record = maturity.MaturityRecord(access=maturity.AccessClass.PUBLIC, assessments=assessments)

    assert record.passed == gates[:index]
    assert record.blocking_gate is failed_gate
    assert record.next_gate is failed_gate
    assert record.released is False
    assert record.quarantined is True
    assert record.release_block_reason == reason


@pytest.mark.parametrize(
    "assessments",
    (
        (assessment(maturity.Gate.EVIDENCE_VERIFIED),),
        (
            assessment(maturity.Gate.INVENTORIED),
            assessment(maturity.Gate.CONTRACT_VERIFIED),
        ),
        (
            assessment(maturity.Gate.INVENTORIED),
            assessment(maturity.Gate.INVENTORIED),
        ),
        (
            assessment(maturity.Gate.EVIDENCE_VERIFIED),
            assessment(maturity.Gate.INVENTORIED),
        ),
        (
            assessment(maturity.Gate.INVENTORIED, maturity.GateResult.FAILED),
            assessment(maturity.Gate.EVIDENCE_VERIFIED),
        ),
    ),
)
def test_assessments_must_start_at_inventoried_be_unique_contiguous_and_stop_on_failure(
    assessments: tuple[maturity.GateAssessment, ...],
) -> None:
    with pytest.raises(ValidationError):
        maturity.MaturityRecord(access=maturity.AccessClass.PUBLIC, assessments=assessments)


@pytest.mark.parametrize("access", tuple(maturity.AccessClass))
def test_full_technical_gates_release_only_nonmanual_access_classes(
    access: maturity.AccessClass,
) -> None:
    record = maturity.MaturityRecord(access=access, assessments=passed_prefix(len(maturity.Gate)))
    manual = access in (maturity.AccessClass.BYOL, maturity.AccessClass.SERVICE_LICENSE)

    assert record.released is not manual
    assert record.quarantined is manual
    assert record.manual_approval_required is manual
    assert record.blocking_gate is None
    assert record.next_gate is None
    if manual:
        assert access.value in record.release_block_reason
    else:
        assert record.release_block_reason is None


@pytest.mark.parametrize("access", (maturity.AccessClass.BYOL, maturity.AccessClass.SERVICE_LICENSE))
def test_manual_access_never_auto_releases_even_after_all_technical_gates(
    access: maturity.AccessClass,
) -> None:
    record = maturity.MaturityRecord(access=access, assessments=passed_prefix(8))

    assert record.passed == tuple(maturity.Gate)
    assert record.released is False
    assert record.quarantined is True
    assert record.manual_approval_required is True


@pytest.mark.parametrize("field", ("released", "quarantined", "passed", "next_gate", "blocking_gate"))
def test_callers_cannot_supply_computed_maturity_state(field: str) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        maturity.MaturityRecord(access=maturity.AccessClass.PUBLIC, **{field: True})


def test_maturity_copy_cannot_forge_release_or_skip_gates() -> None:
    record = maturity.MaturityRecord(access=maturity.AccessClass.PUBLIC)

    with pytest.raises(ValidationError):
        record.model_copy(update={"released": True})
    with pytest.raises(ValidationError):
        record.model_copy(update={"quarantined": False})
    with pytest.raises(ValidationError):
        record.model_copy(update={"assessments": (assessment(maturity.Gate.WORKFLOW_VERIFIED),)})


def test_constructed_maturity_is_revalidated_by_validation_and_copy() -> None:
    forged = maturity.MaturityRecord.model_construct(
        access=maturity.AccessClass.PUBLIC,
        assessments=(assessment(maturity.Gate.WORKFLOW_VERIFIED),),
    )

    with pytest.raises(ValidationError):
        maturity.MaturityRecord.model_validate(forged)
    with pytest.raises(ValidationError):
        forged.model_copy()


def test_maturity_digest_roundtrip_is_stable_and_retains_assessment_evidence() -> None:
    original = maturity.MaturityRecord(access=maturity.AccessClass.PUBLIC, assessments=passed_prefix(2))
    rebuilt = maturity.MaturityRecord.model_validate_json(original.model_dump_json())
    changed_evidence = original.model_copy(
        update={
            "assessments": (
                assessment(maturity.Gate.INVENTORIED, evidence_digests=(SHA_B,)),
                assessment(maturity.Gate.EVIDENCE_VERIFIED),
            )
        }
    )
    changed_access = original.model_copy(update={"access": maturity.AccessClass.GPU_REQUIRED})

    assert original == rebuilt
    assert hash(original) == hash(rebuilt)
    assert original.maturity_digest() == rebuilt.maturity_digest()
    assert original.maturity_digest() != changed_evidence.maturity_digest()
    assert original.maturity_digest() != changed_access.maturity_digest()
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", original.maturity_digest())


def test_maturity_json_contains_only_authoritative_access_and_assessments() -> None:
    record = maturity.MaturityRecord(access=maturity.AccessClass.PUBLIC, assessments=passed_prefix(1))
    dumped = json.loads(record.model_dump_json())

    assert tuple(dumped) == ("access", "assessments")
    assert not {"released", "quarantined", "passed", "next_gate", "blocking_gate"} & dumped.keys()
    assert maturity.MaturityRecord.model_validate_json(record.model_dump_json()) == record


def test_contract_modules_are_declarative_and_do_not_fetch_execute_or_read_a_clock() -> None:
    forbidden_import_roots = {
        "aiohttp",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "urllib.request",
    }

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
        for forbidden_text in (
            "bionodulo.nodes.legacy",
            "legacy.executor",
            "os.system",
            "shell=True",
            "compile_catalog",
            "build_catalog_ledger",
        ):
            assert forbidden_text not in source_text
