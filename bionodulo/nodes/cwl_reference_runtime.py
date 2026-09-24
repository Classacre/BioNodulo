"""Shared runtime for retained CWL documents executed by the reference engine."""

from __future__ import annotations

import abc
import hashlib
import json
import math
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import unquote, urlsplit

import yaml  # type: ignore[import-untyped]

from bionodulo.execution.subprocess_runner import run_subprocess
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.contract.artifacts import Cardinality
from bionodulo.nodes.contract.cwl_reference import (
    CWL_REFERENCE_FACTORY,
    CwlReferenceContract,
    CwlReferenceInputMapping,
    CwlReferenceOutputMapping,
)
from bionodulo.nodes.contract.environments import PixiEnvironment
from bionodulo.nodes.contract.model import ExecutionKind, NodeSpec
from bionodulo.nodes.contract.outputs import collect_outputs
from bionodulo.nodes.declarative_cwl import (
    PROBE_TIMEOUT_SECONDS,
    _artifact_widget_type,
    _canonical_digest,
    _configured_environment_roots,
    _execution_timeout,
    _host_execution_platform,
    _result_values,
    _safe_output_path,
    _sha256_file,
    _validate_output_root,
    _value_widget,
)
from bionodulo.nodes.generation.environments import CondaPrefixReceipt, verify_conda_prefix


REFERENCE_RESULT_MAX_BYTES = 16 * 1024 * 1024
REFERENCE_DIRECTORY_MAX_ENTRIES = 100_000
REFERENCE_DIRECTORY_MAX_DEPTH = 64
_MISSING = object()


def _reference(spec: NodeSpec) -> Any:
    reference = spec.cwl_reference or spec.cwl_oci
    if reference is None:
        raise ValueError("CWL runtime requires a reference or OCI contract")
    return reference


def _validate_bound_spec(spec: NodeSpec) -> NodeSpec:
    validated = NodeSpec.model_validate(spec)
    reference = _reference(validated)
    if validated.execution_factory != CWL_REFERENCE_FACTORY:
        raise ValueError(f"CWL reference execution_factory must be {CWL_REFERENCE_FACTORY!r}")
    if validated.execution_kind is not ExecutionKind.ARGV:
        raise ValueError("CWL reference runtime requires argv execution")
    if not isinstance(validated.environment, PixiEnvironment):
        raise ValueError("CWL reference runtime requires a fully locked Pixi environment")
    if not validated.environment.is_fully_locked:
        raise ValueError("CWL reference runtime environment is not fully locked")
    if reference.backend != "cwltool" or reference.profile != "native-reference":
        raise ValueError("unsupported CWL reference backend or profile")
    if any(mapping.kind == "file" and mapping.array for mapping in reference.input_mappings):
        ports = {port.port_id: port for port in validated.artifact_inputs}
        for mapping in reference.input_mappings:
            if mapping.kind == "file" and mapping.array and ports[mapping.port_id].cardinality is not Cardinality.MANY:
                raise ValueError("CWL File array mapping requires many input cardinality")
    return validated


def _input_types(spec: NodeSpec) -> dict[str, dict[str, Any]]:
    reference = _reference(spec)
    mappings = {mapping.port_id: mapping for mapping in reference.input_mappings}
    declared_formats = _declared_input_formats(reference)
    required: dict[str, Any] = {}
    optional: dict[str, Any] = {}
    for port in spec.artifact_inputs:
        options: dict[str, object] = {}
        mapping = mappings[port.port_id]
        if mapping.array:
            options["multiple"] = True
        formats = declared_formats.get(mapping.cwl_id, ())
        if formats:
            rendered = ", ".join(formats)
            options["cwl_formats"] = list(formats)
            options["description"] = (
                f"The retained CWL descriptor requires an explicitly declared File format ({rendered}). "
                "Connect CWL File Input and declare a compatible URI; this declaration does not prove contents."
            )
        entry = (_artifact_widget_type(port.artifact_type), options)
        (optional if mapping.nullable else required)[port.port_id] = entry
    for parameter in spec.parameters:
        parameter_mapping = mappings.get(parameter.parameter_id)
        if parameter_mapping is None:
            raise ValueError(f"CWL reference parameter {parameter.parameter_id!r} has no input mapping")
        parameter_options: dict[str, object] = {}
        if parameter.description:
            parameter_options["description"] = parameter.description
        if parameter.has_default:
            parameter_options["default"] = (
                _json_value(parameter.default)
                if parameter_mapping.kind == "json"
                else parameter.default
            )
        if parameter.choices is not None:
            parameter_options["options"] = list(parameter.choices)
        if parameter_mapping.kind == "json":
            # The editor's JSON widget preserves arrays as structured values;
            # API callers may also submit JSON text, which is parsed below.
            parameter_options["multiline"] = True
            entry = ("JSON", parameter_options)
        else:
            # Enum parameters remain STRING values with explicit options; the
            # frontend renders that established shape as a select control.
            entry = (_value_widget(parameter.kind), parameter_options)
        (required if parameter.required else optional)[parameter.parameter_id] = entry
    return {"required": required, "optional": optional, "hidden": {}}


def _declared_input_formats(reference: CwlReferenceContract) -> dict[str, tuple[str, ...]]:
    """Expose exact retained CWL File format declarations as editor guidance."""

    try:
        document = yaml.safe_load(reference.source_text)
    except yaml.YAMLError:
        return {}
    if not isinstance(document, Mapping):
        return {}
    raw_inputs = document.get("inputs", {})
    if isinstance(raw_inputs, Mapping):
        entries: list[tuple[object, object]] = list(raw_inputs.items())
    elif isinstance(raw_inputs, list):
        entries = [
            (entry.get("id"), entry)
            for entry in raw_inputs
            if isinstance(entry, Mapping)
        ]
    else:
        return {}
    selected: dict[str, tuple[str, ...]] = {}
    for raw_id, schema in entries:
        if not isinstance(raw_id, str) or not isinstance(schema, Mapping) or "format" not in schema:
            continue
        raw_formats = schema["format"]
        values = raw_formats if isinstance(raw_formats, list) else [raw_formats]
        formats = tuple(value for value in values if isinstance(value, str) and value)
        if formats:
            selected[_short_cwl_id(raw_id)] = formats
    return selected


def _configured_prefix(spec: NodeSpec) -> Path:
    environment = spec.environment
    if not isinstance(environment, PixiEnvironment):
        raise ValueError("CWL reference runtime requires a Pixi environment")
    configured = _configured_environment_roots().get(environment.environment_id)
    if configured is None:
        raise RuntimeError(
            "locked CWL reference environment is not realized; configure its absolute prefix in "
            f"BIONODULO_CWL_ENVIRONMENTS under {environment.environment_id!r}"
        )
    try:
        root = configured.resolve(strict=True)
    except OSError as error:
        raise RuntimeError(f"configured CWL reference prefix does not exist: {configured}") from error
    if not root.is_dir():
        raise RuntimeError(f"configured CWL reference prefix is not a directory: {root}")
    return root


def _engine_path() -> Path:
    raw = os.environ.get("BIONODULO_CWLTOOL", "")
    if not raw:
        raise RuntimeError("BIONODULO_CWLTOOL must name the absolute pinned cwltool executable")
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink():
        raise RuntimeError("BIONODULO_CWLTOOL must be an absolute non-symlink path")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise RuntimeError(f"configured cwltool executable does not exist: {path}") from error
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise RuntimeError(f"configured cwltool is not an executable regular file: {resolved}")
    return resolved


def _expected_digest(variable: str) -> str | None:
    value = os.environ.get(variable)
    if value is None or value == "":
        return None
    if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
        raise RuntimeError(f"{variable} must be a lowercase sha256 digest")
    return value


def _descriptor_document(reference: CwlReferenceContract) -> dict[str, object]:
    value = yaml.safe_load(reference.source_text)
    if type(value) is not dict:
        raise RuntimeError("retained CWL reference source is not an object")
    return value


def _primary_executable(reference: CwlReferenceContract, prefix: Path) -> Path:
    base_command = _descriptor_document(reference).get("baseCommand")
    if isinstance(base_command, str):
        executable_name = base_command
    elif isinstance(base_command, list) and base_command and isinstance(base_command[0], str):
        executable_name = base_command[0]
    else:
        raise RuntimeError("CWL reference descriptor requires a literal primary baseCommand")
    if "/" in executable_name or "\\" in executable_name or executable_name in ("", ".", ".."):
        raise RuntimeError("CWL reference primary baseCommand must be a prefix-local executable name")
    candidate = prefix / "bin" / executable_name
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise RuntimeError(
            f"primary baseCommand {executable_name!r} is absent from the locked tool prefix"
        ) from error
    if os.path.commonpath((str(prefix), str(resolved))) != str(prefix):
        raise RuntimeError("primary baseCommand escapes the locked tool prefix")
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise RuntimeError(f"primary baseCommand is not executable: {resolved}")
    return resolved


def _declares_feature(reference: CwlReferenceContract, feature: str) -> bool:
    document = _descriptor_document(reference)
    for section_name in ("requirements", "hints"):
        section = document.get(section_name)
        if isinstance(section, Mapping) and feature in section:
            return True
        if isinstance(section, list) and any(
            isinstance(item, Mapping) and item.get("class") == feature for item in section
        ):
            return True
    return False


def _nodejs_path(reference: CwlReferenceContract) -> Path | None:
    if not _declares_feature(reference, "InlineJavascriptRequirement"):
        return None
    raw = os.environ.get("BIONODULO_CWL_NODEJS", "")
    if not raw:
        raise RuntimeError(
            "InlineJavascriptRequirement requires an absolute BIONODULO_CWL_NODEJS runtime"
        )
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink():
        raise RuntimeError("BIONODULO_CWL_NODEJS must be an absolute non-symlink path")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise RuntimeError(f"configured CWL Node.js executable does not exist: {path}") from error
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise RuntimeError(f"configured CWL Node.js is not an executable regular file: {resolved}")
    return resolved


def _shell_path(reference: CwlReferenceContract) -> Path | None:
    if not _declares_feature(reference, "ShellCommandRequirement"):
        return None
    if os.name == "nt":
        raise RuntimeError("ShellCommandRequirement requires native Linux /bin/sh")
    configured = Path("/bin/sh")
    try:
        resolved = configured.resolve(strict=True)
    except OSError as error:
        raise RuntimeError("ShellCommandRequirement requires native Linux /bin/sh") from error
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise RuntimeError("ShellCommandRequirement requires an executable /bin/sh")
    return resolved


def _version_matches(output: str, expected: str) -> bool:
    return expected in re.findall(r"(?<![0-9A-Za-z._+-])[0-9]+(?:\.[0-9]+)+(?:[A-Za-z0-9._+-]*)", output)


async def _run_process(
    command: list[str],
    *,
    cwd: Path,
    context: object | None,
    env: dict[str, str] | None = None,
    replace_env: bool = False,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
    stdout_binary: bool = False,
    stdout_max_bytes: int | None = None,
    timeout: float,
) -> dict[str, Any]:
    emit = getattr(context, "emit", None)
    cancel_event = getattr(context, "cancel_event", None)
    return await run_subprocess(
        command,
        cwd=cwd,
        env=env,
        replace_env=replace_env,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        emit=emit if callable(emit) else None,
        node_id=str(getattr(context, "node_id", "cwl-reference")),
        timeout=timeout,
        cancel_event=cancel_event,
        stdout_binary=stdout_binary,
        stdout_max_bytes=stdout_max_bytes,
    )


async def verify_reference_runtime(
    spec: NodeSpec,
    *,
    context: object | None = None,
    log_dir: Path | None = None,
    workspace_dir: str | Path | None = None,
) -> dict[str, object]:
    """Verify the complete Conda inventory and the configured reference engine."""
    validated = _validate_bound_spec(spec)
    environment = validated.environment
    assert isinstance(environment, PixiEnvironment)
    selected = _host_execution_platform()
    prefix = _configured_prefix(validated)
    receipt: CondaPrefixReceipt = verify_conda_prefix(
        environment,
        prefix,
        platform_id=selected,
    )
    engine = _engine_path()
    actual_engine_sha256 = _sha256_file(engine)
    expected_engine_sha256 = _expected_digest("BIONODULO_CWLTOOL_SHA256")
    if expected_engine_sha256 is not None and actual_engine_sha256 != expected_engine_sha256:
        raise RuntimeError(
            f"configured cwltool hash mismatch: expected {expected_engine_sha256}, "
            f"got {actual_engine_sha256}"
        )
    reference = _reference(validated)
    primary = _primary_executable(reference, prefix)
    primary_sha256 = _sha256_file(primary)
    nodejs = _nodejs_path(reference)
    nodejs_sha256 = None if nodejs is None else _sha256_file(nodejs)
    expected_nodejs_sha256 = _expected_digest("BIONODULO_CWL_NODEJS_SHA256")
    if (
        nodejs_sha256 is not None
        and expected_nodejs_sha256 is not None
        and nodejs_sha256 != expected_nodejs_sha256
    ):
        raise RuntimeError(
            f"configured CWL Node.js hash mismatch: expected {expected_nodejs_sha256}, got {nodejs_sha256}"
        )
    shell = _shell_path(reference)
    shell_sha256 = None if shell is None else _sha256_file(shell)
    expected_shell_sha256 = _expected_digest("BIONODULO_CWL_SHELL_SHA256")
    if shell_sha256 is not None and expected_shell_sha256 is not None and shell_sha256 != expected_shell_sha256:
        raise RuntimeError(
            f"configured CWL /bin/sh hash mismatch: expected {expected_shell_sha256}, got {shell_sha256}"
        )
    if workspace_dir is not None:
        workspace = _validate_output_root(Path(workspace_dir))
        with tempfile.TemporaryDirectory(prefix=".cwl-reference-readiness-", dir=workspace):
            pass
    owned_log_dir = log_dir is None
    if owned_log_dir:
        log_dir = Path(tempfile.mkdtemp(prefix=".cwl-reference-probe-"))
    assert log_dir is not None
    try:
        result = await _run_process(
            [str(engine), "--version"],
            cwd=log_dir,
            context=context,
            stdout_path=log_dir / "engine-version.stdout.log",
            stderr_path=log_dir / "engine-version.stderr.log",
            timeout=PROBE_TIMEOUT_SECONDS,
        )
        combined = "\n".join((str(result.get("stdout", "")), str(result.get("stderr", ""))))
        if not _version_matches(combined, reference.engine_version):
            raise RuntimeError(
                f"configured cwltool did not report pinned engine version {reference.engine_version!r}"
            )
        nodejs_version = None
        if nodejs is not None:
            node_result = await _run_process(
                [str(nodejs), "--version"],
                cwd=log_dir,
                context=context,
                stdout_path=log_dir / "nodejs-version.stdout.log",
                stderr_path=log_dir / "nodejs-version.stderr.log",
                timeout=PROBE_TIMEOUT_SECONDS,
            )
            nodejs_version = "\n".join(
                (str(node_result.get("stdout", "")), str(node_result.get("stderr", "")))
            ).strip()
            if re.search(r"v?[0-9]+(?:\.[0-9]+)+", nodejs_version) is None:
                raise RuntimeError("configured CWL Node.js did not report a parseable version")
        return {
            "engine_path": str(engine),
            "engine_version": reference.engine_version,
            "engine_sha256": actual_engine_sha256,
            "engine_sha256_expected": expected_engine_sha256,
            "engine_hash_verified": expected_engine_sha256 is not None,
            "engine_dependency_inventory_scope": "version_and_entrypoint_hash_only",
            "primary_executable": str(primary),
            "primary_executable_sha256": primary_sha256,
            "nodejs_path": None if nodejs is None else str(nodejs),
            "nodejs_version": nodejs_version,
            "nodejs_sha256": nodejs_sha256,
            "nodejs_sha256_expected": expected_nodejs_sha256,
            "nodejs_hash_verified": nodejs is not None and expected_nodejs_sha256 is not None,
            "shell_path": None if shell is None else str(shell),
            "shell_sha256": shell_sha256,
            "shell_sha256_expected": expected_shell_sha256,
            "shell_hash_verified": shell is not None and expected_shell_sha256 is not None,
            "environment_id": environment.environment_id,
            "environment_digest": receipt.environment_digest,
            "environment_lock_digest": receipt.lock_digest,
            "environment_metadata_sha256": receipt.conda_metadata_sha256,
            "environment_installed_inventory_sha256": receipt.installed_inventory_sha256,
            "environment_verified_file_hashes": receipt.verified_file_hashes,
            "environment_unhashed_paths": receipt.unhashed_paths,
            "environment_prefix": str(prefix),
        }
    finally:
        if owned_log_dir:
            shutil.rmtree(log_dir)


def _coerce_file(value: object, *, port_id: str) -> Path:
    if isinstance(value, Mapping):
        raw = value.get("path", value.get("location"))
    else:
        raw = value
    if not isinstance(raw, (str, os.PathLike)):
        raise ValueError(f"CWL File input {port_id!r} must be a path or File object")
    text = os.fspath(raw)
    if text.startswith("file://"):
        parsed = urlsplit(text)
        if parsed.netloc not in ("", "localhost"):
            raise ValueError(f"CWL File input {port_id!r} has a nonlocal file URI")
        text = unquote(parsed.path)
    elif "://" in text:
        raise ValueError(f"CWL File input {port_id!r} must use a local file location")
    path = Path(text).expanduser().absolute()
    if not path.is_file():
        raise ValueError(f"CWL File input {port_id!r} is not an existing regular file: {path}")
    return path


def _coerce_directory(value: object, *, port_id: str) -> Path:
    if isinstance(value, Mapping):
        raw = value.get("path", value.get("location"))
    else:
        raw = value
    if not isinstance(raw, (str, os.PathLike)):
        raise ValueError(f"CWL Directory input {port_id!r} must be a path or Directory object")
    text = os.fspath(raw)
    if text.startswith("file://"):
        parsed = urlsplit(text)
        if parsed.netloc not in ("", "localhost"):
            raise ValueError(f"CWL Directory input {port_id!r} has a nonlocal file URI")
        text = unquote(parsed.path)
    elif "://" in text:
        raise ValueError(f"CWL Directory input {port_id!r} must use a local file location")
    path = Path(text).expanduser().absolute()
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"CWL Directory input {port_id!r} is not a non-symlink directory: {path}")
    return path


def _directory_inventory(root: Path, *, label: str) -> tuple[tuple[dict[str, object], ...], str]:
    entries: list[dict[str, object]] = []

    def visit(directory: Path, relative: Path, depth: int) -> None:
        if depth > REFERENCE_DIRECTORY_MAX_DEPTH:
            raise ValueError(f"{label} exceeds the maximum directory depth")
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as error:
            raise ValueError(f"{label} cannot be read safely") from error
        for child in children:
            if len(entries) >= REFERENCE_DIRECTORY_MAX_ENTRIES:
                raise ValueError(f"{label} exceeds the maximum directory entry count")
            child_relative = relative / child.name
            try:
                mode = child.stat(follow_symlinks=False).st_mode
            except OSError as error:
                raise ValueError(f"{label} changed while being inspected") from error
            if stat.S_ISLNK(mode):
                raise ValueError(f"{label} contains a symbolic link: {child_relative.as_posix()}")
            if stat.S_ISDIR(mode):
                entries.append({"path": child_relative.as_posix(), "type": "directory"})
                visit(Path(child.path), child_relative, depth + 1)
            elif stat.S_ISREG(mode):
                path = Path(child.path)
                entries.append(
                    {
                        "path": child_relative.as_posix(),
                        "type": "file",
                        "size": path.stat().st_size,
                        "sha256": _sha256_file(path),
                    }
                )
            else:
                raise ValueError(f"{label} contains an unsupported filesystem object")

    visit(root, Path(), 0)
    inventory = tuple(entries)
    return inventory, _canonical_digest(inventory)


def _file_format(value: object, *, port_id: str) -> str | None:
    if not isinstance(value, Mapping) or "format" not in value:
        return None
    selected = value["format"]
    if (
        type(selected) is not str
        or not 1 <= len(selected.encode("utf-8")) <= 2048
        or any(character.isspace() or not character.isprintable() for character in selected)
        or not urlsplit(selected).scheme
    ):
        raise ValueError(f"CWL File input {port_id!r} format must be one absolute printable URI")
    return selected


def _json_value(value: object) -> object:
    return json.loads(json.dumps(value, allow_nan=False, default=list))


def _parameter_value(mapping: CwlReferenceInputMapping, value: object) -> object:
    if mapping.kind != "json":
        return _json_value(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"CWL JSON array input {mapping.port_id!r} is not valid JSON: {error.msg}"
            ) from error
    else:
        parsed = _json_value(value)
    if mapping.array and not isinstance(parsed, list):
        raise ValueError(f"CWL JSON array input {mapping.port_id!r} must contain a JSON array")
    return parsed


def _short_cwl_id(value: str) -> str:
    return value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _secondary_file_declarations(reference: CwlReferenceContract) -> dict[str, tuple[object, ...]]:
    try:
        document = yaml.safe_load(reference.source_text)
    except yaml.YAMLError as error:
        raise ValueError(f"retained CWL source cannot be inspected for secondaryFiles: {error}") from error
    if not isinstance(document, Mapping):
        raise ValueError("retained CWL source is not a mapping")
    inputs = document.get("inputs", {})
    declarations: dict[str, tuple[object, ...]] = {}
    if isinstance(inputs, Mapping):
        entries: list[tuple[object, object]] = list(inputs.items())
    elif isinstance(inputs, list):
        entries = [
            (entry.get("id"), entry)
            for entry in inputs
            if isinstance(entry, Mapping) and isinstance(entry.get("id"), str)
        ]
    else:
        raise ValueError("retained CWL inputs are not a mapping or list")
    for raw_id, schema in entries:
        if not isinstance(raw_id, str) or not isinstance(schema, Mapping) or "secondaryFiles" not in schema:
            continue
        raw = schema["secondaryFiles"]
        values = tuple(raw) if isinstance(raw, list) else (raw,)
        if not values:
            raise ValueError(f"CWL input {_short_cwl_id(raw_id)!r} has empty secondaryFiles")
        declarations[_short_cwl_id(raw_id)] = values
    return declarations


def _literal_secondary_rule(value: object, *, port_id: str) -> tuple[str, bool] | None:
    required = True
    if isinstance(value, str):
        raw_pattern: object = value
        if value.endswith("?"):
            raw_pattern = value[:-1]
            required = False
    elif isinstance(value, Mapping):
        raw_pattern = value.get("pattern")
        raw_required = value.get("required", True)
        if not isinstance(raw_required, bool):
            return None
        required = raw_required
    else:
        raise ValueError(f"CWL input {port_id!r} has an invalid secondaryFiles declaration")
    if not isinstance(raw_pattern, str):
        raise ValueError(f"CWL input {port_id!r} has an invalid secondaryFiles pattern")
    pattern = raw_pattern
    if pattern.startswith(("$(", "${")):
        return None
    if not pattern or "/" in pattern or "\\" in pattern or "\x00" in pattern:
        raise ValueError(f"CWL input {port_id!r} has an unsupported secondaryFiles filename pattern")
    return pattern, required


def _secondary_basename(primary_basename: str, pattern: str, *, port_id: str) -> str:
    remainder = pattern
    basename = primary_basename
    while remainder.startswith("^"):
        remainder = remainder[1:]
        suffix_at = basename.rfind(".")
        if suffix_at > 0:
            basename = basename[:suffix_at]
    selected = basename + remainder
    if selected in ("", ".", "..") or Path(selected).name != selected:
        raise ValueError(f"CWL input {port_id!r} secondaryFiles pattern produced an unsafe basename")
    return selected


def _explicit_secondary_values(value: object, *, port_id: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Mapping) or "secondaryFiles" not in value:
        return ()
    raw = value["secondaryFiles"]
    values = raw if isinstance(raw, list) else [raw]
    selected: list[Mapping[str, object]] = []
    for item in values:
        if not isinstance(item, Mapping) or item.get("class", "File") != "File":
            raise ValueError(f"CWL File input {port_id!r} secondaryFiles must contain File objects")
        if "secondaryFiles" in item:
            raise ValueError(f"CWL File input {port_id!r} nested secondaryFiles are unsupported")
        selected.append(item)
    return tuple(selected)


def _stage_secondary_files(
    declarations: tuple[object, ...],
    value: object,
    *,
    port_id: str,
    primary_source: Path,
    primary_destination: Path,
    receipts: list[dict[str, str]],
) -> list[dict[str, str]]:
    staged: list[dict[str, str]] = []
    names: set[str] = set()
    for item in _explicit_secondary_values(value, port_id=port_id):
        source = _coerce_file(item, port_id=f"{port_id}.secondaryFiles")
        raw_basename = item.get("basename", source.name)
        if not isinstance(raw_basename, str) or raw_basename in ("", ".", ".."):
            raise ValueError(f"CWL File input {port_id!r} has an invalid secondary file basename")
        if Path(raw_basename).name != raw_basename or "\x00" in raw_basename:
            raise ValueError(f"CWL File input {port_id!r} has an unsafe secondary file basename")
        if raw_basename == primary_destination.name or raw_basename in names:
            raise ValueError(f"CWL File input {port_id!r} has colliding staged secondary files")
        destination = primary_destination.parent / raw_basename
        receipt = _stage_file(source, destination)
        receipt.update({"port_id": port_id, "role": "secondary", "primary_staged_path": str(primary_destination)})
        receipts.append(receipt)
        staged_file = {"class": "File", "path": str(destination), "basename": raw_basename}
        file_format = _file_format(item, port_id=f"{port_id}.secondaryFiles")
        if file_format is not None:
            staged_file["format"] = file_format
            receipt["format"] = file_format
        staged.append(staged_file)
        names.add(raw_basename)

    for declaration in declarations:
        rule = _literal_secondary_rule(declaration, port_id=port_id)
        if rule is None:
            if not staged:
                raise ValueError(
                    f"CWL File input {port_id!r} uses a dynamic secondaryFiles expression; "
                    "supply explicit File.secondaryFiles metadata"
                )
            continue
        pattern, required = rule
        basename = _secondary_basename(primary_source.name, pattern, port_id=port_id)
        if basename in names:
            continue
        source = primary_source.with_name(basename)
        if not source.is_file():
            if required:
                raise ValueError(f"CWL File input {port_id!r} requires secondary file {basename!r}")
            continue
        destination = primary_destination.parent / basename
        receipt = _stage_file(source, destination)
        receipt.update({"port_id": port_id, "role": "secondary", "primary_staged_path": str(primary_destination)})
        receipts.append(receipt)
        staged.append({"class": "File", "path": str(destination), "basename": basename})
        names.add(basename)
    return staged


def _stage_json_artifacts(
    value: object,
    *,
    port_id: str,
    staging_root: Path,
    receipts: list[dict[str, str]],
) -> object:
    counter = [0]

    def stage(selected: object, logical_path: str) -> object:
        if isinstance(selected, Mapping) and selected.get("class") in {"File", "Directory"}:
            artifact_class = selected["class"]
            index = counter[0]
            counter[0] += 1
            if artifact_class == "File":
                source = _coerce_file(selected, port_id=f"{port_id}{logical_path}")
                destination = staging_root / f"{index:06d}" / source.name
                receipt = _stage_file(source, destination)
                receipt.update({"port_id": port_id, "role": "nested_file", "json_path": logical_path})
                receipts.append(receipt)
                staged_file: dict[str, object] = {
                    "class": "File",
                    "path": str(destination),
                    "basename": source.name,
                }
                file_format = _file_format(selected, port_id=f"{port_id}{logical_path}")
                if file_format is not None:
                    staged_file["format"] = file_format
                    receipt["format"] = file_format
                secondaries = _stage_secondary_files(
                    (),
                    selected,
                    port_id=f"{port_id}{logical_path}",
                    primary_source=source,
                    primary_destination=destination,
                    receipts=receipts,
                )
                if secondaries:
                    staged_file["secondaryFiles"] = secondaries
                return staged_file
            source_directory = _coerce_directory(selected, port_id=f"{port_id}{logical_path}")
            destination = staging_root / f"{index:06d}" / source_directory.name
            receipt = _stage_directory(source_directory, destination)
            receipt.update({"port_id": port_id, "role": "nested_directory", "json_path": logical_path})
            receipts.append(receipt)
            return {
                "class": "Directory",
                "path": str(destination),
                "basename": source_directory.name,
            }
        if isinstance(selected, Mapping):
            if any(not isinstance(key, str) for key in selected):
                raise ValueError(f"CWL JSON input {port_id!r} requires string object keys")
            return {
                key: stage(item, f"{logical_path}/{key.replace('~', '~0').replace('/', '~1')}")
                for key, item in selected.items()
            }
        if isinstance(selected, (list, tuple)):
            return [stage(item, f"{logical_path}/{index}") for index, item in enumerate(selected)]
        return _json_value(selected)

    return stage(value, "")


def _stage_file(source: Path, destination: Path) -> dict[str, str]:
    digest = _sha256_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination, follow_symlinks=True)
    destination.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    if _sha256_file(destination) != digest:
        raise RuntimeError(f"staged CWL reference input changed while copying: {source}")
    return {"source_path": str(source), "source_sha256": digest, "staged_path": str(destination)}


def _stage_directory(source: Path, destination: Path) -> dict[str, str]:
    source_inventory, source_digest = _directory_inventory(source, label=f"CWL input directory {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, symlinks=True)
    source_after, source_after_digest = _directory_inventory(source, label=f"CWL input directory {source}")
    staged_inventory, staged_digest = _directory_inventory(
        destination,
        label=f"staged CWL input directory {destination}",
    )
    if (
        source_inventory != source_after
        or source_digest != source_after_digest
        or staged_inventory != source_inventory
        or staged_digest != source_digest
    ):
        raise RuntimeError(f"CWL input directory changed while copying: {source}")
    for path in sorted(destination.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    destination.chmod(0o555)
    return {
        "source_path": str(source),
        "source_inventory_sha256": source_digest,
        "staged_path": str(destination),
        "staged_inventory_sha256": staged_digest,
        "entry_count": str(len(staged_inventory)),
    }


def _build_job(
    reference: CwlReferenceContract,
    inputs: Mapping[str, object],
    staging_root: Path,
) -> tuple[dict[str, object], tuple[dict[str, str], ...]]:
    job: dict[str, object] = {}
    receipts: list[dict[str, str]] = []
    secondary_declarations = _secondary_file_declarations(reference)
    for mapping in reference.input_mappings:
        value = inputs.get(mapping.port_id, _MISSING)
        if value is _MISSING or value is None:
            if not mapping.nullable:
                # Defaults are applied by cwltool; absence is valid when the
                # corresponding ParameterSpec carries one.
                continue
            continue
        if mapping.kind not in {"file", "directory"}:
            parameter_value = _parameter_value(mapping, value)
            job[mapping.cwl_id] = (
                _stage_json_artifacts(
                    parameter_value,
                    port_id=mapping.port_id,
                    staging_root=staging_root / mapping.port_id,
                    receipts=receipts,
                )
                if mapping.kind == "json"
                else parameter_value
            )
            continue
        if mapping.array:
            # A graph edge carries one artifact value even when its target port
            # is many-valued. Treat that value as a one-element collection;
            # explicit list/tuple job values retain their original ordering.
            values: list[object] = list(value) if isinstance(value, (list, tuple)) else [value]
        else:
            values = [value]
        staged_files: list[dict[str, object]] = []
        for index, item in enumerate(values):
            if mapping.kind == "directory":
                source_directory = _coerce_directory(item, port_id=mapping.port_id)
                directory_destination = staging_root / mapping.port_id / f"{index:04d}" / source_directory.name
                directory_receipt = _stage_directory(source_directory, directory_destination)
                directory_receipt["port_id"] = mapping.port_id
                receipts.append(directory_receipt)
                staged_files.append(
                    {"class": "Directory", "path": str(directory_destination), "basename": source_directory.name}
                )
                continue
            source = _coerce_file(item, port_id=mapping.port_id)
            destination = staging_root / mapping.port_id / f"{index:04d}" / source.name
            receipt = _stage_file(source, destination)
            receipt["port_id"] = mapping.port_id
            receipts.append(receipt)
            staged_file: dict[str, object] = {"class": "File", "path": str(destination)}
            file_format = _file_format(item, port_id=mapping.port_id)
            if file_format is not None:
                staged_file["format"] = file_format
                receipt["format"] = file_format
            secondary_files = _stage_secondary_files(
                secondary_declarations.get(mapping.cwl_id, ()),
                item,
                port_id=mapping.port_id,
                primary_source=source,
                primary_destination=destination,
                receipts=receipts,
            )
            if secondary_files:
                staged_file["secondaryFiles"] = secondary_files
            staged_files.append(staged_file)
        job[mapping.cwl_id] = staged_files if mapping.array else staged_files[0]
    return job, tuple(receipts)


def _find_output(result: Mapping[str, object], mapping: CwlReferenceOutputMapping) -> object:
    if mapping.cwl_id in result:
        return result[mapping.cwl_id]
    suffixes = (f"#{mapping.cwl_id}", f"/{mapping.cwl_id}")
    matches = [value for key, value in result.items() if key.endswith(suffixes)]
    if len(matches) == 1:
        return matches[0]
    return None


def _output_path(
    value: object,
    *,
    mapping: CwlReferenceOutputMapping,
    engine_output_root: Path,
) -> Path:
    expected_class = "Directory" if mapping.kind == "directory" else "File"
    if not isinstance(value, Mapping) or value.get("class") != expected_class:
        raise ValueError(f"cwltool output {mapping.port_id!r} is not a {expected_class} object")
    raw = value.get("path", value.get("location"))
    if not isinstance(raw, str):
        raise ValueError(f"cwltool output {mapping.port_id!r} has no local path")
    if raw.startswith("file://"):
        parsed = urlsplit(raw)
        if parsed.netloc not in ("", "localhost"):
            raise ValueError(f"cwltool output {mapping.port_id!r} has a nonlocal file URI")
        raw = unquote(parsed.path)
    elif "://" in raw:
        raise ValueError(f"cwltool output {mapping.port_id!r} has a non-file location")
    path = Path(raw).absolute()
    try:
        root = engine_output_root.resolve(strict=True)
        resolved = path.resolve(strict=True)
        relative = resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise ValueError(
            f"cwltool output {mapping.port_id!r} is outside the private engine output directory"
        ) from error
    current = root
    for part in relative.parts:
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except OSError as error:
            raise ValueError(f"cwltool output {mapping.port_id!r} is missing: {path}") from error
        if stat.S_ISLNK(mode):
            raise ValueError(f"cwltool output {mapping.port_id!r} traverses a symbolic link")
    mode = os.lstat(resolved).st_mode
    if mapping.kind == "file" and not stat.S_ISREG(mode):
        raise ValueError(f"cwltool output {mapping.port_id!r} is not a regular file: {path}")
    if mapping.kind == "directory":
        if not stat.S_ISDIR(mode):
            raise ValueError(f"cwltool output {mapping.port_id!r} is not a directory: {path}")
        _directory_inventory(resolved, label=f"cwltool output directory {mapping.port_id!r}")
    return resolved


def _published_name(index: int, source: Path) -> str:
    basename = re.sub(r"[^A-Za-z0-9._+-]+", "_", source.name).strip("._") or "artifact"
    if len(basename.encode("utf-8")) > 180:
        suffix = hashlib.sha256(source.name.encode("utf-8", errors="surrogatepass")).hexdigest()[:12]
        basename = basename[:160] + "-" + suffix
    return f"{index:04d}-{basename}"


def _publish_outputs(
    reference: CwlReferenceContract,
    result: Mapping[str, object],
    root: Path,
) -> tuple[dict[str, object], ...]:
    receipts: list[dict[str, object]] = []
    engine_output_root = root / "engine-output"
    for mapping in reference.output_mappings:
        raw = _find_output(result, mapping)
        if raw is None:
            if mapping.nullable or mapping.array:
                continue
            raise ValueError(f"required cwltool output {mapping.cwl_id!r} is missing")
        # CWL unions such as ``File | File[]`` may return either JSON shape.
        # The NodeSpec projection intentionally normalizes that union to a
        # many-valued artifact port, so normalize the singleton here as well.
        values = raw if mapping.array and isinstance(raw, list) else [raw]
        if not isinstance(values, list):
            raise ValueError(f"cwltool output {mapping.cwl_id!r} must be an array")
        output_dir = _safe_output_path(root, f"published/{mapping.port_id}")
        output_dir.mkdir(parents=True, exist_ok=False)
        for index, value in enumerate(values):
            if mapping.kind not in {"file", "directory"}:
                valid = {
                    "string": lambda item: type(item) is str,
                    "integer": lambda item: type(item) is int,
                    "number": lambda item: type(item) is int or (type(item) is float and math.isfinite(item)),
                    "boolean": lambda item: type(item) is bool,
                }[mapping.kind](value)
                if not valid:
                    raise ValueError(f"cwltool output {mapping.cwl_id!r} is not a {mapping.kind} value")
                destination = output_dir / f"{index:04d}-{mapping.port_id}.json"
                payload = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8") + b"\n"
                destination.write_bytes(payload)
                receipts.append(
                    {
                        "port_id": mapping.port_id,
                        "kind": "scalar_json",
                        "cwl_type": mapping.kind,
                        "published_path": destination.relative_to(root).as_posix(),
                        "sha256": _sha256_file(destination),
                        "size_bytes": len(payload),
                    }
                )
                continue
            source = _output_path(
                value,
                mapping=mapping,
                engine_output_root=engine_output_root,
            )
            destination = output_dir / _published_name(index, source)
            if mapping.kind == "directory":
                source_inventory, source_digest = _directory_inventory(
                    source,
                    label=f"cwltool output directory {mapping.port_id!r}",
                )
                shutil.copytree(source, destination, symlinks=True)
                source_after, source_after_digest = _directory_inventory(
                    source,
                    label=f"cwltool output directory {mapping.port_id!r}",
                )
                published_inventory, published_digest = _directory_inventory(
                    destination,
                    label=f"published CWL output directory {mapping.port_id!r}",
                )
                if (
                    source_inventory != source_after
                    or source_digest != source_after_digest
                    or published_inventory != source_inventory
                    or published_digest != source_digest
                ):
                    raise RuntimeError(f"published CWL directory changed while copying: {mapping.port_id}")
                receipts.append(
                    {
                        "port_id": mapping.port_id,
                        "kind": "directory",
                        "source_path": str(source),
                        "published_path": str(destination.relative_to(root).as_posix()),
                        "inventory_sha256": published_digest,
                        "entry_count": len(published_inventory),
                    }
                )
            else:
                shutil.copyfile(source, destination, follow_symlinks=False)
                digest = _sha256_file(destination)
                if digest != _sha256_file(source):
                    raise RuntimeError(f"published CWL output changed while copying: {mapping.port_id}")
                receipts.append(
                    {
                        "port_id": mapping.port_id,
                        "kind": "file",
                        "source_path": str(source),
                        "published_path": str(destination.relative_to(root).as_posix()),
                        "sha256": digest,
                        "size_bytes": destination.stat().st_size,
                    }
                )
    return tuple(receipts)


def _strict_result(path: Path) -> dict[str, object]:
    if path.stat().st_size > REFERENCE_RESULT_MAX_BYTES:
        raise ValueError("cwltool result JSON exceeds the bounded result size")
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        selected: dict[str, object] = {}
        for key, value in pairs:
            if key in selected:
                raise ValueError(f"duplicate cwltool result key: {key}")
            selected[key] = value
        return selected
    value = json.loads(path.read_bytes(), object_pairs_hook=unique)
    if type(value) is not dict:
        raise ValueError("cwltool result must be one JSON object")
    return value


class CwlReferenceNode(BaseNode, abc.ABC):
    """Base implementation bound dynamically to one retained CWL contract."""

    CONTRACT_SPEC: ClassVar[NodeSpec]
    CONTRACT_DIGEST: ClassVar[str] = ""
    SOURCE_DIGEST: ClassVar[str] = ""
    EXPERIMENTAL = True
    EXECUTOR_CACHE_POLICY = "always_run"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return _input_types(cls.CONTRACT_SPEC)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        reference = _reference(cls.CONTRACT_SPEC)
        parameters = {parameter.parameter_id: parameter for parameter in cls.CONTRACT_SPEC.parameters}
        try:
            for mapping in reference.input_mappings:
                value = inputs.get(mapping.port_id, _MISSING)
                parameter = parameters.get(mapping.port_id)
                if value is _MISSING or value is None:
                    if not mapping.nullable and not (parameter is not None and parameter.has_default):
                        raise ValueError(f"required CWL input {mapping.port_id!r} is missing")
                    continue
                if mapping.kind in {"file", "directory"}:
                    values = value if mapping.array and isinstance(value, (list, tuple)) else (value,)
                    for item in values:  # type: ignore[union-attr]
                        if mapping.kind == "file":
                            _coerce_file(item, port_id=mapping.port_id)
                        else:
                            _coerce_directory(item, port_id=mapping.port_id)
                else:
                    _parameter_value(mapping, value)
        except (OSError, TypeError, ValueError) as error:
            return str(error)
        return True

    @classmethod
    def IS_CHANGED(cls, inputs: dict[str, Any]) -> str:
        environment = cls.CONTRACT_SPEC.environment
        return _canonical_digest(
            {
                "contract_digest": cls.CONTRACT_DIGEST,
                "source_digest": cls.SOURCE_DIGEST,
                "environment_digest": None if environment is None else environment.environment_digest(),
                "inputs": json.loads(cls._serialize_inputs(inputs)),
            }
        )

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        metadata = super().metadata()
        reference = _reference(cls.CONTRACT_SPEC)
        metadata["runtime_descriptor"] = {
            "profile": reference.profile,
            "backend": reference.backend,
            "contract_digest": cls.CONTRACT_DIGEST,
            "source_uri": reference.source_uri,
            "source_content_sha256": reference.source_content_sha256,
            "source_size_bytes": reference.source_size_bytes,
            "engine_version": reference.engine_version,
            "primary_package": reference.primary_package,
            "docker_hint_present": reference.docker_hint_present,
            "unfulfilled_hints": list(reference.unfulfilled_hints),
        }
        return metadata

    async def run(self, **kwargs: Any) -> tuple[object, ...]:
        context = kwargs.pop("context", None)
        explicit_output_dir = kwargs.pop("output_dir", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        reference = _reference(self.CONTRACT_SPEC)
        root_value = explicit_output_dir
        if root_value is None and context is not None:
            root_value = getattr(context, "node_dir", None)
        base_root = _validate_output_root(Path(root_value or "."))
        root = _validate_output_root(Path(tempfile.mkdtemp(prefix=".cwl-reference-attempt-", dir=base_root)))
        log_dir = _validate_output_root(
            Path(tempfile.mkdtemp(prefix=f".{base_root.name}.cwl-reference-logs-", dir=base_root.parent))
        )
        try:
            runtime_receipt = await verify_reference_runtime(
                self.CONTRACT_SPEC,
                context=context,
                log_dir=log_dir,
            )
            engine = Path(str(runtime_receipt["engine_path"]))
            prefix = Path(str(runtime_receipt["environment_prefix"]))
            if _sha256_file(engine) != runtime_receipt["engine_sha256"]:
                raise RuntimeError("configured cwltool changed after its readiness probe")
            primary = Path(str(runtime_receipt["primary_executable"]))
            if _sha256_file(primary) != runtime_receipt["primary_executable_sha256"]:
                raise RuntimeError("primary baseCommand changed after environment verification")
            staging = root / "inputs"
            staging.mkdir(mode=0o700)
            job, input_receipts = _build_job(reference, kwargs, staging)
            descriptor = root / "tool.cwl"
            descriptor.write_text(reference.source_text, encoding="utf-8", newline="")
            if _sha256_file(descriptor) != reference.source_content_sha256:
                raise RuntimeError("retained CWL source changed while staging")
            job_path = root / "job.json"
            job_path.write_bytes(json.dumps(job, allow_nan=False, sort_keys=True).encode("utf-8"))
            engine_out = root / "engine-output"
            engine_out.mkdir(mode=0o700)
            temporary = root / "engine-tmp"
            temporary.mkdir(mode=0o700)
            result_path = log_dir / "cwltool-result.json"
            command = [
                str(engine),
                "--no-container",
                "--disable-color",
                "--preserve-environment",
                "PYTHONDONTWRITEBYTECODE",
                "--outdir",
                str(engine_out),
                "--tmpdir-prefix",
                str(temporary / "tmp-"),
                "--tmp-outdir-prefix",
                str(temporary / "out-"),
            ]
            if "external_schema_not_loaded" in reference.unfulfilled_hints:
                command.append("--skip-schemas")
            command.extend((str(descriptor), str(job_path)))
            runtime_path = [str(prefix / "bin")]
            if runtime_receipt["nodejs_path"] is not None:
                nodejs = Path(str(runtime_receipt["nodejs_path"]))
                if _sha256_file(nodejs) != runtime_receipt["nodejs_sha256"]:
                    raise RuntimeError("configured CWL Node.js changed after its readiness probe")
                runtime_path.append(str(nodejs.parent))
            if runtime_receipt.get("shell_path") is not None:
                shell = Path(str(runtime_receipt["shell_path"]))
                if _sha256_file(shell) != runtime_receipt.get("shell_sha256"):
                    raise RuntimeError("native CWL shell changed after its readiness probe")
            await _run_process(
                command,
                cwd=root,
                context=context,
                env={
                    "PATH": os.pathsep.join(runtime_path),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                stdout_path=result_path,
                stderr_path=log_dir / "cwltool.stderr.log",
                stdout_binary=True,
                stdout_max_bytes=REFERENCE_RESULT_MAX_BYTES,
                timeout=_execution_timeout(context),
            )
            result = _strict_result(result_path)
            output_receipts = _publish_outputs(reference, result, root)
            collected = collect_outputs(self.CONTRACT_SPEC.outputs, root, conditions=kwargs)
        except BaseException:
            if (
                root.parent != base_root
                or not root.name.startswith(".cwl-reference-attempt-")
                or root.is_symlink()
            ):
                raise RuntimeError("refusing to clean an invalid CWL reference attempt workspace")
            shutil.rmtree(root)
            raise

        if context is not None:
            run_metadata = getattr(context, "run_metadata", None)
            if isinstance(run_metadata, dict):
                records = run_metadata.setdefault("cwl_reference", {})
                if isinstance(records, dict):
                    records[str(getattr(context, "node_id", self.NODE_ID))] = {
                        "profile": reference.profile,
                        "backend": reference.backend,
                        "source_uri": reference.source_uri,
                        "source_content_sha256": reference.source_content_sha256,
                        "source_size_bytes": reference.source_size_bytes,
                        "contract_digest": self.CONTRACT_DIGEST,
                        "biotools_accession": reference.biotools_accession,
                        "biotools_uri": reference.biotools_uri,
                        "docker_hint_present": reference.docker_hint_present,
                        "unfulfilled_hints": list(reference.unfulfilled_hints),
                        "attempt_workspace": root.name,
                        "input_staging": list(input_receipts),
                        "output_publication": list(output_receipts),
                        "output_format_metadata_scope": "paths_only_not_retained",
                        **runtime_receipt,
                    }
        return _result_values(self.CONTRACT_SPEC.outputs, root, collected)


def bind_cwl_reference_node(spec: NodeSpec) -> type[BaseNode]:
    """Bind a validated reference-engine NodeSpec to the shared runtime."""
    validated = _validate_bound_spec(spec)
    reference = _reference(validated)
    environment = validated.environment
    assert isinstance(environment, PixiEnvironment)
    implementation_version = validated.identity.implementation_version
    version_base, separator, version_build = implementation_version.partition("+")
    version_build_prefix = f"{version_build}." if separator else ""
    attributes: dict[str, object] = {
        "__module__": __name__,
        "CONTRACT_SPEC": validated,
        "NODE_ID": validated.identity.machine_id,
        "DISPLAY_NAME": validated.presentation.display_name,
        "CATEGORY": "/".join(validated.presentation.palette_path),
        "DESCRIPTION": validated.presentation.description,
        "RETURN_TYPES": tuple(_artifact_widget_type(output.artifact_type) for output in validated.outputs),
        "RETURN_NAMES": tuple(output.port_id for output in validated.outputs),
        "REQUIRES_EXTERNAL_TOOLS": True,
        "REQUIRED_EXECUTABLES": [],
        "REQUIRED_CONDA_PACKAGES": [],
        "ENVIRONMENT": {
            "type": "declarative_cwl",
            "name": environment.environment_id,
            "digest": environment.environment_digest(),
            "packages": [package.name for package in environment.packages],
        },
        "VERSION": f"{version_base}+{version_build_prefix}cwlref.{reference.source_content_sha256[7:19]}",
        "EXPERIMENTAL": True,
        "EXECUTOR_CACHE_POLICY": "always_run",
        "CONTRACT_DIGEST": validated.contract_digest(),
        "SOURCE_DIGEST": reference.source_content_sha256,
        "SOURCE_DIGESTS": (reference.source_content_sha256,),
        "SOURCE_URI": reference.source_uri,
        "DOCUMENTATION_URL": reference.biotools_uri,
    }
    return type(
        "CwlReferenceNode_" + validated.identity.machine_id,
        (CwlReferenceNode,),
        attributes,
    )


__all__ = [
    "CwlReferenceNode",
    "REFERENCE_RESULT_MAX_BYTES",
    "bind_cwl_reference_node",
    "verify_reference_runtime",
]
