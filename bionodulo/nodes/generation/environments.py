"""Realize and verify fully locked Conda environments for generated nodes."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import stat
import subprocess
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Final

from bionodulo.nodes.contract.environments import (
    CondaLockedArtifact,
    ExecutionPlatform,
    PackageRequirement,
    PixiEnvironment,
    PlatformLock,
    ResolverIdentity,
)


DEFAULT_CHANNELS: Final[tuple[str, ...]] = (
    "https://conda.anaconda.org/conda-forge",
    "https://conda.anaconda.org/bioconda",
)
INCOMPLETE_MARKER: Final = ".bionodulo-incomplete.json"
RECEIPT_NAME: Final = ".bionodulo-environment.json"
_REQUEST_RE = re.compile(r"^(?P<name>[a-z0-9][a-z0-9._-]{0,127})==(?P<version>[^=,\s]+)$")


@dataclass(frozen=True)
class CondaPrefixReceipt:
    environment_id: str
    environment_digest: str
    platform: str
    prefix: str
    lock_digest: str
    conda_metadata_sha256: str
    installed_inventory_sha256: str
    verified_file_hashes: int
    unhashed_paths: int
    solver_stdout_sha256: str | None = None
    solver_stderr_sha256: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    selected: dict[str, object] = {}
    for key, value in pairs:
        if key in selected:
            raise ValueError(f"duplicate JSON key: {key}")
        selected[key] = value
    return selected


def _read_json_object(path: Path, *, maximum_bytes: int = 16 * 1024 * 1024) -> dict[str, Any]:
    size = path.stat().st_size
    if size > maximum_bytes:
        raise ValueError(f"Conda metadata file exceeds {maximum_bytes} bytes: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"invalid Conda metadata JSON {path.name}: {error}") from error
    if type(value) is not dict:
        raise ValueError(f"Conda metadata must be a JSON object: {path.name}")
    return value


def _host_platform() -> ExecutionPlatform:
    if os.name == "nt" or platform.system().lower() != "linux":
        raise RuntimeError("generated Conda environments currently require native Linux")
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return ExecutionPlatform.LINUX_AMD64
    if machine in {"aarch64", "arm64"}:
        return ExecutionPlatform.LINUX_ARM64
    raise RuntimeError(f"unsupported Linux architecture: {machine or 'unknown'}")


def _selected_lock(environment: PixiEnvironment, selected: ExecutionPlatform) -> PlatformLock:
    lock = next((item for item in environment.locks if item.platform is selected), None)
    if lock is None:
        raise ValueError(f"environment has no lock for {selected.value}")
    return lock


def _safe_prefix(prefix: Path, *, must_exist: bool) -> Path:
    selected = prefix.expanduser().absolute()
    if not selected.is_absolute():
        raise ValueError("Conda prefix must be absolute")
    if selected.is_symlink():
        raise ValueError("Conda prefix must not be a symlink")
    if must_exist and (not selected.exists() or not selected.is_dir()):
        raise ValueError(f"Conda prefix is not an existing directory: {selected}")
    return selected


def _reservation_path(prefix: Path) -> Path:
    return prefix.parent / f".{prefix.name}{INCOMPLETE_MARKER}"


def _metadata_records(prefix: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    metadata_dir = prefix / "conda-meta"
    if not metadata_dir.is_dir() or metadata_dir.is_symlink():
        raise ValueError("Conda prefix has no safe conda-meta directory")
    records: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(metadata_dir.glob("*.json"), key=lambda item: item.name):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Conda metadata record must be a regular file: {path.name}")
        record = _read_json_object(path)
        name = record.get("name")
        if type(name) is not str or name in records:
            raise ValueError(f"invalid or duplicate Conda package name in {path.name}")
        records[name] = (path, record)
    if not records:
        raise ValueError("Conda prefix has no installed package records")
    return records


def _record_paths(record: dict[str, Any]) -> tuple[tuple[str, str | None, int | None, str | None], ...]:
    paths_data = record.get("paths_data")
    if type(paths_data) is dict and type(paths_data.get("paths")) is list:
        selected: list[tuple[str, str | None, int | None, str | None]] = []
        for entry in paths_data["paths"]:
            if type(entry) is not dict or type(entry.get("_path")) is not str:
                raise ValueError("invalid Conda paths_data entry")
            digest = entry.get("sha256_in_prefix", entry.get("sha256"))
            if digest is not None and (type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
                raise ValueError("invalid Conda installed-file SHA-256")
            size = entry.get("size_in_bytes")
            if size is not None and (type(size) is not int or size < 0):
                raise ValueError("invalid Conda installed-file size")
            path_type = entry.get("path_type")
            if path_type is not None and type(path_type) is not str:
                raise ValueError("invalid Conda installed path type")
            selected.append((entry["_path"], digest, size, path_type))
        return tuple(selected)
    files = record.get("files")
    if type(files) is not list or not all(type(item) is str for item in files):
        raise ValueError("Conda package record has no valid file inventory")
    return tuple((item, None, None, None) for item in files)


def _verify_installed_paths(
    prefix: Path,
    records: dict[str, tuple[Path, dict[str, Any]]],
) -> tuple[int, int, str]:
    verified = 0
    unhashed = 0
    actual_inventory: list[dict[str, object]] = []
    for _record_path, record in records.values():
        for relative, expected_hash, expected_size, _path_type in _record_paths(record):
            path = Path(relative)
            if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
                raise ValueError(f"unsafe installed Conda path: {relative!r}")
            target = prefix.joinpath(*path.parts)
            try:
                mode = os.lstat(target).st_mode
            except OSError as error:
                raise ValueError(f"installed Conda path is missing: {relative}") from error
            if stat.S_ISREG(mode):
                actual_hash = _sha256_file(target)
                actual_inventory.append(
                    {"path": relative, "type": "file", "sha256": actual_hash, "size": target.stat().st_size}
                )
                if expected_hash is None and expected_size is not None and os.lstat(target).st_size != expected_size:
                    raise ValueError(f"installed Conda file size mismatch: {relative}")
                if expected_hash is None:
                    unhashed += 1
                elif actual_hash != "sha256:" + expected_hash:
                    if target.suffix == ".pyc":
                        # Conda post-link/Python startup may regenerate bytecode
                        # after paths_data is written. The exact current bytes
                        # remain bound by installed_inventory_sha256 below.
                        unhashed += 1
                    else:
                        raise ValueError(f"installed Conda file hash mismatch: {relative}")
                else:
                    verified += 1
            elif stat.S_ISLNK(mode):
                if expected_hash is None:
                    unhashed += 1
                    continue
                try:
                    resolved = target.resolve(strict=True)
                except OSError as error:
                    raise ValueError(f"installed Conda symlink target is missing: {relative}") from error
                if os.path.commonpath((str(prefix), str(resolved))) != str(prefix):
                    raise ValueError(f"installed Conda symlink escapes its prefix: {relative}")
                if resolved.is_file():
                    resolved_hash = _sha256_file(resolved)
                    actual_inventory.append(
                        {
                            "path": relative,
                            "type": "symlink-file",
                            "target": os.readlink(target),
                            "sha256": resolved_hash,
                            "size": resolved.stat().st_size,
                        }
                    )
                    if resolved_hash != "sha256:" + expected_hash:
                        raise ValueError(f"installed Conda symlink target hash mismatch: {relative}")
                    verified += 1
                elif resolved.is_dir():
                    link_target = os.readlink(target)
                    if expected_size is not None:
                        # Conda packages in the wild use both representations:
                        # some record the symlink payload byte length (for
                        # example ICU's ``current -> 78.3``), while others
                        # record the resolved directory's stat size (for
                        # example ncbi-vdb). Admit only those two values.
                        recorded_sizes = {
                            len(os.fsencode(link_target)),
                            resolved.stat().st_size,
                        }
                        if expected_size not in recorded_sizes:
                            raise ValueError(f"installed Conda directory symlink size mismatch: {relative}")
                    empty_digest = hashlib.sha256(b"").hexdigest()
                    if expected_hash != empty_digest:
                        raise ValueError(f"installed Conda directory symlink hash mismatch: {relative}")
                    actual_inventory.append(
                        {
                            "path": relative,
                            "type": "symlink-directory",
                            "target": link_target,
                        }
                    )
                    # Conda records a sentinel empty hash for a directory
                    # symlink. Its target is containment- and size-checked,
                    # while the target directory's package files are verified
                    # through their own paths_data entries.
                    unhashed += 1
                else:
                    raise ValueError(f"installed Conda symlink target has unsupported type: {relative}")
            elif stat.S_ISDIR(mode):
                if expected_hash is not None:
                    raise ValueError(f"Conda directory unexpectedly declares a hash: {relative}")
                unhashed += 1
                actual_inventory.append({"path": relative, "type": "directory"})
            else:
                raise ValueError(f"installed Conda path has unsupported file type: {relative}")
    actual_inventory.sort(key=lambda item: str(item["path"]))
    return verified, unhashed, _sha256_bytes(_canonical_bytes(actual_inventory))


def verify_conda_prefix(
    environment: PixiEnvironment,
    prefix: str | Path,
    *,
    platform_id: ExecutionPlatform | None = None,
    require_receipt: bool = True,
) -> CondaPrefixReceipt:
    """Verify exact installed package identities and available per-file hashes."""
    validated = PixiEnvironment.model_validate(environment)
    selected = platform_id or _host_platform()
    lock = _selected_lock(validated, selected)
    root = _safe_prefix(Path(prefix), must_exist=True)
    if (root / INCOMPLETE_MARKER).exists() or (require_receipt and _reservation_path(root).exists()):
        raise ValueError("Conda prefix is marked as an incomplete realization")
    if require_receipt and not (root / RECEIPT_NAME).is_file():
        raise ValueError("Conda prefix has no verified realization receipt")

    records = _metadata_records(root)
    locked = {
        artifact.name: artifact
        for artifact in lock.artifacts
        if isinstance(artifact, CondaLockedArtifact)
    }
    if len(locked) != len(lock.artifacts):
        raise ValueError("generated Conda runtime does not support non-Conda lock artifacts")
    if set(records) != set(locked):
        missing = sorted(set(locked) - set(records))
        extra = sorted(set(records) - set(locked))
        raise ValueError(f"installed Conda inventory differs from lock (missing={missing}, extra={extra})")

    canonical_records: list[dict[str, object]] = []
    for name in sorted(locked):
        _path, record = records[name]
        artifact = locked[name]
        for field, expected in (
            ("name", artifact.name),
            ("version", artifact.version),
            ("build", artifact.build),
            ("fn", artifact.filename),
        ):
            if record.get(field) != expected:
                raise ValueError(f"installed Conda {name!r} {field} does not match lock")
        record_sha256 = record.get("sha256")
        if record_sha256 is not None and record_sha256 != artifact.sha256.removeprefix("sha256:"):
            raise ValueError(f"installed Conda {name!r} archive hash does not match lock")
        record_url = record.get("url")
        if record_url is not None and record_url != artifact.url:
            raise ValueError(f"installed Conda {name!r} URL does not match lock")
        canonical_records.append(
            {
                "name": artifact.name,
                "version": artifact.version,
                "build": artifact.build,
                "filename": artifact.filename,
                "url": artifact.url,
                "sha256": artifact.sha256,
            }
        )

    verified, unhashed, installed_inventory_sha256 = _verify_installed_paths(root, records)
    receipt = CondaPrefixReceipt(
        environment_id=validated.environment_id,
        environment_digest=validated.environment_digest(),
        platform=selected.value,
        prefix=str(root),
        lock_digest=lock.lock_digest(),
        conda_metadata_sha256=_sha256_bytes(_canonical_bytes(canonical_records)),
        installed_inventory_sha256=installed_inventory_sha256,
        verified_file_hashes=verified,
        unhashed_paths=unhashed,
    )
    if require_receipt:
        retained = _read_json_object(root / RECEIPT_NAME)
        for field in (
            "environment_id",
            "environment_digest",
            "lock_digest",
            "conda_metadata_sha256",
        ):
            if retained.get(field) != getattr(receipt, field):
                raise ValueError(f"retained Conda realization receipt has stale {field}")
        retained_inventory = retained.get("installed_inventory_sha256")
        if retained_inventory is None:
            raise ValueError("retained Conda realization receipt has no installed path inventory digest")
        if retained_inventory != installed_inventory_sha256:
            raise ValueError("installed Conda path inventory differs from realization receipt")
    return receipt


def _parse_requests(requests: tuple[str, ...]) -> tuple[PackageRequirement, ...]:
    parsed: list[PackageRequirement] = []
    for request in requests:
        match = _REQUEST_RE.fullmatch(request)
        if match is None:
            raise ValueError(f"generated Conda requirement must be an exact name==version pin: {request!r}")
        parsed.append(PackageRequirement(name=match.group("name"), constraint="==" + match.group("version")))
    parsed.sort(key=lambda item: item.name)
    if not parsed or len({item.name for item in parsed}) != len(parsed):
        raise ValueError("generated Conda requirements must be nonempty and unique")
    return tuple(parsed)


def _micromamba_version(executable: Path) -> str:
    result = subprocess.run(
        [str(executable), "--version"],
        check=True,
        shell=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    tokens = result.stdout.strip().split()
    version = tokens[-1] if tokens else ""
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)+(?:[A-Za-z0-9._+-]*)", version) is None:
        raise RuntimeError("micromamba did not report an exact version")
    return version


def _artifact_from_record(record: dict[str, Any]) -> CondaLockedArtifact:
    required = ("name", "version", "build", "fn", "url", "sha256")
    if any(type(record.get(field)) is not str or not record[field] for field in required):
        raise ValueError("installed Conda record lacks immutable package identity fields")
    size = record.get("size")
    if type(size) is not int or size < 1:
        size = None
    return CondaLockedArtifact(
        name=record["name"],
        version=record["version"],
        build=record["build"],
        filename=record["fn"],
        url=record["url"],
        sha256="sha256:" + record["sha256"],
        size_bytes=size,
    )


def _derive_environment(
    packages: tuple[PackageRequirement, ...],
    prefix: Path,
    micromamba: Path,
    channels: tuple[str, ...],
    selected: ExecutionPlatform,
) -> PixiEnvironment:
    explicit = subprocess.run(
        [str(micromamba), "list", "--explicit", "--prefix", str(prefix)],
        check=True,
        shell=False,
        capture_output=True,
        timeout=120,
    ).stdout
    records = _metadata_records(prefix)
    artifacts = tuple(
        sorted((_artifact_from_record(record) for _path, record in records.values()), key=lambda item: item.name)
    )
    resolver = ResolverIdentity(
        name="micromamba",
        version=_micromamba_version(micromamba),
        config_digest=_sha256_bytes(
            _canonical_bytes({"channels": list(channels), "strict_channel_priority": True})
        ),
    )
    native_lock_sha256 = _sha256_bytes(explicit)
    identity_payload = {
        "requests": [item.as_string() for item in packages],
        "platform": selected.value,
        "native_lock_sha256": native_lock_sha256,
    }
    environment_id = "generated-cwl-" + hashlib.sha256(_canonical_bytes(identity_payload)).hexdigest()[:20]
    lock = PlatformLock(
        platform=selected,
        environment_name=environment_id,
        resolver_platform="linux-64" if selected is ExecutionPlatform.LINUX_AMD64 else "linux-aarch64",
        resolver=resolver,
        native_lock_sha256=native_lock_sha256,
        artifacts=artifacts,
    )
    return PixiEnvironment(
        environment_id=environment_id,
        platforms=(selected,),
        packages=packages,
        locks=(lock,),
        channels=tuple(sorted(channels)),
    )


def _publish_receipt(prefix: Path, receipt: CondaPrefixReceipt) -> None:
    receipt_path = prefix / RECEIPT_NAME
    temporary_receipt = prefix / f".{RECEIPT_NAME}.tmp-{os.getpid()}"
    with temporary_receipt.open("xb") as handle:
        handle.write(_canonical_bytes(receipt.to_dict()))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary_receipt, receipt_path)


def solve_conda_environment(
    requests: tuple[str, ...],
    *,
    prefix: str | Path,
    micromamba: str | Path,
    channels: tuple[str, ...] = DEFAULT_CHANNELS,
    timeout_seconds: float = 300.0,
) -> tuple[PixiEnvironment, CondaPrefixReceipt]:
    """Solve exact requests into a fresh final prefix and derive its full lock.

    The final prefix is reserved before micromamba runs because Conda prefixes
    embed absolute paths and must not be relocated. A failed prefix retains an
    incomplete marker and is never admitted as a valid realization.
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0 or timeout_seconds > 3600:
        raise ValueError("generated Conda solve timeout must be in (0, 3600] seconds")
    packages = _parse_requests(requests)
    selected = _host_platform()
    final_prefix = _safe_prefix(Path(prefix), must_exist=False)
    if final_prefix.exists() or final_prefix.is_symlink():
        raise FileExistsError(f"generated Conda prefix already exists: {final_prefix}")
    executable = Path(micromamba).expanduser().absolute()
    if not executable.is_file() or executable.is_symlink() or not os.access(executable, os.X_OK):
        raise ValueError("micromamba must be an existing absolute executable regular file")
    final_prefix.parent.mkdir(parents=True, exist_ok=True)
    marker = _reservation_path(final_prefix)
    with marker.open("xb") as handle:
        handle.write(
            _canonical_bytes(
                {
                    "prefix": str(final_prefix),
                    "requests": [item.as_string() for item in packages],
                    "status": "incomplete",
                }
            )
        )
        handle.flush()
        os.fsync(handle.fileno())

    command = [str(executable), "create", "--yes", "--no-rc", "--strict-channel-priority"]
    for channel in channels:
        command.extend(("--channel", channel))
    command.extend(("--prefix", str(final_prefix)))
    command.extend(item.as_string() for item in packages)
    solver_stdout = final_prefix.parent / f".{final_prefix.name}.micromamba-create.stdout.log"
    solver_stderr = final_prefix.parent / f".{final_prefix.name}.micromamba-create.stderr.log"
    with solver_stdout.open("xb") as stdout_handle, solver_stderr.open("xb") as stderr_handle:
        subprocess.run(
            command,
            check=True,
            shell=False,
            timeout=timeout_seconds,
            stdout=stdout_handle,
            stderr=stderr_handle,
        )
    environment = _derive_environment(
        packages,
        final_prefix,
        executable,
        channels,
        selected,
    )
    receipt = verify_conda_prefix(
        environment,
        final_prefix,
        platform_id=selected,
        require_receipt=False,
    )
    receipt = replace(
        receipt,
        solver_stdout_sha256=_sha256_file(solver_stdout),
        solver_stderr_sha256=_sha256_file(solver_stderr),
    )
    _publish_receipt(final_prefix, receipt)
    marker.unlink()
    return environment, receipt


def recover_conda_environment(
    requests: tuple[str, ...],
    *,
    prefix: str | Path,
    micromamba: str | Path,
    channels: tuple[str, ...] = DEFAULT_CHANNELS,
) -> tuple[PixiEnvironment, CondaPrefixReceipt]:
    """Validate and publish a receipt for an installed but incomplete prefix."""
    packages = _parse_requests(requests)
    selected = _host_platform()
    final_prefix = _safe_prefix(Path(prefix), must_exist=True)
    marker = _reservation_path(final_prefix)
    try:
        marker_mode = os.lstat(marker).st_mode
    except OSError as error:
        raise ValueError("Conda prefix is not an unpublished reserved realization") from error
    if not stat.S_ISREG(marker_mode) or os.path.lexists(final_prefix / RECEIPT_NAME):
        raise ValueError("Conda prefix is not an unpublished reserved realization")
    marker_payload = _read_json_object(marker, maximum_bytes=64 * 1024)
    expected_marker = {
        "prefix": str(final_prefix),
        "requests": [item.as_string() for item in packages],
        "status": "incomplete",
    }
    if marker_payload != expected_marker:
        raise ValueError("Conda prefix reservation marker does not match the requested realization")
    executable = Path(micromamba).expanduser().absolute()
    if not executable.is_file() or executable.is_symlink() or not os.access(executable, os.X_OK):
        raise ValueError("micromamba must be an existing absolute executable regular file")
    solver_stdout = final_prefix.parent / f".{final_prefix.name}.micromamba-create.stdout.log"
    solver_stderr = final_prefix.parent / f".{final_prefix.name}.micromamba-create.stderr.log"
    for log_path in (solver_stdout, solver_stderr):
        try:
            log_mode = os.lstat(log_path).st_mode
        except OSError as error:
            raise ValueError(f"reserved Conda realization has no solver log: {log_path.name}") from error
        if not stat.S_ISREG(log_mode):
            raise ValueError(f"reserved Conda solver log must be a regular file: {log_path.name}")
    environment = _derive_environment(packages, final_prefix, executable, channels, selected)
    receipt = verify_conda_prefix(
        environment,
        final_prefix,
        platform_id=selected,
        require_receipt=False,
    )
    receipt = replace(
        receipt,
        solver_stdout_sha256=_sha256_file(solver_stdout),
        solver_stderr_sha256=_sha256_file(solver_stderr),
    )
    _publish_receipt(final_prefix, receipt)
    marker.unlink()
    return environment, receipt


__all__ = [
    "CondaPrefixReceipt",
    "DEFAULT_CHANNELS",
    "INCOMPLETE_MARKER",
    "RECEIPT_NAME",
    "recover_conda_environment",
    "solve_conda_environment",
    "verify_conda_prefix",
]
