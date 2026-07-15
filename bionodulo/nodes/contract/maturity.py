"""Ordered retained maturity gates with release state derived from evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from bionodulo.nodes.contract.artifacts import ArtifactId, _StrictFrozenModel
from bionodulo.nodes.contract.environments import ExactVersion, Sha256Digest, _validate_exact_version
from bionodulo.nodes.contract.evidence import _validate_retained_text


_MAX_ID_LENGTH = 128

AssessmentSummary = Annotated[str, StringConstraints(min_length=1, max_length=2048)]
AssessmentReason = Annotated[str, StringConstraints(min_length=1, max_length=1024)]


def _canonical_digest(value: _StrictFrozenModel) -> str:
    payload = json.dumps(
        value.model_dump(mode="json", round_trip=True),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _validate_bounded_id(value: str, *, label: str) -> str:
    if len(value) > _MAX_ID_LENGTH:
        raise ValueError(f"{label} must be at most {_MAX_ID_LENGTH} characters")
    return value


class AccessClass(StrEnum):
    PUBLIC = "public"
    PUBLIC_RATE_LIMITED = "public_rate_limited"
    SECRET_REQUIRED = "secret_required"
    LARGE_REFERENCE = "large_reference"
    GPU_REQUIRED = "gpu_required"
    BYOL = "byol"
    SERVICE_LICENSE = "service_license"


class Gate(StrEnum):
    INVENTORIED = "inventoried"
    EVIDENCE_VERIFIED = "evidence_verified"
    CONTRACT_VERIFIED = "contract_verified"
    COMMAND_VERIFIED = "command_verified"
    ENVIRONMENT_VERIFIED = "environment_verified"
    TOOL_SMOKE_VERIFIED = "tool_smoke_verified"
    CLOUD_VERIFIED = "cloud_verified"
    WORKFLOW_VERIFIED = "workflow_verified"


class GateResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class GateAssessment(_StrictFrozenModel):
    gate: Gate
    result: GateResult
    evidence_digests: Annotated[tuple[Sha256Digest, ...], Field(max_length=256)] = ()
    verified_at: date
    verifier_id: ArtifactId
    verifier_version: ExactVersion
    summary: AssessmentSummary
    reason: AssessmentReason | None = None

    @field_validator("verifier_id")
    @classmethod
    def _validate_verifier_id(cls, value: str) -> str:
        return _validate_bounded_id(value, label="verifier ID")

    @field_validator("verifier_version")
    @classmethod
    def _validate_verifier_version(cls, value: str) -> str:
        return _validate_exact_version(value)

    @field_validator("summary", "reason")
    @classmethod
    def _validate_assessment_text(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        label = getattr(info, "field_name", "assessment text").replace("_", " ")
        return _validate_retained_text(value, label=label)

    @model_validator(mode="after")
    def _validate_result_evidence(self) -> Self:
        if len(set(self.evidence_digests)) != len(self.evidence_digests):
            raise ValueError("assessment evidence digests must be unique")
        if self.evidence_digests != tuple(sorted(self.evidence_digests)):
            raise ValueError("assessment evidence digests must use canonical order")
        if self.result is GateResult.PASSED:
            if not self.evidence_digests:
                raise ValueError("passed gate requires retained evidence digests")
            if self.reason is not None:
                raise ValueError("passed gate must not declare a failure reason")
        elif self.reason is None:
            raise ValueError("failed gate requires a nonempty reason")
        return self


class MaturityRecord(_StrictFrozenModel):
    access: AccessClass
    assessments: Annotated[tuple[GateAssessment, ...], Field(max_length=8)] = ()

    @model_validator(mode="after")
    def _validate_assessment_progression(self) -> Self:
        gates = tuple(Gate)
        for index, assessed in enumerate(self.assessments):
            expected = gates[index]
            if assessed.gate is not expected:
                raise ValueError(
                    f"assessment gates must be contiguous: expected {expected.value}, got {assessed.gate.value}"
                )
            if assessed.result is GateResult.FAILED and index != len(self.assessments) - 1:
                raise ValueError("assessment progression must stop after the first failed gate")
        return self

    @property
    def passed(self) -> tuple[Gate, ...]:
        return tuple(assessed.gate for assessed in self.assessments if assessed.result is GateResult.PASSED)

    @property
    def blocking_gate(self) -> Gate | None:
        if self.assessments and self.assessments[-1].result is GateResult.FAILED:
            return self.assessments[-1].gate
        return None

    @property
    def next_gate(self) -> Gate | None:
        if self.blocking_gate is not None:
            return self.blocking_gate
        gates = tuple(Gate)
        if len(self.assessments) < len(gates):
            return gates[len(self.assessments)]
        return None

    @property
    def manual_approval_required(self) -> bool:
        return self.access in (AccessClass.BYOL, AccessClass.SERVICE_LICENSE)

    @property
    def released(self) -> bool:
        return (
            len(self.assessments) == len(Gate)
            and all(assessed.result is GateResult.PASSED for assessed in self.assessments)
            and not self.manual_approval_required
        )

    @property
    def quarantined(self) -> bool:
        return not self.released

    @property
    def release_block_reason(self) -> str | None:
        if self.released:
            return None
        if self.blocking_gate is not None:
            assert self.assessments[-1].reason is not None
            return self.assessments[-1].reason
        if self.next_gate is not None:
            return f"{self.next_gate.value} has not passed"
        if self.manual_approval_required:
            return f"{self.access.value} requires manual approval"
        return None

    def maturity_digest(self) -> str:
        return _canonical_digest(self)


__all__ = [
    "AccessClass",
    "Gate",
    "GateAssessment",
    "GateResult",
    "MaturityRecord",
]
