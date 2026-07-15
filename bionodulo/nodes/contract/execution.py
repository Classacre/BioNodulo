"""Declarative execution plans with no runtime lowering or execution behavior."""

from __future__ import annotations

import hashlib
import json
import math
import re
from enum import StrEnum
from typing import Annotated, Literal, Self, TypeAlias
from urllib.parse import parse_qsl, urlsplit

from pydantic import Field, StringConstraints, field_validator, model_validator

from bionodulo.nodes.contract.artifacts import ArtifactId, _StrictFrozenModel
from bionodulo.nodes.contract.environments import ExecutionPlatform, Sha256Digest


_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
_GPU_TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_ENVIRONMENT_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")
_CALLABLE_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*:"
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$"
)
_TRUSTED_CALLABLE_PREFIX = "bionodulo.nodes.catalog."
_KEYWORD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_HEADER_NAME_RE = re.compile(r"^[a-z0-9!#$%&'*+.^_`|~-]{1,128}$")
_MEDIA_TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+-]{0,126}/[a-z0-9][a-z0-9!#$&^_.+-]{0,126}$")
_PROBE_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]*$")
_SECRET_NAME_TOKENS = frozenset(
    {
        "auth",
        "authorization",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "key",
        "keys",
        "password",
        "passwords",
        "secret",
        "secrets",
        "token",
        "tokens",
    }
)
_SECRET_NAME_PAIRS = frozenset(
    {
        ("access", "key"),
        ("api", "key"),
        ("client", "secret"),
        ("private", "key"),
    }
)
_SENSITIVE_HEADERS = frozenset(
    {
        "access-key",
        "api-key",
        "auth",
        "authorization",
        "client-secret",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "key",
        "keys",
        "password",
        "passwords",
        "private-key",
        "proxy-authorization",
        "secret",
        "secrets",
        "token",
        "tokens",
    }
)
_SECRET_QUERY_KEYS = frozenset(
    {
        "access_key",
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "client_secret",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "key",
        "keys",
        "password",
        "passwords",
        "private_key",
        "secret",
        "secrets",
        "sig",
        "signature",
        "token",
        "tokens",
    }
)


def _name_looks_secret(value: str) -> bool:
    tokens = tuple(token for token in re.split(r"[^a-z0-9]+", value.lower()) if token)
    if any(token in _SECRET_NAME_TOKENS for token in tokens):
        return True
    return any(pair in _SECRET_NAME_PAIRS for pair in zip(tokens, tokens[1:]))


def _canonical_digest(value: _StrictFrozenModel) -> str:
    payload = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _validate_unique_ordered_strings(values: tuple[str, ...], *, label: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be unique")
    if values != tuple(sorted(values)):
        raise ValueError(f"{label} must be canonically ordered")


def _validate_exact_float(value: object) -> object:
    if type(value) is not float:
        raise ValueError("value must be an exact float")
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    return value


def _validate_safe_relative_path(value: str) -> str:
    if not value or value.startswith("/") or "\\" in value or "\x00" in value:
        raise ValueError("path must be a safe relative POSIX path")
    segments = value.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise ValueError("path must be canonical and traversal-free")
    if any(any(ord(character) < 32 or ord(character) == 127 for character in segment) for segment in segments):
        raise ValueError("path must not contain control characters")
    return value


def _validate_arguments(value: tuple[str, ...]) -> tuple[str, ...]:
    if any("\x00" in argument for argument in value):
        raise ValueError("arguments must not contain NUL")
    if sum(len(argument.encode("utf-8")) for argument in value) > 65536:
        raise ValueError("arguments exceed the total byte bound")
    return value


StrictPositiveInt = Annotated[int, Field(strict=True, ge=1)]
Argument = Annotated[str, StringConstraints(max_length=4096)]
ExitCode = Annotated[int, Field(strict=True, ge=1, le=255)]
HttpStatus = Annotated[int, Field(strict=True, ge=400, le=599)]


class ResourceSpec(_StrictFrozenModel):
    cpus: Annotated[int, Field(strict=True, ge=1, le=256)]
    memory_gib: Annotated[float, Field(strict=True, gt=0.0, le=1048576.0, allow_inf_nan=False)]
    scratch_disk_gib: Annotated[
        float,
        Field(strict=True, gt=0.0, le=1048576.0, allow_inf_nan=False),
    ]
    wall_timeout_seconds: Annotated[int, Field(strict=True, ge=1, le=604800)]
    gpu_count: Annotated[int, Field(strict=True, ge=0, le=16)] = 0
    gpu_type: Annotated[str, StringConstraints(min_length=1, max_length=64)] | None = None
    allowed_platforms: Annotated[tuple[ExecutionPlatform, ...], Field(min_length=1, max_length=2)]

    @field_validator("memory_gib", "scratch_disk_gib", mode="before")
    @classmethod
    def _validate_float_fields(cls, value: object) -> object:
        return _validate_exact_float(value)

    @field_validator("gpu_type")
    @classmethod
    def _validate_gpu_type(cls, value: str | None) -> str | None:
        if value is not None and _GPU_TYPE_RE.fullmatch(value) is None:
            raise ValueError("GPU type must be canonical lowercase ASCII")
        return value

    @model_validator(mode="after")
    def _validate_resource_consistency(self) -> Self:
        platform_values = tuple(platform.value for platform in self.allowed_platforms)
        _validate_unique_ordered_strings(platform_values, label="allowed platforms")
        if (self.gpu_count == 0) != (self.gpu_type is None):
            raise ValueError("GPU type must be present exactly when GPU count is nonzero")
        return self


class HttpsEndpoint(_StrictFrozenModel):
    host: Annotated[str, StringConstraints(min_length=1, max_length=253)]
    port: Annotated[int, Field(strict=True, ge=1, le=65535)] = 443

    @field_validator("host")
    @classmethod
    def _validate_host(cls, value: str) -> str:
        if _HOST_RE.fullmatch(value) is None:
            raise ValueError("host must be a canonical DNS hostname without scheme or wildcard")
        return value


class NetworkMode(StrEnum):
    NONE = "none"
    HTTPS_ALLOWLIST = "https_allowlist"


class NetworkPolicy(_StrictFrozenModel):
    mode: NetworkMode = NetworkMode.NONE
    allowlist: Annotated[tuple[HttpsEndpoint, ...], Field(max_length=64)] = ()

    @model_validator(mode="after")
    def _validate_mode(self) -> Self:
        endpoint_keys = tuple(f"{endpoint.host}:{endpoint.port:05d}" for endpoint in self.allowlist)
        _validate_unique_ordered_strings(endpoint_keys, label="HTTPS allowlist endpoints")
        if self.mode is NetworkMode.NONE and self.allowlist:
            raise ValueError("network-none policy cannot have an allowlist")
        if self.mode is NetworkMode.HTTPS_ALLOWLIST and not self.allowlist:
            raise ValueError("HTTPS allowlist mode requires at least one endpoint")
        return self


class RetryPolicy(_StrictFrozenModel):
    attempts: Annotated[int, Field(strict=True, ge=1, le=10)] = 1
    initial_backoff_seconds: Annotated[
        float,
        Field(strict=True, ge=0.0, le=3600.0, allow_inf_nan=False),
    ] = 0.0
    maximum_backoff_seconds: Annotated[
        float,
        Field(strict=True, ge=0.0, le=3600.0, allow_inf_nan=False),
    ] = 0.0
    multiplier: Annotated[
        float,
        Field(strict=True, ge=1.0, le=10.0, allow_inf_nan=False),
    ] = 1.0
    jitter_seconds: Annotated[
        float,
        Field(strict=True, ge=0.0, le=3600.0, allow_inf_nan=False),
    ] = 0.0
    exit_codes: Annotated[tuple[ExitCode, ...], Field(max_length=255)] = ()
    http_statuses: Annotated[tuple[HttpStatus, ...], Field(max_length=200)] = ()

    @field_validator(
        "initial_backoff_seconds",
        "maximum_backoff_seconds",
        "multiplier",
        "jitter_seconds",
        mode="before",
    )
    @classmethod
    def _validate_float_fields(cls, value: object) -> object:
        return _validate_exact_float(value)

    @model_validator(mode="after")
    def _validate_retry_consistency(self) -> Self:
        _validate_unique_ordered_strings(
            tuple(f"{code:03d}" for code in self.exit_codes),
            label="retry exit codes",
        )
        _validate_unique_ordered_strings(
            tuple(str(status) for status in self.http_statuses),
            label="retry HTTP statuses",
        )
        if self.attempts == 1:
            if (
                self.exit_codes
                or self.http_statuses
                or self.initial_backoff_seconds != 0.0
                or self.maximum_backoff_seconds != 0.0
                or self.multiplier != 1.0
                or self.jitter_seconds != 0.0
            ):
                raise ValueError("one-attempt policy cannot declare retry conditions or delays")
            return self
        if not self.exit_codes and not self.http_statuses:
            raise ValueError("multi-attempt policy requires an explicit retry condition")
        if self.initial_backoff_seconds <= 0.0:
            raise ValueError("multi-attempt policy requires a positive initial backoff")
        if self.maximum_backoff_seconds < self.initial_backoff_seconds:
            raise ValueError("maximum backoff must not be below initial backoff")
        if self.jitter_seconds > self.maximum_backoff_seconds:
            raise ValueError("jitter must not exceed maximum backoff")
        return self


class CheckpointMode(StrEnum):
    DISABLED = "disabled"
    PROCESS_SIGNAL = "process_signal"


class CheckpointSignal(StrEnum):
    SIGTERM = "SIGTERM"
    SIGUSR1 = "SIGUSR1"
    SIGUSR2 = "SIGUSR2"


class CheckpointPolicy(_StrictFrozenModel):
    mode: CheckpointMode = CheckpointMode.DISABLED
    signal: CheckpointSignal | None = None
    grace_seconds: Annotated[int, Field(strict=True, ge=1, le=3600)] | None = None
    relative_path: Annotated[str, StringConstraints(min_length=1, max_length=1024)] | None = None

    @field_validator("relative_path")
    @classmethod
    def _validate_path(cls, value: str | None) -> str | None:
        if value is not None:
            return _validate_safe_relative_path(value)
        return None

    @model_validator(mode="after")
    def _validate_checkpoint_consistency(self) -> Self:
        fields = (self.signal, self.grace_seconds, self.relative_path)
        if self.mode is CheckpointMode.DISABLED and any(value is not None for value in fields):
            raise ValueError("disabled checkpoint policy cannot declare process fields")
        if self.mode is CheckpointMode.PROCESS_SIGNAL and any(value is None for value in fields):
            raise ValueError("process checkpoint policy requires signal, grace, and path")
        return self


EnvironmentVariableName = Annotated[str, StringConstraints(min_length=1, max_length=128)]


class LiteralEnvironmentVariable(_StrictFrozenModel):
    kind: Literal["literal"] = "literal"
    name: EnvironmentVariableName
    value: Annotated[str, StringConstraints(max_length=4096)]

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if _ENVIRONMENT_NAME_RE.fullmatch(value) is None:
            raise ValueError("environment variable name must be canonical uppercase ASCII")
        if _name_looks_secret(value):
            raise ValueError("secret-bearing environment variables require a secret reference")
        return value

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("environment variable value must not contain NUL")
        return value


class SecretEnvironmentVariable(_StrictFrozenModel):
    kind: Literal["secret"] = "secret"
    name: EnvironmentVariableName
    secret_id: ArtifactId

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if _ENVIRONMENT_NAME_RE.fullmatch(value) is None:
            raise ValueError("environment variable name must be canonical uppercase ASCII")
        return value


EnvironmentBinding: TypeAlias = Annotated[
    LiteralEnvironmentVariable | SecretEnvironmentVariable,
    Field(discriminator="kind"),
]


class _ExecutionPlanBase(_StrictFrozenModel):
    resources: ResourceSpec
    network: NetworkPolicy = Field(default_factory=NetworkPolicy)
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    checkpoint: CheckpointPolicy = Field(default_factory=CheckpointPolicy)
    environment: Annotated[tuple[EnvironmentBinding, ...], Field(max_length=256)] = ()

    @model_validator(mode="after")
    def _validate_environment(self) -> Self:
        _validate_unique_ordered_strings(
            tuple(binding.name for binding in self.environment),
            label="environment variable names",
        )
        return self

    def plan_digest(self) -> str:
        return _canonical_digest(self)

    def _require_process_retry(self) -> None:
        if self.retry.http_statuses:
            raise ValueError("process plans cannot retry HTTP statuses")


class ArgvPlan(_ExecutionPlanBase):
    kind: Literal["argv"] = "argv"
    executable: ArtifactId
    arguments: Annotated[tuple[Argument, ...], Field(max_length=256)] = ()

    @field_validator("arguments")
    @classmethod
    def _validate_argv(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_arguments(value)

    @model_validator(mode="after")
    def _validate_process_policy(self) -> Self:
        self._require_process_retry()
        return self

    def token_array(self) -> tuple[str, ...]:
        return (self.executable, *self.arguments)


class PipelineStage(_StrictFrozenModel):
    stage_id: ArtifactId
    executable: ArtifactId
    arguments: Annotated[tuple[Argument, ...], Field(max_length=256)] = ()

    @field_validator("arguments")
    @classmethod
    def _validate_argv(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_arguments(value)

    def token_array(self) -> tuple[str, ...]:
        return (self.executable, *self.arguments)


class PipelinePlan(_ExecutionPlanBase):
    kind: Literal["pipeline"] = "pipeline"
    stages: Annotated[tuple[PipelineStage, ...], Field(min_length=2, max_length=32)]

    @model_validator(mode="after")
    def _validate_pipeline(self) -> Self:
        stage_ids = tuple(stage.stage_id for stage in self.stages)
        if len(set(stage_ids)) != len(stage_ids):
            raise ValueError("pipeline stage IDs must be unique")
        self._require_process_retry()
        return self

    def token_arrays(self) -> tuple[tuple[str, ...], ...]:
        return tuple(stage.token_array() for stage in self.stages)


class ScriptPlan(_ExecutionPlanBase):
    kind: Literal["script"] = "script"
    interpreter: ArtifactId
    script: Annotated[str, StringConstraints(min_length=1, max_length=65536)]
    audit_reason: Annotated[str, StringConstraints(min_length=20, max_length=512)]
    arguments: Annotated[tuple[Argument, ...], Field(max_length=256)] = ()

    @field_validator("script")
    @classmethod
    def _validate_script(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("script must not contain NUL")
        if len(value.encode("utf-8")) > 65536:
            raise ValueError("script exceeds the byte bound")
        return value

    @field_validator("audit_reason")
    @classmethod
    def _validate_audit_reason(cls, value: str) -> str:
        if len(value.split()) < 5 or any(ord(character) < 32 for character in value):
            raise ValueError("audit reason must be a nontrivial single-line explanation")
        return value

    @field_validator("arguments")
    @classmethod
    def _validate_argv(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_arguments(value)

    @model_validator(mode="after")
    def _validate_process_policy(self) -> Self:
        self._require_process_retry()
        return self

    @property
    def script_sha256(self) -> str:
        return "sha256:" + hashlib.sha256(self.script.encode("utf-8")).hexdigest()


ScalarValue: TypeAlias = (
    Annotated[bool, Field(strict=True)]
    | Annotated[int, Field(strict=True)]
    | Annotated[float, Field(strict=True, allow_inf_nan=False)]
    | Annotated[str, StringConstraints(max_length=4096)]
    | None
)


def _validate_scalar(value: object) -> object:
    if type(value) is float and not math.isfinite(value):
        raise ValueError("scalar float must be finite")
    if type(value) is str and "\x00" in value:
        raise ValueError("scalar string must not contain NUL")
    return value


class PythonKeyword(_StrictFrozenModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    value: ScalarValue

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if _KEYWORD_RE.fullmatch(value) is None:
            raise ValueError("keyword name must be a Python identifier")
        return value

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: object) -> object:
        return _validate_scalar(value)


class PythonPlan(_ExecutionPlanBase):
    kind: Literal["python"] = "python"
    callable_ref: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    arguments: Annotated[tuple[ScalarValue, ...], Field(max_length=256)] = ()
    keywords: Annotated[tuple[PythonKeyword, ...], Field(max_length=256)] = ()

    @field_validator("callable_ref")
    @classmethod
    def _validate_callable(cls, value: str) -> str:
        if _CALLABLE_RE.fullmatch(value) is None:
            raise ValueError("callable reference must be an absolute module:symbol name")
        module, symbol = value.split(":", 1)
        components = (*module.split("."), *symbol.split("."))
        if not module.startswith(_TRUSTED_CALLABLE_PREFIX) or any(
            component.startswith("__") or component.endswith("__") for component in components
        ):
            raise ValueError("callable reference must use a trusted packaged catalog module and non-dunder symbol")
        return value

    @field_validator("arguments")
    @classmethod
    def _validate_arguments(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        for item in value:
            _validate_scalar(item)
        return value

    @model_validator(mode="after")
    def _validate_python_policy(self) -> Self:
        _validate_unique_ordered_strings(
            tuple(keyword.name for keyword in self.keywords),
            label="Python keyword names",
        )
        if self.retry.exit_codes or self.retry.http_statuses:
            raise ValueError("Python plans cannot retry exit codes or HTTP statuses")
        if self.checkpoint.mode is not CheckpointMode.DISABLED:
            raise ValueError("Python plans do not support process checkpoints")
        return self


class PackagedResource(_StrictFrozenModel):
    package_id: ArtifactId
    relative_path: Annotated[str, StringConstraints(min_length=1, max_length=1024)]

    @field_validator("relative_path")
    @classmethod
    def _validate_resource_path(cls, value: str) -> str:
        _validate_safe_relative_path(value)
        if "/" not in value or not value.endswith(".R"):
            raise ValueError("R resource must be a packaged relative .R path")
        return value


class RPlan(_ExecutionPlanBase):
    kind: Literal["r"] = "r"
    interpreter: ArtifactId
    resource: PackagedResource
    arguments: Annotated[tuple[Argument, ...], Field(max_length=256)] = ()

    @field_validator("arguments")
    @classmethod
    def _validate_argv(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_arguments(value)

    @model_validator(mode="after")
    def _validate_process_policy(self) -> Self:
        self._require_process_retry()
        return self


class HttpMethod(StrEnum):
    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


HeaderName = Annotated[str, StringConstraints(min_length=1, max_length=128)]


def _validate_header_name(value: str) -> str:
    if _HEADER_NAME_RE.fullmatch(value) is None:
        raise ValueError("header name must be canonical lowercase HTTP token syntax")
    return value


class LiteralHttpHeader(_StrictFrozenModel):
    kind: Literal["literal"] = "literal"
    name: HeaderName
    value: Annotated[str, StringConstraints(max_length=8192)]

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        value = _validate_header_name(value)
        if value in _SENSITIVE_HEADERS or _name_looks_secret(value):
            raise ValueError("sensitive HTTP headers require secret references")
        return value

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: str) -> str:
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("header value must not contain control characters")
        return value


class SecretHttpHeader(_StrictFrozenModel):
    kind: Literal["secret"] = "secret"
    name: HeaderName
    secret_id: ArtifactId

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _validate_header_name(value)


HttpHeader: TypeAlias = Annotated[
    LiteralHttpHeader | SecretHttpHeader,
    Field(discriminator="kind"),
]


class HttpBodyReference(_StrictFrozenModel):
    artifact_id: ArtifactId
    media_type: Annotated[str, StringConstraints(min_length=3, max_length=255)]
    sha256: Sha256Digest
    size_bytes: Annotated[int, Field(strict=True, ge=1, le=16 * 1024 * 1024)]

    @field_validator("media_type")
    @classmethod
    def _validate_media_type(cls, value: str) -> str:
        if _MEDIA_TYPE_RE.fullmatch(value) is None:
            raise ValueError("media type must be canonical lowercase type/subtype syntax")
        return value


class RateLimitPolicy(_StrictFrozenModel):
    max_requests: Annotated[int, Field(strict=True, ge=1, le=10000)]
    per_seconds: Annotated[
        float,
        Field(strict=True, gt=0.0, le=86400.0, allow_inf_nan=False),
    ]

    @field_validator("per_seconds", mode="before")
    @classmethod
    def _validate_period(cls, value: object) -> object:
        return _validate_exact_float(value)


def _validate_http_url(value: str) -> str:
    try:
        value.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("HTTP URL must use canonical ASCII spelling") from error
    if "%" in value or "\\" in value or any(ord(character) <= 32 or ord(character) == 127 for character in value):
        raise ValueError("HTTP URL must use canonical ASCII spelling without escapes")
    if not value.startswith("https://"):
        raise ValueError("HTTP URL must start with literal lowercase https://")
    if "#" in value:
        raise ValueError("HTTP URL must not contain a fragment delimiter")
    _, query_separator, raw_query = value.partition("?")
    if query_separator and (not raw_query or "?" in raw_query):
        raise ValueError("HTTP URL query delimiter must introduce one nonempty canonical query")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("HTTP URL is malformed") from error
    if parsed.scheme != "https" or not parsed.netloc or parsed.hostname is None:
        raise ValueError("HTTP plan URL must use HTTPS with an explicit hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("HTTP plan URL must not contain user information")
    raw_host = parsed.netloc.rsplit(":", 1)[0] if port is not None else parsed.netloc
    if raw_host != parsed.hostname or _HOST_RE.fullmatch(raw_host) is None:
        raise ValueError("HTTP plan URL hostname must be canonical lowercase DNS")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("HTTP plan URL port must be between 1 and 65535")
    if port == 443:
        raise ValueError("HTTP plan URL must omit the default HTTPS port")
    canonical_netloc = parsed.hostname
    if port is not None:
        raw_port = parsed.netloc.rsplit(":", 1)[1]
        if raw_port != str(port):
            raise ValueError("HTTP URL port must use canonical decimal spelling")
        canonical_netloc = f"{canonical_netloc}:{port}"
    if parsed.netloc != canonical_netloc:
        raise ValueError("HTTP URL netloc must use canonical spelling")
    if not parsed.path:
        raise ValueError("HTTP URL must declare an explicit canonical path; use / for root")
    segments = parsed.path.split("/")
    if "" in segments[1:-1] or any(segment in (".", "..") for segment in segments):
        raise ValueError("HTTP URL path must be canonical and traversal-free")
    try:
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as error:
        raise ValueError("HTTP query must contain exact key-value pairs") from error
    query_keys = tuple(key for key, _ in query_pairs)
    if "+" in parsed.query:
        raise ValueError("HTTP query must not use form-encoding aliases")
    if len(set(query_keys)) != len(query_keys):
        raise ValueError("HTTP query keys must be unique")
    if tuple(query_pairs) != tuple(sorted(query_pairs)):
        raise ValueError("HTTP query pairs must be canonically ordered")
    for key, item in query_pairs:
        normalized_key = key.lower().replace("-", "_")
        if normalized_key in _SECRET_QUERY_KEYS or _name_looks_secret(normalized_key):
            raise ValueError("HTTP query must not contain secret-bearing keys")
        if any(ord(character) < 32 or ord(character) == 127 for character in key + item):
            raise ValueError("HTTP query must not contain control characters")
    canonical_query = "&".join(f"{key}={item}" for key, item in query_pairs)
    canonical_url = f"https://{canonical_netloc}{parsed.path}"
    if canonical_query:
        canonical_url += f"?{canonical_query}"
    if value != canonical_url:
        raise ValueError("HTTP URL must use its single canonical raw spelling")
    return value


class HttpPlan(_ExecutionPlanBase):
    kind: Literal["http"] = "http"
    method: HttpMethod
    url: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    headers: Annotated[tuple[HttpHeader, ...], Field(max_length=128)] = ()
    body: HttpBodyReference | None = None
    response_validator: ArtifactId
    rate_limit: RateLimitPolicy

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        return _validate_http_url(value)

    @model_validator(mode="after")
    def _validate_http_plan(self) -> Self:
        _validate_unique_ordered_strings(
            tuple(header.name for header in self.headers),
            label="HTTP header names",
        )
        if self.method in (HttpMethod.GET, HttpMethod.HEAD) and self.body is not None:
            raise ValueError("GET and HEAD plans cannot declare a request body")
        if self.retry.exit_codes:
            raise ValueError("HTTP plans cannot retry process exit codes")
        if self.checkpoint.mode is not CheckpointMode.DISABLED:
            raise ValueError("HTTP plans do not support process checkpoints")
        parsed = urlsplit(self.url)
        endpoint = (
            parsed.hostname,
            parsed.port if parsed.port is not None else 443,
        )
        allowed = {(item.host, item.port) for item in self.network.allowlist}
        if self.network.mode is not NetworkMode.HTTPS_ALLOWLIST or endpoint not in allowed:
            raise ValueError("HTTP plan network policy must allow the exact URL host and port")
        return self


class ContainerPlan(_ExecutionPlanBase):
    kind: Literal["container"] = "container"
    environment_id: ArtifactId
    entrypoint: Annotated[tuple[Argument, ...], Field(min_length=1, max_length=64)]
    arguments: Annotated[tuple[Argument, ...], Field(max_length=256)] = ()

    @field_validator("entrypoint", "arguments")
    @classmethod
    def _validate_tokens(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_arguments(value)

    @model_validator(mode="after")
    def _validate_container_plan(self) -> Self:
        if _PROBE_ID_RE.fullmatch(self.entrypoint[0]) is None:
            raise ValueError("container entrypoint must begin with an executable probe ID")
        self._require_process_retry()
        return self

    def token_arrays(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return self.entrypoint, self.arguments


ExecutionPlan: TypeAlias = Annotated[
    ArgvPlan | PipelinePlan | ScriptPlan | PythonPlan | RPlan | HttpPlan | ContainerPlan,
    Field(discriminator="kind"),
]
