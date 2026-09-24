"""Strict data-only import profile for native CWL v1.2 command tools.

This module intentionally implements a small, auditable subset of CWL.  It
normalises a ``CommandLineTool`` into the existing :class:`NodeSpec` contract;
it is not a general CWL evaluator and never interprets JavaScript or shell
expressions.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Self
from urllib.parse import urlsplit

from pydantic import Field, StringConstraints, field_validator, model_validator

from bionodulo.nodes.contract.artifacts import ArtifactId, ArtifactPort, Cardinality, _StrictFrozenModel
from bionodulo.nodes.contract.environments import (
    EnvironmentSpec,
    PixiEnvironment,
    PythonEnvironment,
    REnvironment,
    Sha256Digest,
)
from bionodulo.nodes.contract.outputs import ExactCollector, OutputSpec, StdoutCollector
from bionodulo.nodes.contract.parameters import ParameterSpec, ValueKind

if TYPE_CHECKING:
    from bionodulo.nodes.contract.model import ExecutionKind, NodeSpec, RuntimeBinding


DECLARATIVE_CWL_FACTORY = "bionodulo.nodes.declarative_cwl:DeclarativeCwlNode"
CWL_ADAPTER_RESERVED_INPUT_IDS = frozenset({"context", "output_dir"})
_MAX_TOKEN_BYTES = 4_096
_MAX_BINDINGS = 1_024
_ALLOWED_TOP_LEVEL = frozenset(
    {
        "cwlVersion",
        "class",
        "id",
        "label",
        "doc",
        "baseCommand",
        "inputs",
        "outputs",
        "arguments",
        "stdout",
    }
)


class CwlImportError(ValueError):
    """The document is outside the supported native CWL profile."""


class CwlInputKind(StrEnum):
    FILE = "file"
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"


def _validate_token(value: str, *, label: str, allow_whitespace: bool = True) -> str:
    if not value or value != value.strip() or "\x00" in value:
        raise ValueError(f"{label} must be a nonempty exact token")
    if not all(character.isprintable() for character in value):
        raise ValueError(f"{label} must contain only printable characters")
    if not allow_whitespace and any(character.isspace() for character in value):
        raise ValueError(f"{label} must be one argv token")
    if len(value.encode("utf-8")) > _MAX_TOKEN_BYTES:
        raise ValueError(f"{label} exceeds {_MAX_TOKEN_BYTES} UTF-8 bytes")
    return value


class CwlInputBinding(_StrictFrozenModel):
    input_id: ArtifactId
    kind: CwlInputKind
    required: bool
    has_default: bool = False
    default: object = None
    position: Annotated[int, Field(strict=True, ge=0, le=1_000_000)]
    prefix: Annotated[str, StringConstraints(min_length=1, max_length=256)] | None = None

    @field_validator("prefix")
    @classmethod
    def _validate_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_token(value, label="CWL input prefix", allow_whitespace=False)

    @model_validator(mode="after")
    def _validate_default(self) -> Self:
        if not self.has_default and self.default is not None:
            raise ValueError("CWL input default requires has_default=true")
        if self.required and self.has_default:
            raise ValueError("a CWL input with a default is not required")
        if self.has_default:
            _validate_default_value(self.kind, self.default)
        return self


class CwlLiteralArgument(_StrictFrozenModel):
    value: Annotated[str, StringConstraints(min_length=1, max_length=_MAX_TOKEN_BYTES)]
    position: Annotated[int, Field(strict=True, ge=0, le=1_000_000)]

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: str) -> str:
        return _validate_token(value, label="CWL literal argument")


class CwlInvocation(_StrictFrozenModel):
    source_uri: Annotated[str, StringConstraints(min_length=1, max_length=2_048)]
    # Hash of the parsed document's canonical JSON representation. This binds
    # execution semantics, but deliberately does not claim byte-for-byte source
    # identity because YAML spelling, comments, and whitespace are discarded by
    # parsing.
    descriptor_sha256: Sha256Digest
    # Exact upstream bytes, supplied by file/network callers before parsing.
    # Programmatic dict callers may omit this pair without inventing provenance.
    source_content_sha256: Sha256Digest | None = None
    source_size_bytes: Annotated[int, Field(strict=True, ge=0)] | None = None
    base_command: Annotated[tuple[str, ...], Field(min_length=1, max_length=64)]
    input_bindings: Annotated[tuple[CwlInputBinding, ...], Field(max_length=_MAX_BINDINGS)] = ()
    literal_arguments: Annotated[tuple[CwlLiteralArgument, ...], Field(max_length=_MAX_BINDINGS)] = ()

    @field_validator("source_uri")
    @classmethod
    def _validate_source_uri(cls, value: str) -> str:
        _validate_token(value, label="CWL source URI", allow_whitespace=False)
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "file"}:
            raise ValueError("CWL source URI must use https or file")
        if parsed.scheme == "https" and not parsed.hostname:
            raise ValueError("CWL https source URI requires a host")
        if parsed.scheme == "file" and not parsed.path.startswith("/"):
            raise ValueError("CWL file source URI must be absolute")
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError("CWL source URI must not contain credentials or a fragment")
        return value

    @field_validator("base_command")
    @classmethod
    def _validate_base_command(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            _validate_token(value, label="CWL baseCommand token")
        return values

    @model_validator(mode="after")
    def _validate_bindings(self) -> Self:
        if (self.source_content_sha256 is None) != (self.source_size_bytes is None):
            raise ValueError("CWL raw source digest and size must be supplied together")
        input_ids = tuple(binding.input_id for binding in self.input_bindings)
        if len(set(input_ids)) != len(input_ids):
            raise ValueError("CWL input binding IDs must be unique")
        positions = tuple(binding.position for binding in self.input_bindings) + tuple(
            argument.position for argument in self.literal_arguments
        )
        if len(set(positions)) != len(positions):
            raise ValueError("CWL binding positions must be unique in the strict profile")
        if self.input_bindings != tuple(sorted(self.input_bindings, key=lambda item: (item.position, item.input_id))):
            raise ValueError("CWL input bindings must use canonical position order")
        if self.literal_arguments != tuple(
            sorted(self.literal_arguments, key=lambda item: (item.position, item.value))
        ):
            raise ValueError("CWL literal arguments must use canonical position order")
        return self


def _canonical_document(document: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            document,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as error:
        raise CwlImportError(f"CWL document must be canonical JSON data: {error}") from error


def _descriptor_digest(document: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_document(document)).hexdigest()


def _mapping(value: object, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CwlImportError(f"{label} must be an object")
    if any(not isinstance(key, str) or not key for key in value):
        raise CwlImportError(f"{label} keys must be nonempty strings")
    return value


def _named_definitions(value: object, *, label: str) -> tuple[tuple[str, object], ...]:
    """Normalise the two native CWL map/list parameter declaration forms."""

    if isinstance(value, Mapping):
        mapping = _mapping(value, label=label)
        return tuple(sorted(mapping.items()))
    if not isinstance(value, list):
        raise CwlImportError(f"{label} must be an object or an array of objects with id")
    result: list[tuple[str, object]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        item = _mapping(raw, label=f"{label}[{index}]")
        raw_id = item.get("id")
        if not isinstance(raw_id, str) or not raw_id:
            raise CwlImportError(f"{label}[{index}] requires a nonempty string id")
        item_id = raw_id.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        if not item_id or item_id in seen:
            raise CwlImportError(f"{label} contains a missing or duplicate id: {raw_id!r}")
        seen.add(item_id)
        result.append((item_id, {key: entry for key, entry in item.items() if key != "id"}))
    return tuple(sorted(result))


def _reject_unknown(mapping: Mapping[str, Any], allowed: set[str] | frozenset[str], *, label: str) -> None:
    unsupported = sorted(set(mapping) - set(allowed))
    if unsupported:
        raise CwlImportError(f"{label} uses unsupported field(s): {', '.join(unsupported)}")


def _type_name(raw: object, *, label: str) -> tuple[str, bool]:
    required = True
    if isinstance(raw, str):
        if raw.endswith("?"):
            raw = raw[:-1]
            required = False
        name = raw
    elif (
        isinstance(raw, list)
        and len(raw) == 2
        and "null" in raw
        and all(isinstance(item, str) for item in raw)
    ):
        name = raw[1] if raw[0] == "null" else raw[0]
        required = False
    else:
        raise CwlImportError(f"{label} type must be a supported scalar or ['null', type] union")
    if name not in {"File", "string", "int", "float", "boolean", "stdout"}:
        raise CwlImportError(f"{label} uses unsupported CWL type: {name!r}")
    return name, required


def _validate_default_value(kind: CwlInputKind, value: object) -> None:
    valid = {
        CwlInputKind.FILE: lambda candidate: isinstance(candidate, str) and bool(candidate),
        CwlInputKind.STRING: lambda candidate: isinstance(candidate, str),
        CwlInputKind.INTEGER: lambda candidate: type(candidate) is int,
        CwlInputKind.NUMBER: lambda candidate: type(candidate) in (int, float),
        CwlInputKind.BOOLEAN: lambda candidate: type(candidate) is bool,
    }[kind](value)
    if not valid:
        raise ValueError(f"default does not match CWL {kind.value} input type")


def _input_kind(type_name: str) -> CwlInputKind:
    return {
        "File": CwlInputKind.FILE,
        "string": CwlInputKind.STRING,
        "int": CwlInputKind.INTEGER,
        "float": CwlInputKind.NUMBER,
        "boolean": CwlInputKind.BOOLEAN,
    }[type_name]


def _parameter_kind(kind: CwlInputKind) -> ValueKind:
    return {
        CwlInputKind.STRING: ValueKind.STRING,
        CwlInputKind.INTEGER: ValueKind.INTEGER,
        CwlInputKind.NUMBER: ValueKind.NUMBER,
        CwlInputKind.BOOLEAN: ValueKind.BOOLEAN,
    }[kind]


def _parse_input(
    input_id: str,
    raw: object,
) -> tuple[CwlInputBinding | None, ArtifactPort | None, ParameterSpec | None]:
    if input_id in CWL_ADAPTER_RESERVED_INPUT_IDS:
        raise CwlImportError(f"CWL input {input_id!r} is reserved by the execution adapter")
    definition: Mapping[str, Any]
    if isinstance(raw, str) or isinstance(raw, list):
        definition = {"type": raw}
    else:
        definition = _mapping(raw, label=f"CWL input {input_id!r}")
    _reject_unknown(definition, {"type", "label", "doc", "default", "inputBinding"}, label=f"CWL input {input_id!r}")
    if "type" not in definition:
        raise CwlImportError(f"CWL input {input_id!r} is missing type")
    type_name, required = _type_name(definition["type"], label=f"CWL input {input_id!r}")
    if type_name == "stdout":
        raise CwlImportError(f"CWL input {input_id!r} cannot use stdout type")
    has_default = "default" in definition
    default = definition.get("default")
    if has_default:
        required = False
    kind = _input_kind(type_name)
    if kind is CwlInputKind.FILE and has_default:
        raise CwlImportError(f"CWL File input {input_id!r} defaults are unsupported; stage an explicit input")
    try:
        _validate_default_value(kind, default) if has_default else None
    except ValueError as error:
        raise CwlImportError(f"CWL input {input_id!r} {error}") from error

    raw_binding = definition.get("inputBinding")
    if raw_binding is None:
        binding_doc = None
    else:
        binding_doc = _mapping(raw_binding, label=f"CWL input {input_id!r}.inputBinding")
    if binding_doc is None:
        binding = None
    else:
        _reject_unknown(binding_doc, {"position", "prefix", "separate"}, label=f"CWL input {input_id!r}.inputBinding")
        if "position" not in binding_doc or type(binding_doc["position"]) is not int:
            raise CwlImportError(f"CWL input {input_id!r}.inputBinding requires an integer position")
        if binding_doc.get("separate", True) is not True:
            raise CwlImportError(f"CWL input {input_id!r} separate=false is unsupported")
        prefix = binding_doc.get("prefix")
        if prefix is not None and not isinstance(prefix, str):
            raise CwlImportError(f"CWL input {input_id!r} prefix must be a string")
        try:
            binding = CwlInputBinding(
                input_id=input_id,
                kind=kind,
                required=required,
                has_default=has_default,
                default=default,
                position=binding_doc["position"],
                prefix=prefix,
            )
        except ValueError as error:
            raise CwlImportError(f"invalid CWL input {input_id!r}: {error}") from error
    if kind is CwlInputKind.FILE:
        return (
            binding,
            ArtifactPort(
                port_id=input_id,
                artifact_type="artifact.file",
                cardinality=Cardinality.ONE if required else Cardinality.OPTIONAL_ONE,
            ),
            None,
        )
    return (
        binding,
        None,
        ParameterSpec(
            parameter_id=input_id,
            kind=_parameter_kind(kind),
            required=required,
            has_default=has_default,
            default=default,
            description=str(definition.get("doc") or definition.get("label") or ""),
        ),
    )


def _parse_arguments(raw: object) -> tuple[CwlLiteralArgument, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise CwlImportError("CWL arguments must be an array")
    result: list[CwlLiteralArgument] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise CwlImportError(
                f"CWL arguments[{index}] must be an object with literal valueFrom and explicit position"
            )
        _reject_unknown(item, {"valueFrom", "position"}, label=f"CWL arguments[{index}]")
        if not isinstance(item.get("valueFrom"), str):
            raise CwlImportError(f"CWL arguments[{index}].valueFrom must be a literal string")
        value = item["valueFrom"]
        if "$" in value or "$(" in value or "${" in value:
            raise CwlImportError(f"CWL arguments[{index}] JavaScript/value expressions are unsupported")
        if type(item.get("position")) is not int:
            raise CwlImportError(f"CWL arguments[{index}] requires an integer position")
        try:
            result.append(CwlLiteralArgument(value=value, position=item["position"]))
        except ValueError as error:
            raise CwlImportError(f"invalid CWL arguments[{index}]: {error}") from error
    return tuple(sorted(result, key=lambda item: (item.position, item.value)))


def _safe_relative_output(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CwlImportError(f"{label} must be one literal relative file path")
    if any(character in value for character in "*?[]$(){}"):
        raise CwlImportError(f"{label} patterns and expressions are unsupported")
    try:
        return ExactCollector(relative_path=value).relative_path
    except ValueError as error:
        raise CwlImportError(f"invalid {label}: {error}") from error


def _parse_outputs(document: Mapping[str, Any]) -> tuple[OutputSpec, ...]:
    outputs_doc = _named_definitions(document.get("outputs", {}), label="CWL outputs")
    if len(outputs_doc) != 1:
        raise CwlImportError("the strict CWL profile requires exactly one output")
    stdout_path = document.get("stdout")
    if stdout_path is not None:
        stdout_path = _safe_relative_output(stdout_path, label="CWL stdout")
    outputs: list[OutputSpec] = []
    stdout_count = 0
    for output_id, raw in outputs_doc:
        definition = {"type": raw} if isinstance(raw, str) else _mapping(raw, label=f"CWL output {output_id!r}")
        _reject_unknown(definition, {"type", "label", "doc", "outputBinding"}, label=f"CWL output {output_id!r}")
        if "type" not in definition:
            raise CwlImportError(f"CWL output {output_id!r} is missing type")
        type_name, required = _type_name(definition["type"], label=f"CWL output {output_id!r}")
        if not required:
            raise CwlImportError(f"CWL output {output_id!r} optional outputs are outside the strict profile")
        if type_name == "stdout":
            stdout_count += 1
            if stdout_path is None:
                raise CwlImportError(f"CWL stdout output {output_id!r} requires top-level stdout")
            if "outputBinding" in definition:
                raise CwlImportError(f"CWL stdout output {output_id!r} must not declare outputBinding")
            collector = StdoutCollector(relative_path=stdout_path)
        elif type_name == "File":
            binding = _mapping(definition.get("outputBinding"), label=f"CWL output {output_id!r}.outputBinding")
            _reject_unknown(binding, {"glob"}, label=f"CWL output {output_id!r}.outputBinding")
            output_path = _safe_relative_output(binding.get("glob"), label=f"CWL output {output_id!r} glob")
            if stdout_path is not None and output_path == stdout_path:
                stdout_count += 1
                collector = StdoutCollector(relative_path=output_path)
            else:
                collector = ExactCollector(relative_path=output_path)
        else:
            raise CwlImportError(f"CWL output {output_id!r} must be File or stdout")
        outputs.append(
            OutputSpec(
                port_id=output_id,
                artifact_type="artifact.file",
                collector=collector,
                # CWL File does not imply non-empty content.
                require_nonempty=False,
            )
        )
    if stdout_count > 1:
        raise CwlImportError("the strict CWL profile permits at most one stdout output")
    if stdout_path is not None and stdout_count != 1:
        raise CwlImportError("top-level CWL stdout requires exactly one stdout output")
    if not outputs:
        raise CwlImportError("CWL CommandLineTool must declare at least one output")
    return tuple(outputs)


def _runtime_binding(
    environment: EnvironmentSpec,
    *,
    executable_name: str,
    tool_id: str,
    tool_version: str,
) -> tuple[ExecutionKind, RuntimeBinding]:
    from bionodulo.nodes.contract.model import ExecutionKind, RuntimeBinding

    # The first executable slice is native argv in an existing, fully locked
    # package environment. Container contracts remain modelled elsewhere, but
    # accepting one here before a container backend exists would overstate the
    # descriptor's executability.
    if not isinstance(environment, (PixiEnvironment, PythonEnvironment, REnvironment)):
        raise CwlImportError("native CWL import currently requires a locked package environment")
    matching_probes = tuple(
        item
        for item in environment.executable_probes
        if item.expected_version == tool_version
        and item.locator.replace("\\", "/").rsplit("/", 1)[-1] == executable_name
    )
    if not matching_probes:
        raise CwlImportError(
            f"locked environment must declare exactly one executable probe for {executable_name!r} "
            f"at version {tool_version!r}"
        )
    if len(matching_probes) > 1:
        raise CwlImportError(
            f"locked environment declares ambiguous executable probes for {executable_name!r} "
            f"at version {tool_version!r}"
        )
    probe = matching_probes[0]
    if probe.fingerprint is None:
        raise CwlImportError(
            f"executable probe {probe.probe_id!r} for {executable_name!r} must declare a binary fingerprint"
        )
    package = next((item for item in environment.packages if item.name == tool_id), None)
    if package is not None:
        return (
            ExecutionKind.ARGV,
            RuntimeBinding(
                tool_id=tool_id,
                tool_version=tool_version,
                execution_kind=ExecutionKind.ARGV,
                execution_factory=DECLARATIVE_CWL_FACTORY,
                package_name=tool_id,
            ),
        )
    return (
        ExecutionKind.ARGV,
        RuntimeBinding(
            tool_id=tool_id,
            tool_version=tool_version,
            execution_kind=ExecutionKind.ARGV,
            execution_factory=DECLARATIVE_CWL_FACTORY,
            probe_id=probe.probe_id,
        ),
    )


def import_cwl(
    document: dict[str, Any],
    *,
    node_id: str,
    environment: EnvironmentSpec,
    tool_id: str,
    tool_version: str,
    source_uri: str,
    source_content_sha256: str | None = None,
    source_size_bytes: int | None = None,
) -> NodeSpec:
    """Import one strict native CWL v1.2 ``CommandLineTool`` as a quarantined spec."""

    from bionodulo.nodes.contract.model import (
        NodeIdentity,
        NodeOwnership,
        NodePresentation,
        NodeSpec,
    )
    # Keep the catalog registry import behind the public import boundary.
    # ``catalog.artifacts`` itself imports contract models during package
    # initialisation, so importing it at module load time creates a cycle when
    # callers discover artifact types before CWL support.
    from bionodulo.nodes.catalog.artifacts import ARTIFACT_REGISTRY

    if type(document) is not dict:
        raise CwlImportError("CWL document must be an object")
    _canonical_document(document)
    _reject_unknown(document, _ALLOWED_TOP_LEVEL, label="CWL CommandLineTool")
    if document.get("cwlVersion") != "v1.2":
        raise CwlImportError("native CWL import requires cwlVersion 'v1.2'")
    if document.get("class") != "CommandLineTool":
        raise CwlImportError("native CWL import supports CommandLineTool only")

    base_command_raw = document.get("baseCommand")
    if isinstance(base_command_raw, str):
        base_command = (base_command_raw,)
    elif isinstance(base_command_raw, list) and base_command_raw and all(
        isinstance(item, str) for item in base_command_raw
    ):
        base_command = tuple(base_command_raw)
    else:
        raise CwlImportError("CWL baseCommand must be a nonempty string or string array")

    bindings: list[CwlInputBinding] = []
    artifact_inputs: list[ArtifactPort] = []
    parameters: list[ParameterSpec] = []
    for input_id, raw in _named_definitions(document.get("inputs", {}), label="CWL inputs"):
        binding, artifact_input, parameter = _parse_input(input_id, raw)
        if binding is not None:
            bindings.append(binding)
        if artifact_input is not None:
            artifact_inputs.append(artifact_input)
        if parameter is not None:
            parameters.append(parameter)
    bindings.sort(key=lambda item: (item.position, item.input_id))
    literal_arguments = _parse_arguments(document.get("arguments"))
    outputs = _parse_outputs(document)
    try:
        file_type_registered = ARTIFACT_REGISTRY.is_type_compatible("artifact.file", "artifact.file")
    except Exception as error:
        raise CwlImportError("generic artifact.file type is not registered") from error
    if not file_type_registered:
        raise CwlImportError("generic artifact.file type is not registered")

    try:
        invocation = CwlInvocation(
            source_uri=source_uri,
            descriptor_sha256=_descriptor_digest(document),
            source_content_sha256=source_content_sha256,
            source_size_bytes=source_size_bytes,
            base_command=base_command,
            input_bindings=tuple(bindings),
            literal_arguments=literal_arguments,
        )
    except ValueError as error:
        raise CwlImportError(f"invalid CWL invocation: {error}") from error
    execution_kind, runtime_binding = _runtime_binding(
        environment,
        executable_name=base_command[0].replace("\\", "/").rsplit("/", 1)[-1],
        tool_id=tool_id,
        tool_version=tool_version,
    )
    label = document.get("label")
    doc = document.get("doc")
    display_name = label if isinstance(label, str) and label.strip() else node_id.replace("_", " ").title()
    description = doc if isinstance(doc, str) and doc.strip() else f"Imported CWL tool {tool_id} {tool_version}."
    try:
        return NodeSpec(
            identity=NodeIdentity(
                stable_id=f"cwl::{node_id}",
                machine_id=node_id,
                contract_version="2.0.0",
                implementation_version="1.0.0",
                tool_id=tool_id,
                tool_version=tool_version,
            ),
            presentation=NodePresentation(
                display_name=display_name,
                description=description,
                palette_path=("Imported", "CWL"),
                domain_tags=("cwl", tool_id) if tool_id != "cwl" else ("cwl",),
                operation_kind="transform",
                owner=NodeOwnership.EXTERNAL_TOOL,
                tool_family=tool_id,
            ),
            artifact_inputs=tuple(artifact_inputs),
            parameters=tuple(parameters),
            outputs=outputs,
            environment=environment,
            execution_kind=execution_kind,
            execution_factory=DECLARATIVE_CWL_FACTORY,
            runtime_binding=runtime_binding,
            cwl_invocation=invocation,
        )
    except ValueError as error:
        raise CwlImportError(f"imported CWL contract is invalid: {error}") from error


__all__ = [
    "CwlImportError",
    "CWL_ADAPTER_RESERVED_INPUT_IDS",
    "CwlInputBinding",
    "CwlInputKind",
    "CwlInvocation",
    "CwlLiteralArgument",
    "DECLARATIVE_CWL_FACTORY",
    "import_cwl",
]
