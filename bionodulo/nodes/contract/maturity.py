"""Ordered retained maturity gates with release state derived from evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from bionodulo.nodes.contract.artifacts import ArtifactId, _StrictFrozenModel
from bionodulo.nodes.contract.environments import ExactVersion, Sha256Digest, _validate_exact_version
from bionodulo.nodes.contract.evidence import FailureCode, VerificationKind, failure_code_ui_reason


_MAX_ID_LENGTH = 128


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


_ACCESS_CLASS_PRECEDENCE = {item: index for index, item in enumerate(AccessClass)}
_ACCESS_MODES = frozenset(
    {
        AccessClass.PUBLIC,
        AccessClass.PUBLIC_RATE_LIMITED,
        AccessClass.SECRET_REQUIRED,
        AccessClass.BYOL,
        AccessClass.SERVICE_LICENSE,
    }
)
_PUBLIC_INCOMPATIBLE = frozenset(
    {
        AccessClass.PUBLIC_RATE_LIMITED,
        AccessClass.SECRET_REQUIRED,
        AccessClass.BYOL,
        AccessClass.SERVICE_LICENSE,
    }
)
_SECRET_CAPABLE = frozenset(
    {
        AccessClass.PUBLIC_RATE_LIMITED,
        AccessClass.SECRET_REQUIRED,
        AccessClass.BYOL,
        AccessClass.SERVICE_LICENSE,
    }
)
_REQUIRED_SECRET_CAPABLE = frozenset(
    {
        AccessClass.SECRET_REQUIRED,
        AccessClass.BYOL,
        AccessClass.SERVICE_LICENSE,
    }
)
_MANUAL_APPROVAL_CLASSES = frozenset({AccessClass.BYOL, AccessClass.SERVICE_LICENSE})


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


_GATE_FAILURE_CODES = {
    Gate.INVENTORIED: frozenset({FailureCode.INVENTORY_MISSING}),
    Gate.EVIDENCE_VERIFIED: frozenset({FailureCode.EVIDENCE_MISSING, FailureCode.EVIDENCE_CONFLICT}),
    Gate.CONTRACT_VERIFIED: frozenset({FailureCode.CONTRACT_INVALID}),
    Gate.COMMAND_VERIFIED: frozenset({FailureCode.COMMAND_FIXTURE_FAILED}),
    Gate.ENVIRONMENT_VERIFIED: frozenset({FailureCode.ENVIRONMENT_RESOLUTION_FAILED}),
    Gate.TOOL_SMOKE_VERIFIED: frozenset({FailureCode.TOOL_SMOKE_FAILED}),
    Gate.CLOUD_VERIFIED: frozenset({FailureCode.CLOUD_RUN_FAILED}),
    Gate.WORKFLOW_VERIFIED: frozenset({FailureCode.WORKFLOW_RUN_FAILED}),
}

_GATE_VERIFICATION_KINDS = {
    Gate.INVENTORIED: VerificationKind.INVENTORY,
    Gate.EVIDENCE_VERIFIED: VerificationKind.EVIDENCE_COVERAGE,
    Gate.CONTRACT_VERIFIED: VerificationKind.CONTRACT_COMPILE,
    Gate.COMMAND_VERIFIED: VerificationKind.COMMAND_FIXTURE,
    Gate.ENVIRONMENT_VERIFIED: VerificationKind.ENVIRONMENT_PROBE,
    Gate.TOOL_SMOKE_VERIFIED: VerificationKind.TOOL_SMOKE,
    Gate.CLOUD_VERIFIED: VerificationKind.CLOUD_RUN,
    Gate.WORKFLOW_VERIFIED: VerificationKind.WORKFLOW_RUN,
}

_GATE_UI_LABELS = {
    Gate.INVENTORIED: "Inventory verification",
    Gate.EVIDENCE_VERIFIED: "Evidence verification",
    Gate.CONTRACT_VERIFIED: "Contract verification",
    Gate.COMMAND_VERIFIED: "Command verification",
    Gate.ENVIRONMENT_VERIFIED: "Environment verification",
    Gate.TOOL_SMOKE_VERIFIED: "Tool smoke verification",
    Gate.CLOUD_VERIFIED: "Cloud verification",
    Gate.WORKFLOW_VERIFIED: "Workflow verification",
}


class GateAssessment(_StrictFrozenModel):
    gate: Gate
    result: GateResult
    verification_digests: Annotated[tuple[Sha256Digest, ...], Field(min_length=1, max_length=256)]
    verified_at: date
    verifier_id: ArtifactId
    verifier_version: ExactVersion
    failure_code: FailureCode | None = None

    @field_validator("verifier_id")
    @classmethod
    def _validate_verifier_id(cls, value: str) -> str:
        return _validate_bounded_id(value, label="verifier ID")

    @field_validator("verifier_version")
    @classmethod
    def _validate_verifier_version(cls, value: str) -> str:
        return _validate_exact_version(value)

    @model_validator(mode="after")
    def _validate_result_evidence(self) -> Self:
        if len(set(self.verification_digests)) != len(self.verification_digests):
            raise ValueError("assessment verification digests must be unique")
        if self.verification_digests != tuple(sorted(self.verification_digests)):
            raise ValueError("assessment verification digests must use canonical order")
        if self.result is GateResult.PASSED:
            if self.failure_code is not None:
                raise ValueError("passed gate must not declare a failure code")
        elif self.failure_code is None:
            raise ValueError("failed gate requires a failure code")
        elif self.failure_code not in _GATE_FAILURE_CODES[self.gate]:
            raise ValueError("gate failure code is not valid for that gate")
        return self

    @property
    def ui_summary(self) -> str:
        suffix = "passed" if self.result is GateResult.PASSED else "failed"
        return f"{_GATE_UI_LABELS[self.gate]} {suffix}"

    @property
    def ui_reason(self) -> str | None:
        return None if self.failure_code is None else failure_code_ui_reason(self.failure_code)

    @property
    def verification_kind(self) -> VerificationKind:
        return _GATE_VERIFICATION_KINDS[self.gate]


class MaturityRecord(_StrictFrozenModel):
    schema_version: Literal[2]
    access_classes: Annotated[tuple[AccessClass, ...], Field(min_length=1, max_length=7)]
    assessments: Annotated[tuple[GateAssessment, ...], Field(max_length=8)] = ()

    @model_validator(mode="after")
    def _validate_record(self) -> Self:
        if len(set(self.access_classes)) != len(self.access_classes):
            raise ValueError("access classes must be unique")
        access_order = tuple(_ACCESS_CLASS_PRECEDENCE[item] for item in self.access_classes)
        if access_order != tuple(sorted(access_order)):
            raise ValueError("access classes must use canonical enum order")
        access_set = set(self.access_classes)
        if not access_set & _ACCESS_MODES:
            raise ValueError("access classes must include an access mode")
        if AccessClass.PUBLIC in access_set and access_set & _PUBLIC_INCOMPATIBLE:
            raise ValueError("public access must not coexist with credential or license access classes")

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
        return bool(set(self.access_classes) & _MANUAL_APPROVAL_CLASSES)

    @property
    def permits_secrets(self) -> bool:
        return bool(set(self.access_classes) & _SECRET_CAPABLE)

    @property
    def permits_required_secrets(self) -> bool:
        return bool(set(self.access_classes) & _REQUIRED_SECRET_CAPABLE)

    @property
    def requires_secret(self) -> bool:
        return AccessClass.SECRET_REQUIRED in self.access_classes

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
            return self.assessments[-1].ui_reason
        if self.next_gate is not None:
            return f"{_GATE_UI_LABELS[self.next_gate]} has not passed"
        if self.manual_approval_required:
            manual_classes = ", ".join(item.value for item in self.access_classes if item in _MANUAL_APPROVAL_CLASSES)
            return f"{manual_classes} requires manual approval"
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
