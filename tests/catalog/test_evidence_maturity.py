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
        "tool_id": "samtools",
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


_RETAINED_TEXT_FIELDS = (
    "source_title",
    "source_description",
    "source_version_locator",
    "claim_locator",
    "claim_statement",
    "verification_summary",
    "assessment_summary",
    "assessment_reason",
)


def retained_text(field: str, value: str) -> str:
    if field == "source_title":
        return source(evidence.SourceKind.OFFICIAL_MANUAL, title=value).title
    if field == "source_description":
        return source(evidence.SourceKind.OFFICIAL_MANUAL, description=value).description
    if field == "source_version_locator":
        locator = f"1.23.1 {value}"
        captured = source(evidence.SourceKind.OFFICIAL_MANUAL, version_locator=locator)
        assert captured.version_locator is not None
        return captured.version_locator.removeprefix("1.23.1 ")
    if field == "claim_locator":
        return claim(locator=value).locator
    if field == "claim_statement":
        return claim(statement=value).statement
    if field == "verification_summary":
        return verification(summary=value).summary
    if field == "assessment_summary":
        return assessment(maturity.Gate.INVENTORIED, summary=value).summary
    if field == "assessment_reason":
        failed = assessment(maturity.Gate.INVENTORIED, maturity.GateResult.FAILED, reason=value)
        assert failed.reason is not None
        return failed.reason
    raise AssertionError(f"unknown retained-text field {field}")


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


@pytest.mark.parametrize("field", _RETAINED_TEXT_FIELDS)
@pytest.mark.parametrize(
    "value",
    (
        "Résumé — 測試 🧬",
        "أداة موثوقة",
        "The access_token parameter is <TOKEN>.",
        "access_token=<TOKEN>",
        'Set client_secret="${TOKEN}".',
        "https://service.invalid/run?password=[REDACTED]&mode=test",
        "Authorization: Bearer REDACTED.",
        "Authorization=Basic ***",
        "Authorization Bearer <TOKEN>",
        "Authorization Basic [REDACTED]",
        "token=<TOKEN>.",
        "auth=[REDACTED].",
        "credential=***.",
        "Run --token <TOKEN>",
        "Run --token ${TOKEN}",
        "Use password [REDACTED]",
        'Authorization: "Bearer <TOKEN>"',
        'Authorization: "Basic [REDACTED]"',
        'Authorization: "Bearer" <TOKEN>',
        "Defaults: output=/tmp/default, stream=/dev/stdout, tool=/usr/bin/tool.",
        "Captured from /home/<USER>/work.",
        "Captured from /Users/<USER>/work.",
        r"Captured from C:\Users\<USER>\work.",
        "Captured from /home/<USER>.",
        r"Captured from C:\Users\<USER>.",
        "Captured from </home/<USER>/work>.",
        "Captured from file://localhost/home/<USER>/work.",
        "See https://docs.example.org/home/user for documented behavior.",
        "Database metadata: foreign_key_id=42.",
        "The monkey habitat and keynote schedule contain no credentials.",
        "The key parameter selects the output map.",
        "Token bucket algorithm is documented.",
        "Password hashing uses Argon2.",
        "Credentials are supplied at runtime.",
        "The token parser accepts quoted values.",
        "Password rotation is documented upstream.",
        "The --token option is required.",
        "Use password hashing for stored credentials.",
        "Configure authentication using OAuth.",
        "See profile://buildhost/home/alice/work for the documented profile URI.",
        "The password is hashed with Argon2.",
        "The token is documented in the HTTP reference.",
        "Credentials are supplied via OAuth2.",
        "Use --no-token to disable authentication.",
    ),
)
def test_retained_text_accepts_printable_unicode_redactions_and_documented_paths(
    field: str,
    value: str,
) -> None:
    assert retained_text(field, value) == value


@pytest.mark.parametrize("field", _RETAINED_TEXT_FIELDS)
@pytest.mark.parametrize(
    "value",
    (
        "access_token=live-value",
        "access-token: live-value",
        'CLIENT_SECRET="live-value"',
        "OPENAI_API_KEY=sk-live-value",
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
        "api-key=live-value",
        "refresh_token=live-value",
        "refresh_key=live-value",
        "auth_token=live-value",
        "auth-key=live-value",
        "auth=live-value",
        "credential=live-value",
        "credentials: live-value",
        "license_key=live-value",
        "license-key=live-value",
        "https://service.invalid/run?password=hunter2&mode=test",
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9",
        "Authorization=Basic dXNlcjpwYXNz",
        "client_secret=<TOKEN> live-secret",
        'client_secret="<TOKEN>" live-secret',
        "Authorization: <TOKEN> live-secret",
        "token=<TOKEN> extra",
        "Authorization Bearer live-secret",
        "Authorization Basic dXNlcjpwYXNz",
        "Authorization Bearer <TOKEN> extra",
        "token=<TOKEN>-suffix",
        'client_secret="<TOKEN> live-secret"',
        'client_secret="<TOKEN>"live-secret',
        'Authorization: "Bearer <TOKEN> live-secret"',
        'Authorization: "Bearer <TOKEN>"live-secret',
        'Authorization: "Bearer" live-secret',
        'Authorization: "Basic" dXNlcjpwYXNz',
        "api_key=<API_KEY>",
        "token=<TOKEN>. live-secret",
        "credential=***. AKIAIOSFODNN7EXAMPLE",
        "token=<TOKEN>. Continue with live-secret",
        "credential=***. Continue with AKIAIOSFODNN7EXAMPLE",
        "token=<TOKEN>. Swordfish",
        "token=<TOKEN>. Continue with abc123XYZ",
        "token=<TOKEN>. The fallback token is abc123",
        "token=<TOKEN>, live-secret",
        "token=<TOKEN>; live-secret",
        "token=<TOKEN>. Continue with Swordfish",
        "token=<TOKEN>. Swordfish is the official fallback.",
        "token=<TOKEN>. Use Swordfish for the documented account.",
        "token=<TOKEN>&fallback=live-secret",
        "token=<TOKEN>&fallback=abc123XYZ",
        "token=<TOKEN>#live-secret",
        "token=<TOKEN>#fallback=abc123XYZ",
    ),
)
def test_retained_text_rejects_unredacted_secret_assignments_and_redaction_prefix_leaks(
    field: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError, match="secret"):
        retained_text(field, value)


@pytest.mark.parametrize("field", _RETAINED_TEXT_FIELDS)
@pytest.mark.parametrize(
    "value",
    (
        "Run --token live-secret",
        "Run --api-key sk-live-value",
        "Use password hunter2",
        "Use credential AKIAIOSFODNN7EXAMPLE",
        "The password is hunter2.",
        "The token is live-secret.",
        "The API key is sk-live-value.",
        "The token value is live-secret.",
        "Use --token value live-secret.",
        "Authorization header Bearer live-secret",
        "Use `--token live-secret` for the request.",
        "Run `--token` live-secret",
        'Run "--token" live-secret',
        "Run '--token' live-secret",
        "SECRET_KEY=live-secret",
        "--private-key live-secret",
        "--token Swordfish",
        "The password is Swordfish.",
        "The token equals Swordfish.",
        "The token configured: Swordfish.",
        "The token supplied: Swordfish.",
        'The "token" is Swordfish.',
        "The token_value is Swordfish.",
        "--token <TOKEN> Swordfish",
        "--token <TOKEN> Swordfish official flow",
        "The token is configured: Swordfish.",
        "The token is provided: Swordfish.",
        "The apikey is Swordfish.",
        "The access_token is Swordfish.",
        "The secret_key is Swordfish.",
        "Use access_token live-secret.",
        "Run --token option Swordfish.",
        "API key sk-live-value",
        "Private key abc123XYZ",
    ),
)
def test_retained_text_rejects_secret_bearing_cli_and_prose_forms(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match="secret"):
        retained_text(field, value)


@pytest.mark.parametrize("field", _RETAINED_TEXT_FIELDS)
@pytest.mark.parametrize(
    "value",
    (
        "The token is configured with Swordfish.",
        "The token is provided by Swordfish.",
        "The token field with live-secret is retained.",
        "The password policy is Swordfish.",
        "Run --token <TOKEN> only when Swordfish is used.",
        "Run [--token] Swordfish.",
        "Run `--token`=Swordfish.",
        "--passphrase Swordfish",
    ),
)
def test_retained_text_rejects_plain_values_after_secret_bearing_grammar(
    field: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError, match="secret"):
        retained_text(field, value)


@pytest.mark.parametrize("field", _RETAINED_TEXT_FIELDS)
@pytest.mark.parametrize(
    "value",
    (
        "Password hashing uses SHA-256.",
        "Password hashing uses PBKDF2-HMAC-SHA256.",
        "The token parameter supports SHA-256 digests.",
    ),
)
def test_retained_text_accepts_recognized_hash_algorithm_prose(field: str, value: str) -> None:
    assert retained_text(field, value) == value


@pytest.mark.parametrize("field", _RETAINED_TEXT_FIELDS)
@pytest.mark.parametrize(
    "value",
    (
        "Captured from /home/user/project/help.txt",
        "Captured from /Users/user/project/help.txt",
        "Captured from /root/.cache/tool/help.txt",
        r"Captured from C:\Users\user\AppData\Local\Temp\help.txt",
        "Captured from D:/Documents and Settings/user/work/help.txt",
        "Captured from /mnt/c/Users/user/work/help.txt",
        "Captured from /home/<USER>evil/work/help.txt",
        r"Captured from C:\Users\<USER>evil\work\help.txt",
        "Captured from </home/alice/work/help.txt>",
        r"Captured from <C:\Users\alice\work\help.txt>",
        "Captured from,/home/alice/work/help.txt",
        "Captured from file://localhost/home/alice/work/help.txt",
        "Captured from file://localhost/Users/alice/work/help.txt",
        "Captured from file://buildhost/home/alice/work",
        "Captured from file://localhost/root/private",
        "Captured from file://buildhost//home/alice/work",
        "Captured from file://buildhost/home//alice/work",
        "Captured from file://buildhost//home//alice/work",
        r"Captured from \\server\Users\\alice\work",
        r"Captured from \\server\Users\alice\work\help.txt",
        "Captured from /tmp/pytest-of-user/pytest-3/test_help0/output.txt",
        "Captured from /tmp/pytest-of-user/pytest-current/out",
        "Captured from /private/var/folders/aa/bb/T/pytest-of-user/pytest-3/test_help0/output.txt",
    ),
)
def test_retained_text_rejects_capture_host_paths(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match="host path"):
        retained_text(field, value)


@pytest.mark.parametrize("field", _RETAINED_TEXT_FIELDS)
@pytest.mark.parametrize(
    "value",
    (
        "/home//alice/work",
        "/Users//alice/work",
        r"C:\Users\alice\work",
        "file:///home//alice/work",
        r"\\?\C:\Users\alice\work",
    ),
)
def test_retained_text_rejects_doubled_and_extended_capture_host_paths(
    field: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError, match="host path"):
        retained_text(field, value)


@pytest.mark.parametrize("field", _RETAINED_TEXT_FIELDS)
@pytest.mark.parametrize(
    "url",
    (
        "http://user:pass@example.com/docs",
        "https://user@example.com/docs",
        "https://:pass@example.com/docs",
        "https://user:@example.com/docs",
        "ftp://user:pass@example.com/docs",
        "averylongcustomschemeoverthirtytwocharacters://user:pass@example.com/docs",
        "//user:pass@example.com/docs",
        "//user@example.com/docs",
        "docs.//user:pass@example.com/x",
    ),
)
def test_retained_text_rejects_url_userinfo_credentials(field: str, url: str) -> None:
    with pytest.raises(ValidationError, match="userinfo"):
        retained_text(field, f"See {url} for details.")


@pytest.mark.parametrize("field", _RETAINED_TEXT_FIELDS)
@pytest.mark.parametrize(
    "value",
    (
        "Contact user@example.com for details.",
        "Use mailto:user@example.com for support.",
        "See https://example.com/@user/profile for details.",
        "See //example.com/@user/profile for details.",
        "See https://example.com/a//user@example.com/x for a documented path.",
    ),
)
def test_retained_text_accepts_at_signs_outside_uri_authority_userinfo(field: str, value: str) -> None:
    assert retained_text(field, value) == value


@pytest.mark.parametrize("field", _RETAINED_TEXT_FIELDS)
@pytest.mark.parametrize(
    "value",
    (
        "line\u2028separator",
        "paragraph\u2029separator",
        "right-to-left\u202eoverride",
        "zero\u200bwidth",
        "next\x85line",
        "byte-order\ufeffmark",
        "private\ue000use",
    ),
)
def test_retained_text_rejects_unicode_separators_formats_and_controls(
    field: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError, match="printable"):
        retained_text(field, value)


@pytest.mark.parametrize("kind", tuple(evidence.SourceKind))
def test_each_source_kind_has_a_valid_minimal_immutable_json_roundtrip(
    kind: evidence.SourceKind,
) -> None:
    captured = source(kind)
    rebuilt = evidence.EvidenceSource.model_validate_json(captured.model_dump_json())

    assert rebuilt == captured
    assert hash(rebuilt) == hash(captured)
    assert rebuilt.kind is kind
    assert rebuilt.tool_id == "samtools"


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
        "ftp://docs.example.org/tool/manual.html",
        "HTTPS://docs.example.org/tool/manual.html",
        "https://user@docs.example.org/tool/manual.html",
        "https://:password@docs.example.org/tool/manual.html",
        "https://user:@docs.example.org/tool/manual.html",
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


@pytest.mark.parametrize("kind", (evidence.SourceKind.OFFICIAL_MANUAL, evidence.SourceKind.OFFICIAL_API_SCHEMA))
@pytest.mark.parametrize(
    "segment",
    ("latest", "stable", "current", "main", "master", "head", "develop", "release", "trunk"),
)
def test_official_documentation_rejects_moving_url_segments(
    kind: evidence.SourceKind,
    segment: str,
) -> None:
    with pytest.raises(ValidationError, match="moving"):
        source(kind).model_copy(update={"url": f"https://docs.example.org/samtools/{segment}/reference.html"})


@pytest.mark.parametrize("kind", (evidence.SourceKind.OFFICIAL_MANUAL, evidence.SourceKind.OFFICIAL_API_SCHEMA))
@pytest.mark.parametrize("locator", ("latest reference", "stable schema", "current docs", "main branch"))
def test_official_documentation_rejects_moving_version_locators(
    kind: evidence.SourceKind,
    locator: str,
) -> None:
    with pytest.raises(ValidationError, match="moving"):
        source(kind).model_copy(update={"version_locator": locator})


@pytest.mark.parametrize("kind", (evidence.SourceKind.OFFICIAL_MANUAL, evidence.SourceKind.OFFICIAL_API_SCHEMA))
def test_official_documentation_must_bind_exact_tool_version_without_url_mismatch(
    kind: evidence.SourceKind,
) -> None:
    path_bound = source(kind).model_copy(
        update={
            "url": "https://docs.example.org/samtools/1.23.1/reference.html",
            "version_locator": "reference",
        }
    )
    locator_bound = source(kind).model_copy(
        update={
            "url": "https://docs.example.org/samtools/reference.html",
            "version_locator": "1.23.1 reference",
        }
    )

    assert path_bound.url is not None and locator_bound.version_locator == "1.23.1 reference"

    with pytest.raises(ValidationError, match="tool version"):
        source(kind).model_copy(
            update={
                "url": "https://docs.example.org/samtools/1.20/reference.html",
                "version_locator": "1.23.1 reference",
            }
        )
    with pytest.raises(ValidationError, match="tool version"):
        source(kind).model_copy(
            update={
                "url": "https://docs.example.org/samtools/reference.html",
                "version_locator": "reference",
            }
        )


@pytest.mark.parametrize(
    "url",
    (
        "https://docs.example.org/samtools/docs/1.20/reference.html",
        "https://docs.example.org/samtools/user-guide/1.20/reference.html",
    ),
)
def test_official_documentation_rejects_nested_mismatched_tool_versions(url: str) -> None:
    with pytest.raises(ValidationError, match="tool version"):
        source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(
            update={"url": url, "version_locator": "1.23.1 reference"}
        )


@pytest.mark.parametrize(
    "url",
    (
        "https://docs.example.org/samtools-htslib-1.23.1/reference.html",
        "https://docs.example.org/samtools-api-1.23.1/reference.html",
    ),
)
def test_official_documentation_rejects_false_composite_tool_contexts(url: str) -> None:
    with pytest.raises(ValidationError, match="tool version"):
        source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(
            update={"url": url, "version_locator": "1.23.1 reference"}
        )


def test_official_documentation_accepts_nested_matching_tool_version_with_reference_locator() -> None:
    url = "https://docs.example.org/samtools/docs/1.23.1/reference.html"

    captured = source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(
        update={"url": url, "version_locator": "reference"}
    )

    assert captured.url == url
    assert captured.version_locator == "reference"


@pytest.mark.parametrize(
    ("url", "locator"),
    (
        ("https://docs.example.org/samtools-1.20/reference.html", "1.23.1 reference"),
        ("https://docs.example.org/samtools/reference-1.20.html", "1.23.1 reference"),
        ("https://docs.example.org/samtools/1.23.1/reference.html", "samtools-1.20 reference"),
        ("https://docs.example.org/samtools1.20/reference.html", "1.23.1 reference"),
        ("https://docs.example.org/samtoolsV1.20/reference.html", "1.23.1 reference"),
        ("https://docs.example.org/samtools-v1.20/reference.html", "1.23.1 reference"),
        ("https://docs.example.org/samtools-docs-1.20/reference.html", "1.23.1 reference"),
        ("https://docs.example.org/samtools-release-notes-1.20/reference.html", "1.23.1 reference"),
        ("https://docs.example.org/samtools-user-guide-1.20/reference.html", "1.23.1 reference"),
        ("https://docs.example.org/samtools/1.23.1/reference.html", "samtools1.20 reference"),
        ("https://docs.example.org/samtools/1.23.1/reference.html", "samtoolsV1.20 reference"),
        ("https://docs.example.org/samtools/1.23.1/reference.html", "samtools-v1.20 reference"),
        ("https://docs.example.org/samtools/1.23.1/reference.html", "V1.20 reference"),
    ),
)
def test_official_documentation_rejects_conflicting_embedded_dotted_versions(
    url: str,
    locator: str,
) -> None:
    with pytest.raises(ValidationError, match="tool version"):
        source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(update={"url": url, "version_locator": locator})


@pytest.mark.parametrize(
    ("url", "locator"),
    (
        ("https://docs.example.org/samtools-1.23.1/reference.html", "reference"),
        ("https://docs.example.org/samtools/reference-1.23.1.html", "reference"),
        ("https://docs.example.org/samtools/reference.html", "samtools-1.23.1 reference"),
    ),
)
def test_official_documentation_accepts_exact_embedded_dotted_versions(
    url: str,
    locator: str,
) -> None:
    captured = source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(update={"url": url, "version_locator": locator})

    assert captured.url == url
    assert captured.version_locator == locator


@pytest.mark.parametrize(
    ("url", "locator"),
    (
        ("https://docs.example.org/api/2/samtools/1.23.1/reference.html", "section 42"),
        ("https://docs.example.org/2026/samtools/1.23.1/reference.html", "section 42"),
        ("https://docs.example.org/samtools/v1.23.1/reference.html", "section 42"),
        ("https://docs.example.org/samtools/reference.html", "v1.23.1 section 42"),
        ("https://docs.example.org/samtools/V1.23.1/reference.html", "section 42"),
        ("https://docs.example.org/samtools/reference.html", "V1.23.1 section 42"),
        ("https://docs.example.org/api/2.0/samtools/1.23.1/reference.html", "manual"),
        ("https://docs.example.org/samtools/reference.html", "1.23.1 manual, section 1.2"),
    ),
)
def test_official_documentation_ignores_unrelated_numbers_and_normalizes_v_versions(
    url: str,
    locator: str,
) -> None:
    captured = source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(update={"url": url, "version_locator": locator})

    assert captured.url == url
    assert captured.version_locator == locator


@pytest.mark.parametrize(
    ("url", "locator"),
    (
        ("https://docs.example.org/api/1.23.1/samtools/reference.html", "section 42"),
        ("https://docs.example.org/samtools/reference.html", "htslib 1.23.1 reference"),
        ("https://docs.example.org/samtools/reference.html", "htslib version 1.23.1"),
        ("https://docs.example.org/samtools/reference.html", "API documentation 1.23.1"),
    ),
)
def test_official_documentation_does_not_use_unrelated_matching_versions_as_binding(
    url: str,
    locator: str,
) -> None:
    with pytest.raises(ValidationError, match="bind the exact tool version"):
        source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(update={"url": url, "version_locator": locator})


def test_official_documentation_ignores_unrelated_mismatched_tool_versions_when_url_is_bound() -> None:
    captured = source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(update={"version_locator": "htslib version 1.20"})

    assert captured.version_locator == "htslib version 1.20"


def test_official_documentation_accepts_a_matching_suffix_bearing_tool_version() -> None:
    captured = source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(
        update={
            "tool_version": "1.23.1-beta",
            "url": "https://docs.example.org/samtools/1.23.1-beta/reference.html",
            "version_locator": "1.23.1-beta reference",
        }
    )

    assert captured.tool_version == "1.23.1-beta"


@pytest.mark.parametrize(
    "locator",
    ("1.23.1-beta docs", "v1.23.1-beta docs", "1.23.1+build docs", "1.23.1.post1 docs"),
)
def test_official_documentation_rejects_suffixes_when_tool_version_is_core(locator: str) -> None:
    with pytest.raises(ValidationError, match="tool version"):
        source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(update={"version_locator": locator})


def test_official_documentation_rejects_suffix_bearing_url_when_tool_version_is_core() -> None:
    with pytest.raises(ValidationError, match="tool version"):
        source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(
            update={
                "url": "https://docs.example.org/samtools/v1.23.1-beta/reference.html",
                "version_locator": "1.23.1 reference",
            }
        )


@pytest.mark.parametrize("version", ("", "latest", "main", "1.*", ">=1.2", " 1.2", "1.2 ", "1.2\n"))
def test_sources_and_records_require_exact_tool_versions(version: str) -> None:
    with pytest.raises(ValidationError):
        source(evidence.SourceKind.OFFICIAL_MANUAL).model_copy(update={"tool_version": version})
    with pytest.raises(ValidationError):
        evidence_record().model_copy(update={"tool_version": version})


@pytest.mark.parametrize("revision", (COMMIT_A, COMMIT_B))
def test_package_recipe_revision_is_a_full_lowercase_git_object_id(revision: str) -> None:
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
    "pointer",
    (
        "/environment/packages",
        "/environment/packages/0",
        "/environment/packages/0/constraint",
    ),
)
def test_package_recipe_claims_are_scoped_to_environment_packages(pointer: str) -> None:
    recipe = source(evidence.SourceKind.PACKAGE_RECIPE)
    asserted = claim(source_id=recipe.source_id, contract_pointer=pointer)

    record = evidence_record(sources=(recipe,), claims=(asserted,))

    assert record.claims == (asserted,)


@pytest.mark.parametrize(
    "pointer",
    (
        "/environment",
        "/environment/locks/0",
        "/outputs/0",
        "/environment/packages_evil/0",
        "/environment/packages~1evil/0",
        "/environment~1packages/0",
    ),
)
def test_package_recipe_claims_reject_non_package_contract_pointers(pointer: str) -> None:
    recipe = source(evidence.SourceKind.PACKAGE_RECIPE)
    asserted = claim(source_id=recipe.source_id, contract_pointer=pointer)

    with pytest.raises(ValidationError, match="package"):
        evidence_record(sources=(recipe,), claims=(asserted,))


@pytest.mark.parametrize(
    "revision",
    (
        "",
        "latest",
        "main",
        "master",
        "1.2.3",
        "samtools-1.23.1-0",
        "1" * 12,
        "1" * 39,
        "1" * 41,
        "A" * 40,
        "g" * 40,
        "1" * 40 + "\n",
    ),
)
def test_package_recipe_rejects_non_git_or_noncanonical_revisions(revision: str) -> None:
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


@pytest.mark.parametrize(
    "argv",
    (
        ("--help",),
        ("-h",),
        ("-help",),
        ("help",),
        ("view", "--help"),
        ("view", "-h"),
        ("view", "-help"),
        ("help", "view"),
    ),
)
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
        ("-h", "view"),
        ("-help", "view"),
        ("view", "help"),
        ("help", "help"),
        ("help", "View"),
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


def test_claim_pointer_allows_printable_unicode_but_rejects_format_characters() -> None:
    assert claim(contract_pointer="/outputs/測試").contract_pointer == "/outputs/測試"

    with pytest.raises(ValidationError, match="printable"):
        claim(contract_pointer="/outputs/safe\u202eunsafe")


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
    redacted = claim(
        statement="Use the token parameter <TOKEN> only when the official service requires authentication."
    )

    assert redacted.statement.startswith("Use the token parameter <TOKEN>")
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


@pytest.mark.parametrize(
    "kind",
    (
        evidence.SourceKind.OFFICIAL_MANUAL,
        evidence.SourceKind.OFFICIAL_API_SCHEMA,
        evidence.SourceKind.UPSTREAM_SOURCE,
        evidence.SourceKind.INSTALLED_HELP,
        evidence.SourceKind.PACKAGE_RECIPE,
    ),
)
def test_evidence_record_rejects_sources_for_a_different_tool(kind: evidence.SourceKind) -> None:
    captured = source(kind, tool_id="bcftools")
    pointer = "/environment/packages/0/version" if kind is evidence.SourceKind.PACKAGE_RECIPE else "/outputs/0"
    asserted = claim(source_id=captured.source_id, contract_pointer=pointer)

    with pytest.raises(ValidationError, match="tool ID"):
        evidence_record(sources=(captured,), claims=(asserted,))


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


def test_sources_use_authoritative_kind_precedence_then_source_id_order() -> None:
    manual = source(evidence.SourceKind.OFFICIAL_MANUAL, source_id="z-manual")
    api = source(evidence.SourceKind.OFFICIAL_API_SCHEMA, source_id="a-api")
    manual_claim = claim(source_id=manual.source_id)

    precedence_ordered = evidence_record(sources=(manual, api), claims=(manual_claim,))

    assert precedence_ordered.sources == (manual, api)
    with pytest.raises(ValidationError, match="source captures"):
        evidence_record(sources=(api, manual), claims=(manual_claim,))

    first_manual = source(
        evidence.SourceKind.OFFICIAL_MANUAL,
        source_id="a-manual",
        url="https://docs.example.org/samtools/1.23.1/a-reference.html",
    )
    second_manual = source(
        evidence.SourceKind.OFFICIAL_MANUAL,
        source_id="z-manual",
        url="https://docs.example.org/samtools/1.23.1/z-reference.html",
        content_sha256=SHA_D,
    )
    first_claim = claim(source_id=first_manual.source_id)

    same_kind_ordered = evidence_record(sources=(first_manual, second_manual), claims=(first_claim,))

    assert same_kind_ordered.sources == (first_manual, second_manual)
    with pytest.raises(ValidationError, match="source captures"):
        evidence_record(sources=(second_manual, first_manual), claims=(first_claim,))


def test_source_provenance_rejects_duplicate_and_conflicting_captures_under_new_ids() -> None:
    original = source(evidence.SourceKind.OFFICIAL_MANUAL, source_id="a-manual")
    alias = source(
        evidence.SourceKind.OFFICIAL_MANUAL,
        source_id="z-manual",
        title="Renamed retained manual",
        description="A later description for the same authoritative source capture.",
        retrieved_at=date(2026, 7, 16),
    )
    original_claim = claim(source_id=original.source_id)

    with pytest.raises(ValidationError, match="duplicate source capture"):
        evidence_record(sources=(original, alias), claims=(original_claim,))

    conflicting = alias.model_copy(update={"content_sha256": SHA_D})
    with pytest.raises(ValidationError, match="conflicting source capture"):
        evidence_record(sources=(original, conflicting), claims=(original_claim,))


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


def test_same_pointer_claims_from_distinct_sources_must_agree_on_contract_value() -> None:
    manual = source(evidence.SourceKind.OFFICIAL_MANUAL)
    upstream = source(evidence.SourceKind.UPSTREAM_SOURCE)
    manual_claim = claim()
    conflicting = claim(
        claim_id="upstream-output-collector",
        source_id=upstream.source_id,
        excerpt_sha256=SHA_D,
        contract_value_sha256=SHA_D,
    )

    with pytest.raises(ValidationError, match="conflicting contract values"):
        evidence_record(sources=(manual, upstream), claims=(manual_claim, conflicting))


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


def test_verification_provenance_rejects_duplicate_and_conflicting_results_under_new_ids() -> None:
    original = verification("a-smoke")
    alias = verification(
        "z-smoke",
        verified_at=date(2026, 7, 16),
        summary="A later description for the same retained verification capture.",
    )

    with pytest.raises(ValidationError, match="duplicate verification capture"):
        evidence_record(verifications=(original, alias))

    conflicting = alias.model_copy(update={"result_sha256": SHA_C})
    with pytest.raises(ValidationError, match="conflicting verification capture"):
        evidence_record(verifications=(original, conflicting))


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
