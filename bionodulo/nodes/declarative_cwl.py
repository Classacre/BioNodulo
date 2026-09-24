"""Shared native runtime for the supported declarative CWL profile.

The module deliberately contains no tool identities or command-specific
branches.  A validated :class:`NodeSpec` supplies every port, argument, output,
runtime, and provenance binding used by the dynamically bound node class.
"""

from __future__ import annotations

import abc
import hashlib
import json
import math
import os
import platform
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any, ClassVar, Mapping, Sequence

from bionodulo.execution.subprocess_runner import run_subprocess
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.contract.artifacts import Cardinality
from bionodulo.nodes.contract.environments import ExecutableProbe, ExecutionPlatform
from bionodulo.nodes.contract.model import ExecutionKind, NodeSpec
from bionodulo.nodes.contract.outputs import (
    ExactCollector,
    GlobCollector,
    OutputSpec,
    StdoutCollector,
    collect_outputs,
)
from bionodulo.nodes.contract.parameters import ParameterSpec


DECLARATIVE_CWL_FACTORY = "bionodulo.nodes.declarative_cwl:DeclarativeCwlNode"
SUPPORTED_CWL_PROFILE = "cwl-v1.2-native-command-line-tool-v1"
DEFAULT_COMMAND_TIMEOUT_SECONDS = 3_600.0
PROBE_TIMEOUT_SECONDS = 30.0

_MISSING = object()
_VALUE_WIDGET_TYPES = {
    "string": "STRING",
    "integer": "INT",
    "number": "FLOAT",
    "boolean": "BOOLEAN",
}
_PROCESS_KINDS = {
    ExecutionKind.ARGV,
    ExecutionKind.PIPELINE,
    ExecutionKind.SCRIPT,
}


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _invocation_dump(spec: NodeSpec) -> dict[str, object]:
    invocation = spec.cwl_invocation
    if invocation is None:
        raise ValueError("declarative CWL execution requires NodeSpec.cwl_invocation")
    return invocation.model_dump(mode="json", round_trip=True)


def _source_digests(spec: NodeSpec) -> tuple[str, ...]:
    invocation = spec.cwl_invocation
    digests = set() if spec.evidence is None else {source.content_sha256 for source in spec.evidence.sources}
    if invocation is not None and invocation.source_content_sha256 is not None:
        digests.add(invocation.source_content_sha256)
    return tuple(sorted(digests))


def _artifact_widget_type(type_id: str) -> str:
    if type_id == "artifact.file":
        return "FILE"
    if type_id == "artifact.directory":
        return "DIRECTORY"
    if type_id == "file.text":
        return "TXT"
    normalized = type_id.strip().upper().replace("-", "_").replace(".", "_")
    return normalized or "FILE"


def _value_widget(kind: object) -> str:
    try:
        return _VALUE_WIDGET_TYPES[_enum_value(kind)]
    except KeyError as error:
        raise ValueError(f"unsupported declarative CWL value kind: {_enum_value(kind)!r}") from error


def _parameter_options(parameter: ParameterSpec) -> dict[str, object]:
    options: dict[str, object] = {}
    if parameter.description:
        options["description"] = parameter.description
    if parameter.has_default:
        options["default"] = parameter.default
    if parameter.choices is not None:
        options["options"] = list(parameter.choices)
    if parameter.minimum is not None:
        options["min"] = parameter.minimum
    if parameter.maximum is not None:
        options["max"] = parameter.maximum
    return options


def _input_types(spec: NodeSpec) -> dict[str, dict[str, Any]]:
    required: dict[str, Any] = {}
    optional: dict[str, Any] = {}
    for artifact_port in spec.artifact_inputs:
        artifact_entry: tuple[str, dict[str, object]] = (_artifact_widget_type(artifact_port.artifact_type), {})
        target = required if artifact_port.cardinality is Cardinality.ONE else optional
        target[artifact_port.port_id] = artifact_entry
    for value_port in spec.value_inputs:
        value_entry: tuple[str, dict[str, object]] = (
            _value_widget(value_port.kind),
            {"description": value_port.description} if value_port.description else {},
        )
        (required if value_port.required else optional)[value_port.port_id] = value_entry
    for parameter in spec.parameters:
        entry = (_value_widget(parameter.kind), _parameter_options(parameter))
        (required if parameter.required else optional)[parameter.parameter_id] = entry
    return {"required": required, "optional": optional, "hidden": {}}


def _probe_for(spec: NodeSpec) -> ExecutableProbe:
    environment = spec.environment
    invocation = spec.cwl_invocation
    if environment is None or invocation is None:
        raise ValueError("declarative CWL execution requires a locked environment and invocation")
    probes = tuple(environment.executable_probes)
    binding = spec.runtime_binding
    if binding is not None and binding.probe_id is not None:
        selected = next((probe for probe in probes if probe.probe_id == binding.probe_id), None)
        if selected is None:
            raise ValueError(f"runtime executable probe {binding.probe_id!r} is missing")
        return selected

    executable_name = Path(invocation.base_command[0]).name
    candidates = tuple(
        probe
        for probe in probes
        if Path(probe.locator).name == executable_name
        and probe.expected_version == spec.identity.tool_version
    )
    if len(candidates) != 1:
        raise ValueError(
            "declarative CWL native execution requires exactly one locked executable probe "
            f"for {executable_name!r}"
        )
    return candidates[0]


def _environment_digest(spec: NodeSpec) -> str:
    environment = spec.environment
    if environment is None:
        raise ValueError("declarative CWL execution requires a locked environment")
    return environment.environment_digest()


def _execution_timeout(context: object | None) -> float:
    try:
        value = getattr(getattr(getattr(context, "executor"), "settings"), "execution").timeout_seconds
        timeout = float(value)
    except (AttributeError, TypeError, ValueError):
        return DEFAULT_COMMAND_TIMEOUT_SECONDS
    if not math.isfinite(timeout) or timeout <= 0:
        return DEFAULT_COMMAND_TIMEOUT_SECONDS
    return timeout


def _host_execution_platform() -> ExecutionPlatform:
    if os.name == "nt" or platform.system().lower() != "linux":
        raise RuntimeError(
            "the native declarative CWL profile currently supports locked Linux environments only"
        )
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return ExecutionPlatform.LINUX_AMD64
    if machine in {"aarch64", "arm64"}:
        return ExecutionPlatform.LINUX_ARM64
    raise RuntimeError(f"unsupported native declarative CWL Linux architecture: {machine or 'unknown'}")


def _assert_supported_host(spec: NodeSpec) -> None:
    selected = _host_execution_platform()
    environment = spec.environment
    if environment is None or selected not in environment.platforms:
        raise RuntimeError(
            f"the locked declarative CWL environment does not support host platform {selected.value}"
        )


def _configured_environment_roots() -> dict[str, Path]:
    raw = os.environ.get("BIONODULO_CWL_ENVIRONMENTS", "")
    if not raw:
        return {}
    if len(raw.encode("utf-8")) > 65_536:
        raise RuntimeError("BIONODULO_CWL_ENVIRONMENTS exceeds 65536 UTF-8 bytes")
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        selected: dict[str, object] = {}
        for key, value in pairs:
            if key in selected:
                raise ValueError(f"duplicate environment ID: {key}")
            selected[key] = value
        return selected

    try:
        document = json.loads(raw, object_pairs_hook=unique_object)
    except (json.JSONDecodeError, UnicodeError, ValueError) as error:
        raise RuntimeError(f"BIONODULO_CWL_ENVIRONMENTS must be a JSON object: {error}") from error
    if type(document) is not dict:
        raise RuntimeError("BIONODULO_CWL_ENVIRONMENTS must be a JSON object")
    roots: dict[str, Path] = {}
    for environment_id, raw_path in document.items():
        if type(environment_id) is not str or type(raw_path) is not str:
            raise RuntimeError("BIONODULO_CWL_ENVIRONMENTS must map string IDs to absolute paths")
        path = Path(raw_path)
        if not path.is_absolute():
            raise RuntimeError(f"configured CWL environment root must be absolute: {raw_path!r}")
        roots[environment_id] = path
    return roots


def _environment_root(spec: NodeSpec) -> Path:
    environment = spec.environment
    if environment is None:
        raise RuntimeError("declarative CWL environment is absent")
    configured = _configured_environment_roots()
    raw_root = configured.get(environment.environment_id)
    if raw_root is None:
        raise RuntimeError(
            "locked CWL environment is not realized; configure its absolute prefix in "
            f"BIONODULO_CWL_ENVIRONMENTS under {environment.environment_id!r}"
        )
    try:
        root = raw_root.resolve(strict=True)
    except OSError as error:
        raise RuntimeError(
            f"configured CWL environment root does not exist: {raw_root}"
        ) from error
    if not root.is_dir():
        raise RuntimeError(f"configured CWL environment root is not a directory: {root}")
    return root


def _locked_executable(spec: NodeSpec, probe: ExecutableProbe | None = None) -> Path:
    selected = probe or _probe_for(spec)
    root = _environment_root(spec)
    candidate = root.joinpath(*selected.locator.split("/"))
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise RuntimeError(f"locked executable is absent from the configured environment: {candidate}") from error
    if os.path.commonpath((str(root), str(resolved))) != str(root):
        raise RuntimeError(f"locked executable locator escapes its configured environment: {selected.locator}")
    if not resolved.is_file():
        raise RuntimeError(f"locked executable is not a regular file: {resolved}")
    if not os.access(resolved, os.X_OK):
        raise RuntimeError(f"locked executable is not executable: {resolved}")
    invocation = spec.cwl_invocation
    if invocation is None or Path(invocation.base_command[0]).name != Path(selected.locator).name:
        raise RuntimeError("CWL baseCommand executable does not match the locked executable probe locator")
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _fresh_binary_digest(spec: NodeSpec) -> str:
    try:
        return _sha256_file(_locked_executable(spec))
    except (OSError, RuntimeError, ValueError) as error:
        return f"unverified:{type(error).__name__}:{error}"


def _validate_bound_spec(spec: NodeSpec) -> NodeSpec:
    validated = NodeSpec.model_validate(spec)
    invocation = validated.cwl_invocation
    if invocation is None:
        raise ValueError("bind_cwl_node requires a descriptor-backed NodeSpec")
    if validated.execution_factory != DECLARATIVE_CWL_FACTORY:
        raise ValueError(
            f"declarative CWL NodeSpec execution_factory must be {DECLARATIVE_CWL_FACTORY!r}"
        )
    if validated.execution_kind not in _PROCESS_KINDS:
        raise ValueError("declarative CWL native execution requires an argv-compatible execution kind")
    if not validated.outputs:
        raise ValueError("declarative CWL native execution requires at least one declared output")
    stdout_count = 0
    for output in validated.outputs:
        collector = output.collector
        if isinstance(collector, StdoutCollector):
            stdout_count += 1
        elif isinstance(collector, ExactCollector):
            pass
        elif isinstance(collector, GlobCollector):
            if collector.container.value != "file" or collector.maximum != 1:
                raise ValueError("the native CWL profile supports only single-file output globs")
        else:
            raise ValueError(
                "the native CWL profile supports exact files, single-file globs, and stdout outputs only"
            )
        if output.cardinality not in (Cardinality.ONE, Cardinality.OPTIONAL_ONE):
            raise ValueError("the native CWL profile supports only scalar file outputs")
    if stdout_count > 1:
        raise ValueError("the native CWL profile supports at most one stdout output")

    declarations = {
        **{port.port_id: "file" for port in validated.artifact_inputs},
        **{port.port_id: _enum_value(port.kind) for port in validated.value_inputs},
        **{parameter.parameter_id: _enum_value(parameter.kind) for parameter in validated.parameters},
    }
    bindings = {binding.input_id: _enum_value(binding.kind) for binding in invocation.input_bindings}
    extra = sorted(set(bindings) - set(declarations))
    mismatched = sorted(
        input_id
        for input_id in set(bindings) & set(declarations)
        if bindings[input_id] != declarations[input_id]
    )
    if extra or mismatched:
        details = ([f"unknown bindings: {', '.join(extra)}"] if extra else []) + (
            [f"kind mismatches: {', '.join(mismatched)}"] if mismatched else []
        )
        raise ValueError("CWL invocation/input contract mismatch (" + "; ".join(details) + ")")
    probe = _probe_for(validated)
    if probe.fingerprint is None:
        raise ValueError("native declarative CWL execution requires an exact executable fingerprint")
    _environment_digest(validated)
    return validated


def _coerce_file(value: object, input_id: str) -> str:
    if isinstance(value, Mapping):
        raw = value.get("path", value.get("location"))
    else:
        raw = value
    if not isinstance(raw, (str, os.PathLike)):
        raise ValueError(f"CWL File input {input_id!r} must be a path or File object")
    text = os.fspath(raw)
    if text.startswith("file://"):
        text = text[7:]
    path = Path(text).expanduser().absolute()
    if not path.is_file():
        raise ValueError(f"CWL File input {input_id!r} is not an existing regular file: {path}")
    return str(path)


def _coerce_scalar(value: object, kind: str, input_id: str) -> str | bool:
    if kind == "file":
        return _coerce_file(value, input_id)
    if kind == "string":
        if type(value) is not str:
            raise ValueError(f"CWL string input {input_id!r} must be an exact string")
        return value
    if kind == "integer":
        if type(value) is not int:
            raise ValueError(f"CWL integer input {input_id!r} must be an exact integer")
        return str(value)
    if kind == "number":
        if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)):
            raise ValueError(f"CWL number input {input_id!r} must be a finite exact number")
        return str(value)
    if kind == "boolean":
        if type(value) is not bool:
            raise ValueError(f"CWL boolean input {input_id!r} must be an exact boolean")
        return value
    raise ValueError(f"unsupported CWL input kind for {input_id!r}: {kind!r}")


def _render_argv(spec: NodeSpec, inputs: Mapping[str, object]) -> list[str]:
    invocation = spec.cwl_invocation
    if invocation is None:  # Defensive for trusted-only model construction.
        raise ValueError("CWL invocation is absent")
    positioned: list[tuple[int, list[str]]] = [
        (argument.position, [argument.value]) for argument in invocation.literal_arguments
    ]
    for binding in invocation.input_bindings:
        value = inputs.get(binding.input_id, _MISSING)
        if value is _MISSING or value is None:
            if binding.has_default:
                value = binding.default
            elif binding.required:
                raise ValueError(f"required CWL input {binding.input_id!r} is missing")
            else:
                continue
        if value is None:
            continue
        kind = _enum_value(binding.kind)
        rendered = _coerce_scalar(value, kind, binding.input_id)
        tokens: list[str]
        if kind == "boolean":
            # CWL CommandLineBinding treats a boolean as a flag: true emits its
            # prefix and false emits nothing. With no prefix neither value adds
            # an argv token.
            tokens = [binding.prefix] if rendered is True and binding.prefix is not None else []
        else:
            text = str(rendered).lower() if kind == "boolean" else str(rendered)
            tokens = ([binding.prefix] if binding.prefix is not None else []) + [text]
        positioned.append((binding.position, tokens))
    positioned.sort(key=lambda item: item[0])
    return [*invocation.base_command, *(token for _position, tokens in positioned for token in tokens)]


def _validate_output_root(path: Path) -> Path:
    root = path.expanduser().absolute()
    existing = root
    while not existing.exists():
        if existing.parent == existing:
            break
        existing = existing.parent
    cursor = existing
    while cursor.parent != cursor:
        if stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"CWL output root has a symlink ancestor: {cursor}")
        cursor = cursor.parent
    root.mkdir(parents=True, exist_ok=True)
    cursor = root
    while cursor.parent != cursor:
        mode = os.lstat(cursor).st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"CWL output root has a symlink ancestor: {cursor}")
        cursor = cursor.parent
    if not root.is_dir():
        raise ValueError(f"CWL output root is not a directory: {root}")
    return root


def _stdout_spec(specs: Sequence[OutputSpec]) -> tuple[OutputSpec, StdoutCollector] | None:
    for output in specs:
        if isinstance(output.collector, StdoutCollector):
            return output, output.collector
    return None


def _safe_output_path(root: Path, relative_path: str) -> Path:
    candidate = root.joinpath(*relative_path.split("/"))
    if os.path.commonpath((str(root), str(candidate.absolute()))) != str(root):
        raise ValueError(f"declared CWL output escapes its output root: {relative_path}")
    return candidate


def _ensure_stdout_parent(root: Path, relative_path: str) -> None:
    parent = _safe_output_path(root, relative_path).parent
    parent.mkdir(parents=True, exist_ok=True)
    cursor = parent
    while cursor != root:
        if stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"CWL stdout parent contains a symlink: {cursor}")
        cursor = cursor.parent


def _stage_file_inputs(
    spec: NodeSpec,
    inputs: Mapping[str, object],
    staging_root: Path,
) -> tuple[dict[str, object], tuple[dict[str, str], ...]]:
    invocation = spec.cwl_invocation
    assert invocation is not None
    staged = dict(inputs)
    receipts: list[dict[str, str]] = []
    for binding in invocation.input_bindings:
        if _enum_value(binding.kind) != "file":
            continue
        value = inputs.get(binding.input_id, _MISSING)
        if value is _MISSING or value is None:
            continue
        source = Path(_coerce_file(value, binding.input_id))
        source_digest = _sha256_file(source)
        # Include the input ID and digest in the private name to avoid basename
        # collisions while retaining the original suffix for tools that inspect
        # extensions.  copy2 never hardlinks the user's source artifact.
        input_directory = staging_root / binding.input_id
        input_directory.mkdir(mode=0o700)
        destination = input_directory / source.name
        shutil.copy2(source, destination, follow_symlinks=True)
        destination.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        if _sha256_file(destination) != source_digest:
            raise RuntimeError(f"staged CWL File input changed while copying: {binding.input_id}")
        staged[binding.input_id] = str(destination)
        receipts.append(
            {
                "input_id": binding.input_id,
                "source_path": str(source),
                "source_sha256": source_digest,
                "staged_name": f"{binding.input_id}/{destination.name}",
            }
        )
    return staged, tuple(receipts)


def _result_values(specs: Sequence[OutputSpec], root: Path, collected: object) -> tuple[object, ...]:
    values: list[object] = []
    for output in specs:
        selected = collected[output.port_id]  # type: ignore[index]
        if selected is None:
            values.append(None)
        elif isinstance(selected, tuple):
            values.append([str(_safe_output_path(root, item.relative_path)) for item in selected])
        else:
            values.append(str(_safe_output_path(root, selected.relative_path)))
    return tuple(values)


class DeclarativeCwlNode(BaseNode, abc.ABC):
    """Base implementation dynamically bound to one immutable ``NodeSpec``."""

    CONTRACT_SPEC: ClassVar[NodeSpec]
    CONTRACT_DIGEST: ClassVar[str] = ""
    DESCRIPTOR_DIGEST: ClassVar[str] = ""
    INVOCATION_DIGEST: ClassVar[str] = ""
    SOURCE_DIGESTS: ClassVar[tuple[str, ...]] = ()
    SOURCE_URI: ClassVar[str] = ""
    CWL_PROFILE: ClassVar[str] = SUPPORTED_CWL_PROFILE
    RUNTIME_ASSURANCE: ClassVar[str] = (
        "Native Linux argv execution in a configured environment prefix. The selected "
        "executable version and mandatory binary fingerprint are checked every run, and "
        "File inputs are isolated copies. The declared package lock and its digest are "
        "retained but the prefix's complete dependency inventory is not re-attested at "
        "runtime. This profile does not provide an operating-system sandbox."
    )
    EXPERIMENTAL = True
    # The current executor does not include IS_CHANGED in its cache key.  Until
    # that general cache contract changes, every descriptor-backed invocation
    # must re-run its executable probe and output collection.
    EXECUTOR_CACHE_POLICY = "always_run"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return _input_types(cls.CONTRACT_SPEC)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        try:
            for port in cls.CONTRACT_SPEC.artifact_inputs:
                value = inputs.get(port.port_id, _MISSING)
                if value is _MISSING or value is None:
                    if port.cardinality is Cardinality.ONE:
                        raise ValueError(f"required CWL input {port.port_id!r} is missing")
                    continue
                _coerce_file(value, port.port_id)
            for parameter in cls.CONTRACT_SPEC.parameters:
                value = inputs.get(parameter.parameter_id, _MISSING)
                if value is _MISSING or value is None:
                    if parameter.required:
                        raise ValueError(f"required CWL input {parameter.parameter_id!r} is missing")
                    continue
                parameter.model_copy(
                    update={
                        "required": False,
                        "has_default": True,
                        "default": value,
                    }
                )
            _render_argv(cls.CONTRACT_SPEC, inputs)
        except (OSError, TypeError, ValueError) as error:
            return str(error)
        return True

    @classmethod
    def IS_CHANGED(cls, inputs: dict[str, Any]) -> str:
        payload = {
            "contract_digest": cls.CONTRACT_DIGEST,
            "descriptor_digest": cls.DESCRIPTOR_DIGEST,
            "invocation_digest": cls.INVOCATION_DIGEST,
            "environment_digest": _environment_digest(cls.CONTRACT_SPEC),
            "environment_verification": "declaration_retained_executable_verified",
            "assurance": cls.RUNTIME_ASSURANCE,
            "source_digests": cls.SOURCE_DIGESTS,
            "binary_digest": _fresh_binary_digest(cls.CONTRACT_SPEC),
            "inputs": json.loads(cls._serialize_inputs(inputs)),
        }
        return _canonical_digest(payload)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        metadata = super().metadata()
        invocation = cls.CONTRACT_SPEC.cwl_invocation
        assert invocation is not None
        metadata["runtime_descriptor"] = {
            "profile": cls.CWL_PROFILE,
            "contract_digest": cls.CONTRACT_DIGEST,
            "descriptor_digest": cls.DESCRIPTOR_DIGEST,
            "invocation_digest": cls.INVOCATION_DIGEST,
            "source_uri": cls.SOURCE_URI,
            "source_digests": list(cls.SOURCE_DIGESTS),
            "source_content_sha256": invocation.source_content_sha256,
            "source_size_bytes": invocation.source_size_bytes,
            "environment_digest": _environment_digest(cls.CONTRACT_SPEC),
        }
        return metadata

    async def _run_command(
        self,
        command: list[str],
        *,
        context: object | None,
        cwd: Path,
        stdout_path: Path,
        stderr_path: Path,
        stdout_binary: bool = False,
        stdout_max_bytes: int | None = None,
        timeout: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        if context is not None and hasattr(context, "run_command"):
            result = await context.run_command(  # type: ignore[union-attr]
                command,
                cwd=cwd,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                stdout_binary=stdout_binary,
                stdout_max_bytes=stdout_max_bytes,
                timeout=timeout,
            )
        else:
            result = await run_subprocess(
                command,
                cwd=cwd,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                node_id=self.NODE_ID,
                stdout_binary=stdout_binary,
                stdout_max_bytes=stdout_max_bytes,
                timeout=timeout,
            )
        if int(result.get("returncode", 0)) != 0:
            raise RuntimeError(
                f"CWL command failed with exit {result.get('returncode')}: "
                f"{str(result.get('stderr', ''))[-500:]}"
            )
        return result

    async def _verify_executable(
        self,
        *,
        context: object | None,
        root: Path,
        stream_dir: Path,
    ) -> dict[str, object]:
        spec = self.CONTRACT_SPEC
        invocation = spec.cwl_invocation
        assert invocation is not None
        probe = _probe_for(spec)
        local_path = _locked_executable(spec, probe)
        executable = str(local_path)
        actual_digest = _sha256_file(local_path)
        if probe.fingerprint is not None:
            if actual_digest != probe.fingerprint:
                raise RuntimeError(
                    f"executable fingerprint mismatch for {executable!r}: expected {probe.fingerprint}, "
                    f"got {actual_digest}"
                )
        result = await self._run_command(
            [executable, *probe.version_arguments],
            context=context,
            cwd=root,
            stdout_path=stream_dir / "probe.stdout.log",
            stderr_path=stream_dir / "probe.stderr.log",
            timeout=PROBE_TIMEOUT_SECONDS,
        )
        combined = "\n".join((str(result.get("stdout", "")), str(result.get("stderr", ""))))
        matched = False
        for line in combined.splitlines():
            if not line.startswith(probe.version_line_prefix):
                continue
            remainder = line[len(probe.version_line_prefix) :].strip()
            if remainder and remainder.split(maxsplit=1)[0] == probe.expected_version:
                matched = True
                break
        if not matched:
            raise RuntimeError(
                f"executable probe {probe.probe_id!r} did not report locked version "
                f"{probe.expected_version!r} after prefix {probe.version_line_prefix!r}"
            )
        return {
            "probe_id": probe.probe_id,
            "expected_version": probe.expected_version,
            "binary_sha256": actual_digest,
            "binary_fingerprint_declared": probe.fingerprint is not None,
            "binary_fingerprint_verified": probe.fingerprint is not None,
        }

    async def run(self, **kwargs: Any) -> tuple[object, ...]:
        context = kwargs.pop("context", None)
        explicit_output_dir = kwargs.pop("output_dir", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        _assert_supported_host(self.CONTRACT_SPEC)

        root_value = explicit_output_dir
        if root_value is None and context is not None:
            root_value = getattr(context, "node_dir", None)
        base_root = _validate_output_root(Path(root_value or "."))
        root = _validate_output_root(Path(tempfile.mkdtemp(prefix=".cwl-attempt-", dir=base_root)))
        invocation = self.CONTRACT_SPEC.cwl_invocation
        assert invocation is not None
        stdout_binding = _stdout_spec(self.CONTRACT_SPEC.outputs)
        if stdout_binding is not None:
            _ensure_stdout_parent(root, stdout_binding[1].relative_path)

        stream_dir = _validate_output_root(
            Path(tempfile.mkdtemp(prefix=f".{base_root.name}.cwl-logs-", dir=base_root.parent))
        )
        try:
            with tempfile.TemporaryDirectory(prefix=".cwl-inputs-", dir=base_root) as temporary:
                staging_root = Path(temporary)
                staged_inputs, input_receipts = _stage_file_inputs(
                    self.CONTRACT_SPEC,
                    kwargs,
                    staging_root,
                )
                probe_record = await self._verify_executable(
                    context=context,
                    root=root,
                    stream_dir=stream_dir,
                )
                capture_path = stream_dir / "command.stdout"
                command = _render_argv(self.CONTRACT_SPEC, staged_inputs)
                command_executable = _locked_executable(self.CONTRACT_SPEC)
                if _sha256_file(command_executable) != probe_record["binary_sha256"]:
                    raise RuntimeError("locked executable changed after its version probe")
                command[0] = str(command_executable)
                await self._run_command(
                    command,
                    context=context,
                    cwd=root,
                    stdout_path=capture_path,
                    stderr_path=stream_dir / "command.stderr.log",
                    stdout_binary=stdout_binding is not None,
                    stdout_max_bytes=(None if stdout_binding is None else stdout_binding[1].maximum_bytes),
                    timeout=_execution_timeout(context),
                )
                stdout: bytes | None = None
                stdout_truncated: bool | None = None
                if stdout_binding is not None:
                    output, collector = stdout_binding
                    if not capture_path.is_file():
                        raise RuntimeError(f"stdout output {output.port_id!r} was not captured")
                    stdout_size = capture_path.stat().st_size
                    if stdout_size > collector.maximum_bytes:
                        raise RuntimeError(
                            f"stdout output {output.port_id!r} exceeds its {collector.maximum_bytes}-byte limit"
                        )
                    stdout = capture_path.read_bytes()
                    stdout_truncated = False
                collected = collect_outputs(
                    self.CONTRACT_SPEC.outputs,
                    root,
                    stdout=stdout,
                    stdout_truncated=stdout_truncated,
                    conditions=kwargs,
                )
        except BaseException:
            # The directory was created by this invocation under the validated
            # node root. Removing it prevents failed-attempt files from becoming
            # artifacts or being accepted by a later retry.
            if root.parent != base_root or not root.name.startswith(".cwl-attempt-") or root.is_symlink():
                raise RuntimeError("refusing to clean an invalid CWL attempt workspace")
            shutil.rmtree(root)
            raise

        if context is not None:
            run_metadata = getattr(context, "run_metadata", None)
            if isinstance(run_metadata, dict):
                records = run_metadata.setdefault("declarative_cwl", {})
                if isinstance(records, dict):
                    records[str(getattr(context, "node_id", self.NODE_ID))] = {
                        "profile": self.CWL_PROFILE,
                        "source_uri": self.SOURCE_URI,
                        "source_digests": list(self.SOURCE_DIGESTS),
                        "source_content_sha256": invocation.source_content_sha256,
                        "source_size_bytes": invocation.source_size_bytes,
                        "contract_digest": self.CONTRACT_DIGEST,
                        "descriptor_digest": self.DESCRIPTOR_DIGEST,
                        "invocation_digest": self.INVOCATION_DIGEST,
                        "environment_digest": _environment_digest(self.CONTRACT_SPEC),
                        "environment_verification": "declaration_retained_executable_verified",
                        "attempt_workspace": root.name,
                        "input_staging": list(input_receipts),
                        **probe_record,
                    }
        return _result_values(self.CONTRACT_SPEC.outputs, root, collected)


def bind_cwl_node(spec: NodeSpec) -> type[BaseNode]:
    """Bind one validated CWL ``NodeSpec`` to the shared native runtime class."""

    validated = _validate_bound_spec(spec)
    invocation = validated.cwl_invocation
    assert invocation is not None
    environment = validated.environment
    assert environment is not None
    package_names = [package.name for package in getattr(environment, "packages", ())]
    display_category = "/".join(validated.presentation.palette_path)
    implementation_version = validated.identity.implementation_version
    version_base, separator, version_build = implementation_version.partition("+")
    version_build_prefix = f"{version_build}." if separator else ""
    attributes: dict[str, object] = {
        "__module__": __name__,
        "CONTRACT_SPEC": validated,
        "NODE_ID": validated.identity.machine_id,
        "DISPLAY_NAME": validated.presentation.display_name,
        "CATEGORY": display_category,
        "DESCRIPTION": validated.presentation.description,
        "RETURN_TYPES": tuple(_artifact_widget_type(output.artifact_type) for output in validated.outputs),
        "RETURN_NAMES": tuple(output.port_id for output in validated.outputs),
        "REQUIRES_EXTERNAL_TOOLS": True,
        "REQUIRED_EXECUTABLES": [],
        # The descriptor's lock is realized separately and selected only via
        # trusted server configuration.  Feeding these packages back into the
        # legacy solver would create a second, unrelated environment.
        "REQUIRED_CONDA_PACKAGES": [],
        "ENVIRONMENT": {
            "type": "declarative_cwl",
            "name": environment.environment_id,
            "digest": environment.environment_digest(),
            "packages": package_names,
        },
        "VERSION": f"{version_base}+{version_build_prefix}cwl.{invocation.descriptor_sha256[7:19]}",
        "EXPERIMENTAL": True,
        "EXECUTOR_CACHE_POLICY": "always_run",
        "CONTRACT_DIGEST": validated.contract_digest(),
        "DESCRIPTOR_DIGEST": invocation.descriptor_sha256,
        "INVOCATION_DIGEST": _canonical_digest(_invocation_dump(validated)),
        "SOURCE_DIGESTS": _source_digests(validated),
        "SOURCE_URI": invocation.source_uri,
        "DOCUMENTATION_URL": invocation.source_uri if invocation.source_uri.startswith("https://") else "",
    }
    class_name = "DeclarativeCwlNode_" + validated.identity.machine_id
    return type(class_name, (DeclarativeCwlNode,), attributes)


__all__ = [
    "DECLARATIVE_CWL_FACTORY",
    "DEFAULT_COMMAND_TIMEOUT_SECONDS",
    "PROBE_TIMEOUT_SECONDS",
    "SUPPORTED_CWL_PROFILE",
    "DeclarativeCwlNode",
    "bind_cwl_node",
]
