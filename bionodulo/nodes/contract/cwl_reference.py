"""Data-only contracts for execution by the locked CWL reference engine.

Unlike the deliberately small native CWL profile, this profile retains the
exact upstream document and delegates CWL expression, argument, staging, and
output semantics to ``cwltool``.  The parser here only projects a safe UI
schema and rejects documents whose host/runtime requirements cannot be stated
truthfully by the current native backend.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Annotated, Any, Literal, Self, cast
from urllib.parse import unquote, urlsplit

import yaml  # type: ignore[import-untyped]
from pydantic import Field, StringConstraints, field_validator, model_validator

from bionodulo.nodes.contract.artifacts import (
    ArtifactContainer,
    ArtifactId,
    ArtifactPort,
    Cardinality,
    _StrictFrozenModel,
)
from bionodulo.nodes.contract.environments import (
    EnvironmentSpec,
    ExactVersion,
    PixiEnvironment,
    Sha256Digest,
)
from bionodulo.nodes.contract.outputs import GlobCollector, OutputSpec
from bionodulo.nodes.contract.parameters import ParameterSpec, ValueKind

if TYPE_CHECKING:
    from bionodulo.nodes.contract.model import NodeSpec


CWL_REFERENCE_FACTORY = "bionodulo.nodes.cwl_reference_runtime:CwlReferenceNode"
CWL_REFERENCE_BACKEND: Literal["cwltool"] = "cwltool"
CWL_REFERENCE_PROFILE: Literal["native-reference"] = "native-reference"
_MAX_SOURCE_BYTES = 4 * 1024 * 1024
_MAX_ARRAY_OUTPUTS = 4096
_RESERVED_INPUT_IDS = frozenset({"context", "output_dir"})
_SAFE_REQUIRED = frozenset(
    {
        "InlineJavascriptRequirement",
        "InitialWorkDirRequirement",
        "EnvVarRequirement",
        "ShellCommandRequirement",
        "SoftwareRequirement",
    }
)
_UNFULFILLED_HINTS = frozenset(
    {
        "DockerRequirement",
        "ResourceRequirement",
        "NetworkAccess",
    }
)
_PORT_RE = re.compile(r"[^a-z0-9_.-]+")


class CwlReferenceImportError(ValueError):
    """A descriptor cannot be admitted to the native reference-engine profile."""


class CwlReferenceInputMapping(_StrictFrozenModel):
    cwl_id: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    port_id: ArtifactId
    kind: Literal["file", "directory", "string", "integer", "number", "boolean", "enum", "json"]
    array: bool = False
    nullable: bool = False


class CwlReferenceOutputMapping(_StrictFrozenModel):
    cwl_id: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    port_id: ArtifactId
    kind: Literal["file", "directory", "string", "integer", "number", "boolean"] = "file"
    array: bool = False
    nullable: bool = False


class CwlReferenceInspection(_StrictFrozenModel):
    cwl_version: Literal["v1.0", "v1.1", "v1.2"]
    artifact_inputs: tuple[ArtifactPort, ...] = ()
    parameters: tuple[ParameterSpec, ...] = ()
    outputs: tuple[OutputSpec, ...]
    input_mappings: tuple[CwlReferenceInputMapping, ...] = ()
    output_mappings: tuple[CwlReferenceOutputMapping, ...]
    docker_hint_present: bool = False
    unfulfilled_hints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_projection(self) -> Self:
        input_ports = tuple(item.port_id for item in self.input_mappings)
        output_ports = tuple(item.port_id for item in self.output_mappings)
        if len(input_ports) != len(set(input_ports)):
            raise ValueError("CWL input IDs collide after deterministic port normalization")
        if len(output_ports) != len(set(output_ports)):
            raise ValueError("CWL output IDs collide after deterministic port normalization")
        if self.unfulfilled_hints != tuple(sorted(set(self.unfulfilled_hints))):
            raise ValueError("unfulfilled CWL hints must be unique and canonically ordered")
        return self


class CwlReferenceContract(_StrictFrozenModel):
    source_uri: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    source_text: Annotated[str, StringConstraints(min_length=1)]
    source_content_sha256: Sha256Digest
    source_size_bytes: Annotated[int, Field(strict=True, ge=1, le=_MAX_SOURCE_BYTES)]
    cwl_version: Literal["v1.0", "v1.1", "v1.2"]
    backend: Literal["cwltool"] = CWL_REFERENCE_BACKEND
    profile: Literal["native-reference"] = CWL_REFERENCE_PROFILE
    engine_package: Literal["cwltool"] = CWL_REFERENCE_BACKEND
    engine_version: ExactVersion
    primary_package: ArtifactId
    biotools_accession: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    biotools_uri: Annotated[str, StringConstraints(min_length=1, max_length=2048)]
    input_mappings: tuple[CwlReferenceInputMapping, ...] = ()
    output_mappings: Annotated[tuple[CwlReferenceOutputMapping, ...], Field(min_length=1)]
    docker_hint_present: bool = False
    unfulfilled_hints: tuple[str, ...] = ()

    @field_validator("source_uri")
    @classmethod
    def _validate_source_uri(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "file"}:
            raise ValueError("CWL reference source URI must use https or file")
        if parsed.scheme == "https" and not parsed.hostname:
            raise ValueError("CWL reference https source URI requires a host")
        if parsed.scheme == "file" and not parsed.path.startswith("/"):
            raise ValueError("CWL reference file URI must be absolute")
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError("CWL reference source URI must not contain credentials or a fragment")
        return value

    @field_validator("biotools_accession")
    @classmethod
    def _validate_accession(cls, value: str) -> str:
        if value != value.strip() or not all(character.isprintable() for character in value):
            raise ValueError("bio.tools accession must be exact printable text")
        return value

    @field_validator("engine_version")
    @classmethod
    def _validate_engine_version(cls, value: str) -> str:
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)+(?:[A-Za-z0-9._+-]*)", value) is None:
            raise ValueError("CWL reference engine version must be an exact version")
        return value

    @field_validator("biotools_uri")
    @classmethod
    def _validate_biotools_uri(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.hostname not in {"bio.tools", "www.bio.tools"}:
            raise ValueError("bio.tools evidence URI must be an https URL on bio.tools")
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError("bio.tools evidence URI must not contain credentials or a fragment")
        return value

    @model_validator(mode="after")
    def _validate_retained_source(self) -> Self:
        try:
            content = self.source_text.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError("CWL reference source must be valid UTF-8") from error
        if b"\x00" in content:
            raise ValueError("CWL reference source must not contain NUL bytes")
        if len(content) != self.source_size_bytes:
            raise ValueError("CWL reference source byte count does not match retained text")
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        if digest != self.source_content_sha256:
            raise ValueError("CWL reference source digest does not match retained text")
        if self.input_mappings != tuple(sorted(self.input_mappings, key=lambda item: item.port_id)):
            raise ValueError("CWL reference input mappings must use canonical port order")
        if self.output_mappings != tuple(sorted(self.output_mappings, key=lambda item: item.port_id)):
            raise ValueError("CWL reference output mappings must use canonical port order")
        if self.unfulfilled_hints != tuple(sorted(set(self.unfulfilled_hints))):
            raise ValueError("unfulfilled CWL hints must be unique and canonically ordered")
        return self


class _UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[object, object]:
        self.flatten_mapping(node)
        mapping: dict[object, object] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in mapping:
                    raise yaml.constructor.ConstructorError(
                        "while parsing a CWL reference descriptor",
                        node.start_mark,
                        f"duplicate mapping key: {key!r}",
                        key_node.start_mark,
                    )
                mapping[key] = self.construct_object(value_node, deep=deep)
            except TypeError as error:
                raise yaml.constructor.ConstructorError(
                    "while parsing a CWL reference descriptor",
                    node.start_mark,
                    "mapping keys must be scalar",
                    key_node.start_mark,
                ) from error
        return mapping


def _mapping(value: object, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) or not key for key in value):
        raise CwlReferenceImportError(f"{label} must be an object with nonempty string keys")
    return value


def _short_id(value: str, *, label: str) -> str:
    short = value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    if not short or not all(character.isprintable() for character in short):
        raise CwlReferenceImportError(f"{label} has an invalid CWL identifier")
    return short


def _port_id(cwl_id: str, *, prefix: str) -> str:
    normalized = _PORT_RE.sub("_", cwl_id.lower()).strip("_.-")
    if not normalized or not normalized[0].isalpha():
        normalized = f"{prefix}_{normalized}" if normalized else prefix
    if len(normalized) > 128:
        suffix = hashlib.sha256(cwl_id.encode("utf-8")).hexdigest()[:12]
        normalized = f"{normalized[:115]}_{suffix}"
    return normalized


def _presentation_text(value: object, *, fallback: str, maximum: int) -> str:
    """Project bounded single-line UI prose without changing retained source."""

    selected = value if isinstance(value, str) else fallback
    printable = "".join(character if character.isprintable() else " " for character in selected)
    normalized = " ".join(printable.split()) or fallback
    if len(normalized) > maximum:
        normalized = normalized[: maximum - 3].rstrip() + "..."
    return normalized


def _source_display_name(source_uri: str, *, fallback: str) -> str:
    stem = PurePosixPath(unquote(urlsplit(source_uri).path)).stem
    words = " ".join(part for part in re.split(r"[_-]+", stem) if part)
    return words.title() if words else fallback


def _named_definitions(value: object, *, label: str) -> tuple[tuple[str, Mapping[str, Any]], ...]:
    items: list[tuple[str, Mapping[str, Any]]] = []
    if isinstance(value, Mapping):
        for raw_identifier, raw_definition in _mapping(value, label=label).items():
            definition = {"type": raw_definition} if not isinstance(raw_definition, Mapping) else raw_definition
            items.append(
                (
                    _short_id(raw_identifier, label=label),
                    _mapping(definition, label=f"{label} {raw_identifier!r}"),
                )
            )
    elif isinstance(value, list):
        for index, raw_definition in enumerate(value):
            definition = _mapping(raw_definition, label=f"{label}[{index}]")
            raw_list_identifier = definition.get("id")
            if not isinstance(raw_list_identifier, str):
                raise CwlReferenceImportError(f"{label}[{index}] requires a string id")
            items.append(
                (
                    _short_id(raw_list_identifier, label=f"{label}[{index}].id"),
                    {key: item for key, item in definition.items() if key != "id"},
                )
            )
    else:
        raise CwlReferenceImportError(f"{label} must be a mapping or list")
    identifiers = tuple(identifier for identifier, _ in items)
    if len(identifiers) != len(set(identifiers)):
        raise CwlReferenceImportError(f"{label} contains duplicate short identifiers")
    return tuple(items)


class _Schema:
    def __init__(
        self,
        *,
        kind: str,
        array: bool = False,
        nullable: bool = False,
        symbols: tuple[str, ...] = (),
    ) -> None:
        self.kind = kind
        self.array = array
        self.nullable = nullable
        self.symbols = symbols


def _schema(raw: object, *, label: str, preserve_artifact_union: bool = False) -> _Schema:
    nullable = False
    if isinstance(raw, list):
        non_null = [item for item in raw if item != "null"]
        nullable = len(non_null) != len(raw)
        if not non_null:
            raise CwlReferenceImportError(f"{label} supports only a nullable union with one concrete type")
        if len(non_null) == 1:
            raw = non_null[0]
        else:
            alternatives = tuple(_schema(item, label=f"{label} union member") for item in non_null)
            artifact_kinds = {item.kind for item in alternatives}
            if (
                len(artifact_kinds) == 1
                and artifact_kinds <= {"file", "directory"}
                and all(not item.nullable for item in alternatives)
                and any(item.array for item in alternatives)
            ):
                if preserve_artifact_union:
                    return _Schema(kind="json", nullable=nullable)
                return _Schema(kind=alternatives[0].kind, array=True, nullable=nullable)
            if all(isinstance(item, Mapping) and item.get("type") == "record" for item in non_null):
                return _Schema(kind="json", nullable=nullable)
            raise CwlReferenceImportError(
                f"{label} supports multi-type unions only for records or scalar/array forms "
                "of one artifact type"
            )
    if isinstance(raw, str):
        if raw.endswith("?"):
            nullable = True
            raw = raw[:-1]
        array = raw.endswith("[]")
        if array:
            raw = raw[:-2]
        kind = {
            "File": "file",
            "Directory": "directory",
            "stdout": "file",
            "stderr": "file",
            "string": "string",
            "int": "integer",
            "long": "integer",
            "float": "number",
            "double": "number",
            "boolean": "boolean",
        }.get(raw)
        if kind is None:
            raise CwlReferenceImportError(f"{label} uses unsupported CWL type {raw!r}")
        return _Schema(kind=kind, array=array, nullable=nullable)
    schema = _mapping(raw, label=label)
    schema_type = schema.get("type")
    if schema_type == "array":
        if "items" not in schema:
            raise CwlReferenceImportError(f"{label} array schema requires items")
        item = _schema(schema["items"], label=f"{label}.items")
        if item.array or item.nullable:
            raise CwlReferenceImportError(f"{label} nested or nullable array items are unsupported")
        return _Schema(kind=item.kind, array=True, nullable=nullable, symbols=item.symbols)
    if schema_type == "enum":
        symbols = schema.get("symbols")
        if not isinstance(symbols, list) or not symbols or any(not isinstance(item, str) for item in symbols):
            raise CwlReferenceImportError(f"{label} enum requires nonempty string symbols")
        if len(symbols) != len(set(symbols)):
            raise CwlReferenceImportError(f"{label} enum symbols must be unique")
        return _Schema(kind="enum", nullable=nullable, symbols=tuple(symbols))
    if schema_type == "record":
        fields = schema.get("fields")
        if not isinstance(fields, (Mapping, list)) or not fields:
            raise CwlReferenceImportError(f"{label} record requires nonempty fields")
        return _Schema(kind="json", nullable=nullable)
    raise CwlReferenceImportError(f"{label} uses an unsupported CWL schema object")


def _requirement_classes(value: object, *, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        return tuple(_mapping(value, label=label))
    if not isinstance(value, list):
        raise CwlReferenceImportError(f"{label} must be a mapping or list")
    classes: list[str] = []
    for index, item in enumerate(value):
        declaration = _mapping(item, label=f"{label}[{index}]")
        class_name = declaration.get("class")
        if not isinstance(class_name, str) or not class_name:
            raise CwlReferenceImportError(f"{label}[{index}] requires a class")
        classes.append(class_name)
    return tuple(classes)


def _reject_external_references(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in {"$import", "$include"} or (key == "$schemas" and path != "$"):
                raise CwlReferenceImportError(f"self-contained CWL profile rejects {key} at {path}")
            _reject_external_references(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_external_references(item, path=f"{path}[{index}]")


def _external_schema_hint(document: Mapping[str, Any]) -> bool:
    raw_schemas = document.get("$schemas")
    if raw_schemas is None:
        return False
    if not isinstance(raw_schemas, list) or not raw_schemas:
        raise CwlReferenceImportError("top-level $schemas must be a nonempty list of absolute HTTPS URLs")
    for index, value in enumerate(raw_schemas):
        if not isinstance(value, str):
            raise CwlReferenceImportError(f"top-level $schemas[{index}] must be an absolute HTTPS URL")
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise CwlReferenceImportError(f"top-level $schemas[{index}] must be an absolute HTTPS URL")
    return True


def inspect_reference_document(
    document: dict[str, Any], *, allow_container_requirement: bool = False
) -> CwlReferenceInspection:
    """Validate and project a reference-engine document without an environment."""

    if type(document) is not dict:
        raise CwlReferenceImportError("CWL reference document must be an object")
    _reject_external_references(document)
    version = document.get("cwlVersion")
    if version not in {"v1.0", "v1.1", "v1.2"}:
        raise CwlReferenceImportError("CWL reference document requires cwlVersion v1.0, v1.1, or v1.2")
    if document.get("class") != "CommandLineTool":
        raise CwlReferenceImportError("CWL reference profile supports CommandLineTool only")

    required = _requirement_classes(document.get("requirements"), label="CWL requirements")
    supported_required = _SAFE_REQUIRED | ({"DockerRequirement"} if allow_container_requirement else set())
    unsupported_required = sorted(set(required) - supported_required)
    if unsupported_required:
        raise CwlReferenceImportError(
            "native CWL reference backend cannot honor required feature(s): " + ", ".join(unsupported_required)
        )
    hints = _requirement_classes(document.get("hints"), label="CWL hints")
    unfulfilled = set(hints) & _UNFULFILLED_HINTS | (set(hints) - _SAFE_REQUIRED)
    if allow_container_requirement:
        unfulfilled.discard("DockerRequirement")
    if _external_schema_hint(document):
        unfulfilled.add("external_schema_not_loaded")
    unfulfilled_hints = tuple(sorted(unfulfilled))

    artifact_inputs: list[ArtifactPort] = []
    parameters: list[ParameterSpec] = []
    input_mappings: list[CwlReferenceInputMapping] = []
    for cwl_id, definition in _named_definitions(document.get("inputs", {}), label="CWL inputs"):
        if "type" not in definition:
            raise CwlReferenceImportError(f"CWL input {cwl_id!r} is missing type")
        parsed = _schema(
            definition["type"],
            label=f"CWL input {cwl_id!r}",
            preserve_artifact_union=True,
        )
        port_id = _port_id(cwl_id, prefix="input")
        if port_id in _RESERVED_INPUT_IDS:
            raise CwlReferenceImportError(f"CWL input {cwl_id!r} collides with reserved adapter input {port_id!r}")
        has_default = "default" in definition
        required_input = not parsed.nullable and not has_default
        if parsed.kind in {"file", "directory"}:
            if has_default:
                raise CwlReferenceImportError(f"CWL artifact input {cwl_id!r} defaults are unsupported")
            artifact_inputs.append(
                ArtifactPort(
                    port_id=port_id,
                    artifact_type=f"artifact.{parsed.kind}",
                    cardinality=(
                        Cardinality.MANY
                        if parsed.array
                        else Cardinality.ONE if required_input else Cardinality.OPTIONAL_ONE
                    ),
                )
            )
        else:
            kind = {
                "string": ValueKind.STRING,
                "integer": ValueKind.INTEGER,
                "number": ValueKind.NUMBER,
                "boolean": ValueKind.BOOLEAN,
                "enum": ValueKind.STRING,
                "json": ValueKind.JSON,
            }[parsed.kind]
            if parsed.array:
                kind = ValueKind.JSON
            description = definition.get("doc") or definition.get("label") or ""
            if not isinstance(description, str):
                description = ""
            parameters.append(
                ParameterSpec(
                    parameter_id=port_id,
                    kind=kind,
                    required=required_input,
                    has_default=has_default,
                    default=definition.get("default"),
                    choices=parsed.symbols if parsed.kind == "enum" and not parsed.array else None,
                    description=description,
                )
            )
        input_mappings.append(
            CwlReferenceInputMapping(
                cwl_id=cwl_id,
                port_id=port_id,
                kind=cast(
                    Literal["file", "directory", "string", "integer", "number", "boolean", "enum", "json"],
                    "json" if parsed.array and parsed.kind not in {"file", "directory"} else parsed.kind,
                ),
                array=parsed.array,
                nullable=parsed.nullable,
            )
        )

    outputs: list[OutputSpec] = []
    output_mappings: list[CwlReferenceOutputMapping] = []
    for cwl_id, definition in _named_definitions(document.get("outputs", {}), label="CWL outputs"):
        if "type" not in definition:
            raise CwlReferenceImportError(f"CWL output {cwl_id!r} is missing type")
        parsed = _schema(definition["type"], label=f"CWL output {cwl_id!r}")
        if parsed.kind not in {"file", "directory", "string", "integer", "number", "boolean"}:
            raise CwlReferenceImportError(f"CWL output {cwl_id!r} uses an unsupported output type")
        scalar = parsed.kind not in {"file", "directory"}
        port_id = _port_id(cwl_id, prefix="output")
        minimum = 0 if parsed.nullable or parsed.array else 1
        maximum = _MAX_ARRAY_OUTPUTS if parsed.array else 1
        outputs.append(
            OutputSpec(
                port_id=port_id,
                artifact_type="artifact.file" if scalar else f"artifact.{parsed.kind}",
                cardinality=(
                    Cardinality.MANY
                    if parsed.array
                    else Cardinality.OPTIONAL_ONE if parsed.nullable else Cardinality.ONE
                ),
                collector=GlobCollector(
                    pattern=f"published/{port_id}/*",
                    minimum=minimum,
                    maximum=maximum,
                    container=(
                        ArtifactContainer.DIRECTORY
                        if parsed.kind == "directory"
                        else ArtifactContainer.FILE
                    ),
                ),
                require_nonempty=False,
            )
        )
        output_mappings.append(
            CwlReferenceOutputMapping(
                cwl_id=cwl_id,
                port_id=port_id,
                kind=cast(Literal["file", "directory", "string", "integer", "number", "boolean"], parsed.kind),
                array=parsed.array,
                nullable=parsed.nullable,
            )
        )
    if not outputs:
        raise CwlReferenceImportError("CWL reference CommandLineTool must declare at least one output")

    try:
        return CwlReferenceInspection(
            cwl_version=version,
            artifact_inputs=tuple(sorted(artifact_inputs, key=lambda item: item.port_id)),
            parameters=tuple(sorted(parameters, key=lambda item: item.parameter_id)),
            outputs=tuple(sorted(outputs, key=lambda item: item.port_id)),
            input_mappings=tuple(sorted(input_mappings, key=lambda item: item.port_id)),
            output_mappings=tuple(sorted(output_mappings, key=lambda item: item.port_id)),
            docker_hint_present="DockerRequirement" in hints,
            unfulfilled_hints=unfulfilled_hints,
        )
    except ValueError as error:
        raise CwlReferenceImportError(f"invalid CWL reference projection: {error}") from error


def _parse_source(source_content: bytes | str) -> tuple[bytes, str, dict[str, Any]]:
    if isinstance(source_content, bytes):
        raw = source_content
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CwlReferenceImportError("CWL reference source must be UTF-8") from error
    elif isinstance(source_content, str):
        text = source_content
        try:
            raw = text.encode("utf-8")
        except UnicodeEncodeError as error:
            raise CwlReferenceImportError("CWL reference source must be UTF-8") from error
    else:
        raise CwlReferenceImportError("CWL reference source must be bytes or text")
    if not raw or len(raw) > _MAX_SOURCE_BYTES or b"\x00" in raw:
        raise CwlReferenceImportError(f"CWL reference source must be 1-{_MAX_SOURCE_BYTES} UTF-8 bytes without NUL")
    try:
        document = yaml.load(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as error:
        raise CwlReferenceImportError(f"invalid CWL reference YAML: {error}") from error
    if type(document) is not dict:
        raise CwlReferenceImportError("CWL reference source must parse to one object")
    return raw, text, document


def validate_cwl_reference_environment(
    environment: EnvironmentSpec,
    *,
    primary_package: str,
    primary_package_version: str,
) -> None:
    if not isinstance(environment, PixiEnvironment):
        raise CwlReferenceImportError("CWL reference execution requires a locked Pixi/Conda environment")
    if not environment.is_fully_locked:
        raise CwlReferenceImportError("CWL reference execution environment must be fully locked")
    requests = {request.name: request for request in environment.packages}
    if primary_package not in requests:
        raise CwlReferenceImportError(f"locked environment is missing required package {primary_package!r}")
    for lock in environment.locks:
        inventory = {artifact.name: artifact.version for artifact in lock.artifacts}
        if inventory.get(primary_package) != primary_package_version:
            raise CwlReferenceImportError(
                f"lock for {lock.platform.value} must resolve {primary_package!r} "
                f"exactly to {primary_package_version!r}"
            )


def import_cwl_reference(
    source_content: bytes | str,
    *,
    node_id: str,
    source_uri: str,
    biotools_accession: str,
    biotools_uri: str,
    environment: EnvironmentSpec,
    primary_package: str,
    primary_package_version: str,
    engine_version: str,
) -> NodeSpec:
    """Import one self-contained CommandLineTool for locked native cwltool execution."""

    from bionodulo.nodes.catalog.artifacts import ARTIFACT_REGISTRY
    from bionodulo.nodes.contract.model import (
        ExecutionKind,
        NodeIdentity,
        NodeOwnership,
        NodePresentation,
        NodeSpec,
        RuntimeBinding,
    )

    raw, source_text, document = _parse_source(source_content)
    inspection = inspect_reference_document(document)
    if not ARTIFACT_REGISTRY.is_type_compatible("artifact.file", "artifact.file"):
        raise CwlReferenceImportError("generic artifact.file type is not registered")
    validate_cwl_reference_environment(
        environment,
        primary_package=primary_package,
        primary_package_version=primary_package_version,
    )
    contract = CwlReferenceContract(
        source_uri=source_uri,
        source_text=source_text,
        source_content_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
        source_size_bytes=len(raw),
        cwl_version=inspection.cwl_version,
        engine_version=engine_version,
        primary_package=primary_package,
        biotools_accession=biotools_accession,
        biotools_uri=biotools_uri,
        input_mappings=inspection.input_mappings,
        output_mappings=inspection.output_mappings,
        docker_hint_present=inspection.docker_hint_present,
        unfulfilled_hints=inspection.unfulfilled_hints,
    )
    display_name = _presentation_text(
        document.get("label"),
        fallback=_source_display_name(source_uri, fallback=node_id.replace("_", " ").title()),
        maximum=256,
    )
    description = _presentation_text(
        document.get("doc"),
        fallback=f"Generated from bio.tools {biotools_accession}.",
        maximum=2048,
    )
    try:
        return NodeSpec(
            identity=NodeIdentity(
                stable_id=f"cwlref::{node_id}",
                machine_id=node_id,
                contract_version="2.0.0",
                implementation_version="1.0.0",
                tool_id=primary_package,
                tool_version=primary_package_version,
            ),
            presentation=NodePresentation(
                display_name=display_name,
                description=description,
                palette_path=("Generated", "bio.tools", "CWL"),
                domain_tags=("biotools", "cwl"),
                operation_kind="transform",
                owner=NodeOwnership.EXTERNAL_TOOL,
                tool_family=primary_package,
            ),
            artifact_inputs=inspection.artifact_inputs,
            parameters=inspection.parameters,
            outputs=inspection.outputs,
            environment=environment,
            execution_kind=ExecutionKind.ARGV,
            execution_factory=CWL_REFERENCE_FACTORY,
            runtime_binding=RuntimeBinding(
                tool_id=primary_package,
                tool_version=primary_package_version,
                execution_kind=ExecutionKind.ARGV,
                execution_factory=CWL_REFERENCE_FACTORY,
                package_name=primary_package,
            ),
            cwl_reference=contract,
        )
    except ValueError as error:
        raise CwlReferenceImportError(f"imported CWL reference contract is invalid: {error}") from error


__all__ = [
    "CWL_REFERENCE_BACKEND",
    "CWL_REFERENCE_FACTORY",
    "CWL_REFERENCE_PROFILE",
    "CwlReferenceContract",
    "CwlReferenceImportError",
    "CwlReferenceInputMapping",
    "CwlReferenceInspection",
    "CwlReferenceOutputMapping",
    "import_cwl_reference",
    "inspect_reference_document",
    "validate_cwl_reference_environment",
]
