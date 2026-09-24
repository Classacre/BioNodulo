"""Generated Conda prefixes retain and verify complete package identities."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from bionodulo.nodes.contract.environments import (
    CondaLockedArtifact,
    ExecutionPlatform,
    PackageRequirement,
    PixiEnvironment,
    PlatformLock,
    ResolverIdentity,
)
from bionodulo.nodes.generation import environments


SHA_A = "sha256:" + "a" * 64


def _write_record(
    prefix: Path,
    *,
    name: str,
    version: str,
    build: str = "test_0",
) -> CondaLockedArtifact:
    relative = f"bin/{name}"
    content = f"{name}-{version}\n".encode()
    target = prefix / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    filename = f"{name}-{version}-{build}.conda"
    url = f"https://conda.anaconda.org/conda-forge/linux-64/{filename}"
    archive_hash = hashlib.sha256((name + version).encode()).hexdigest()
    record = {
        "name": name,
        "version": version,
        "build": build,
        "fn": filename,
        "url": url,
        "sha256": archive_hash,
        "size": 100,
        "paths_data": {
            "paths": [
                {
                    "_path": relative,
                    "path_type": "hardlink",
                    "sha256_in_prefix": hashlib.sha256(content).hexdigest(),
                }
            ]
        },
    }
    metadata = prefix / "conda-meta"
    metadata.mkdir(exist_ok=True)
    (metadata / f"{name}-{version}-{build}.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    return CondaLockedArtifact(
        name=name,
        version=version,
        build=build,
        filename=filename,
        url=url,
        sha256="sha256:" + archive_hash,
        size_bytes=100,
    )


def _environment(prefix: Path) -> PixiEnvironment:
    artifacts = tuple(
        sorted(
            (
                _write_record(prefix, name="cwltool", version="3.1.2"),
                _write_record(prefix, name="seqtk", version="1.4"),
            ),
            key=lambda item: item.name,
        )
    )
    lock = PlatformLock(
        platform=ExecutionPlatform.LINUX_AMD64,
        environment_name="generated-cwl-test",
        resolver_platform="linux-64",
        resolver=ResolverIdentity(name="micromamba", version="2.3.3", config_digest=SHA_A),
        native_lock_sha256="sha256:" + "b" * 64,
        artifacts=artifacts,
    )
    return PixiEnvironment(
        environment_id="generated-cwl-test",
        platforms=(ExecutionPlatform.LINUX_AMD64,),
        packages=(
            PackageRequirement(name="cwltool", constraint="==3.1.2"),
            PackageRequirement(name="seqtk", constraint="==1.4"),
        ),
        locks=(lock,),
        channels=tuple(sorted(environments.DEFAULT_CHANNELS)),
    )


def test_verify_conda_prefix_checks_inventory_and_installed_file_hashes(tmp_path: Path) -> None:
    environment = _environment(tmp_path)

    receipt = environments.verify_conda_prefix(
        environment,
        tmp_path,
        platform_id=ExecutionPlatform.LINUX_AMD64,
        require_receipt=False,
    )

    assert receipt.environment_digest == environment.environment_digest()
    assert receipt.verified_file_hashes == 2
    assert receipt.unhashed_paths == 0

    (tmp_path / "bin" / "seqtk").write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="installed Conda file hash mismatch"):
        environments.verify_conda_prefix(
            environment,
            tmp_path,
            platform_id=ExecutionPlatform.LINUX_AMD64,
            require_receipt=False,
        )


def test_incomplete_or_extra_package_prefix_is_rejected(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    marker = tmp_path.parent / f".{tmp_path.name}{environments.INCOMPLETE_MARKER}"
    marker.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete realization"):
        environments.verify_conda_prefix(
            environment,
            tmp_path,
            platform_id=ExecutionPlatform.LINUX_AMD64,
        )
    marker.unlink()
    _write_record(tmp_path, name="unexpected", version="1.0")
    with pytest.raises(ValueError, match="inventory differs"):
        environments.verify_conda_prefix(
            environment,
            tmp_path,
            platform_id=ExecutionPlatform.LINUX_AMD64,
            require_receipt=False,
        )


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
def test_conda_softlink_hash_verifies_resolved_internal_target(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    target = tmp_path / "lib" / "libseqtk.so.1.0"
    target.parent.mkdir()
    target.write_bytes(b"shared-library")
    link = tmp_path / "lib" / "libseqtk.so.1"
    link.symlink_to(target.name)
    metadata = next((tmp_path / "conda-meta").glob("seqtk-*.json"))
    record = json.loads(metadata.read_text(encoding="utf-8"))
    record["paths_data"]["paths"].append(
        {
            "_path": "lib/libseqtk.so.1",
                    "path_type": "softlink",
                    "sha256_in_prefix": hashlib.sha256(b"shared-library").hexdigest(),
                    "size_in_bytes": len(b"shared-library"),
        }
    )
    metadata.write_text(json.dumps(record), encoding="utf-8")

    receipt = environments.verify_conda_prefix(
        environment,
        tmp_path,
        platform_id=ExecutionPlatform.LINUX_AMD64,
        require_receipt=False,
    )

    assert receipt.verified_file_hashes == 3


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
def test_conda_directory_softlink_requires_internal_target_and_empty_hash(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    target = tmp_path / "lib" / "icu" / "78.3"
    target.mkdir(parents=True)
    link = tmp_path / "lib" / "icu" / "current"
    link.symlink_to(target.name, target_is_directory=True)
    metadata = next((tmp_path / "conda-meta").glob("seqtk-*.json"))
    record = json.loads(metadata.read_text(encoding="utf-8"))
    record["paths_data"]["paths"].append(
        {
            "_path": "lib/icu/current",
            "path_type": "softlink",
            "sha256_in_prefix": hashlib.sha256(b"").hexdigest(),
            "size_in_bytes": target.stat().st_size,
        }
    )
    metadata.write_text(json.dumps(record), encoding="utf-8")

    receipt = environments.verify_conda_prefix(
        environment,
        tmp_path,
        platform_id=ExecutionPlatform.LINUX_AMD64,
        require_receipt=False,
    )

    assert receipt.unhashed_paths == 1


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
def test_conda_directory_softlink_accepts_link_payload_size(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    target = tmp_path / "usr" / "include" / "ncbi-vdb"
    target.mkdir(parents=True)
    link = tmp_path / "usr" / "include" / "vdb-current"
    link.symlink_to(target.name, target_is_directory=True)
    assert os.lstat(link).st_size != target.stat().st_size
    metadata = next((tmp_path / "conda-meta").glob("seqtk-*.json"))
    record = json.loads(metadata.read_text(encoding="utf-8"))
    record["paths_data"]["paths"].append(
        {
            "_path": "usr/include/vdb-current",
            "path_type": "softlink",
            "sha256_in_prefix": hashlib.sha256(b"").hexdigest(),
            "size_in_bytes": len(os.fsencode(os.readlink(link))),
        }
    )
    metadata.write_text(json.dumps(record), encoding="utf-8")

    receipt = environments.verify_conda_prefix(
        environment,
        tmp_path,
        platform_id=ExecutionPlatform.LINUX_AMD64,
        require_receipt=False,
    )

    assert receipt.unhashed_paths == 1


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
def test_conda_directory_softlink_rejects_unrecognized_size(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    target = tmp_path / "usr" / "include" / "ncbi-vdb"
    target.mkdir(parents=True)
    link = tmp_path / "usr" / "include" / "vdb-current"
    link.symlink_to(target.name, target_is_directory=True)
    invalid_size = max(os.lstat(link).st_size, target.stat().st_size) + 1
    metadata = next((tmp_path / "conda-meta").glob("seqtk-*.json"))
    record = json.loads(metadata.read_text(encoding="utf-8"))
    record["paths_data"]["paths"].append(
        {
            "_path": "usr/include/vdb-current",
            "path_type": "softlink",
            "sha256_in_prefix": hashlib.sha256(b"").hexdigest(),
            "size_in_bytes": invalid_size,
        }
    )
    metadata.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="directory symlink size mismatch"):
        environments.verify_conda_prefix(
            environment,
            tmp_path,
            platform_id=ExecutionPlatform.LINUX_AMD64,
            require_receipt=False,
        )


def _write_recovery_marker(prefix: Path, requests: tuple[str, ...]) -> Path:
    marker = prefix.parent / f".{prefix.name}{environments.INCOMPLETE_MARKER}"
    marker.write_text(
        json.dumps(
            {
                "prefix": str(prefix.absolute()),
                "requests": list(requests),
                "status": "incomplete",
            }
        ),
        encoding="utf-8",
    )
    return marker


def test_recover_conda_environment_requires_exact_marker_and_solver_logs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "generated-prefix"
    prefix.mkdir()
    requests = ("seqtk==1.4",)
    marker = _write_recovery_marker(prefix, requests)
    micromamba = tmp_path / "micromamba"
    micromamba.write_bytes(b"binary")
    monkeypatch.setattr(environments, "_host_platform", lambda: ExecutionPlatform.LINUX_AMD64)
    monkeypatch.setattr(environments.os, "access", lambda _path, _mode: True)

    with pytest.raises(ValueError, match="no solver log"):
        environments.recover_conda_environment(
            requests,
            prefix=prefix,
            micromamba=micromamba,
        )

    stdout_log = prefix.parent / f".{prefix.name}.micromamba-create.stdout.log"
    stderr_log = prefix.parent / f".{prefix.name}.micromamba-create.stderr.log"
    stdout_log.write_bytes(b"solver stdout")
    stderr_log.mkdir()
    with pytest.raises(ValueError, match="solver log must be a regular file"):
        environments.recover_conda_environment(
            requests,
            prefix=prefix,
            micromamba=micromamba,
        )

    stderr_log.rmdir()
    stderr_log.write_bytes(b"solver stderr")
    marker.write_text(
        json.dumps(
            {
                "prefix": str(prefix.absolute()),
                "requests": ["seqtk==9.9"],
                "status": "incomplete",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="marker does not match"):
        environments.recover_conda_environment(
            requests,
            prefix=prefix,
            micromamba=micromamba,
        )


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires extra privileges")
def test_recover_conda_environment_rejects_symlink_marker_and_logs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "generated-prefix"
    prefix.mkdir()
    requests = ("seqtk==1.4",)
    real_marker = tmp_path / "marker.json"
    real_marker.write_text(
        json.dumps(
            {"prefix": str(prefix.absolute()), "requests": list(requests), "status": "incomplete"}
        ),
        encoding="utf-8",
    )
    marker = prefix.parent / f".{prefix.name}{environments.INCOMPLETE_MARKER}"
    marker.symlink_to(real_marker)
    micromamba = tmp_path / "micromamba"
    micromamba.write_bytes(b"binary")
    monkeypatch.setattr(environments, "_host_platform", lambda: ExecutionPlatform.LINUX_AMD64)
    monkeypatch.setattr(environments.os, "access", lambda _path, _mode: True)

    with pytest.raises(ValueError, match="not an unpublished reserved realization"):
        environments.recover_conda_environment(
            requests,
            prefix=prefix,
            micromamba=micromamba,
        )

    marker.unlink()
    _write_recovery_marker(prefix, requests)
    real_log = tmp_path / "solver.log"
    real_log.write_bytes(b"solver output")
    stdout_log = prefix.parent / f".{prefix.name}.micromamba-create.stdout.log"
    stderr_log = prefix.parent / f".{prefix.name}.micromamba-create.stderr.log"
    stdout_log.symlink_to(real_log)
    stderr_log.write_bytes(b"solver stderr")
    with pytest.raises(ValueError, match="solver log must be a regular file"):
        environments.recover_conda_environment(
            requests,
            prefix=prefix,
            micromamba=micromamba,
        )


def test_recover_conda_environment_publishes_log_bound_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "generated-prefix"
    environment = _environment(prefix)
    requests = ("cwltool==3.1.2", "seqtk==1.4")
    marker = _write_recovery_marker(prefix, requests)
    stdout_log = prefix.parent / f".{prefix.name}.micromamba-create.stdout.log"
    stderr_log = prefix.parent / f".{prefix.name}.micromamba-create.stderr.log"
    stdout_log.write_bytes(b"solver stdout")
    stderr_log.write_bytes(b"solver stderr")
    micromamba = tmp_path / "micromamba"
    micromamba.write_bytes(b"binary")
    monkeypatch.setattr(environments, "_host_platform", lambda: ExecutionPlatform.LINUX_AMD64)
    monkeypatch.setattr(environments.os, "access", lambda _path, _mode: True)
    monkeypatch.setattr(environments, "_derive_environment", lambda *_args, **_kwargs: environment)

    recovered, receipt = environments.recover_conda_environment(
        requests,
        prefix=prefix,
        micromamba=micromamba,
    )

    assert recovered == environment
    assert receipt.solver_stdout_sha256 == environments._sha256_file(stdout_log)
    assert receipt.solver_stderr_sha256 == environments._sha256_file(stderr_log)
    assert not marker.exists()
    assert (prefix / environments.RECEIPT_NAME).is_file()

def test_failed_solve_retains_final_prefix_as_invalid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    micromamba = tmp_path / "micromamba"
    micromamba.write_bytes(b"binary")
    prefix = tmp_path / "generated" / "failed-prefix"
    monkeypatch.setattr(environments, "_host_platform", lambda: ExecutionPlatform.LINUX_AMD64)
    monkeypatch.setattr(environments.os, "access", lambda _path, _mode: True)

    def fail(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.CalledProcessError(1, "micromamba")

    monkeypatch.setattr(environments.subprocess, "run", fail)

    with pytest.raises(subprocess.CalledProcessError):
        environments.solve_conda_environment(
            ("cwltool==3.1.2", "seqtk==1.4"),
            prefix=prefix,
            micromamba=micromamba,
        )

    marker = prefix.parent / f".{prefix.name}{environments.INCOMPLETE_MARKER}"
    assert marker.is_file()
    with pytest.raises(FileExistsError):
        environments.solve_conda_environment(
            ("cwltool==3.1.2", "seqtk==1.4"),
            prefix=prefix,
            micromamba=micromamba,
        )


def test_generated_requirements_must_be_exact_unique_pins(tmp_path: Path) -> None:
    micromamba = tmp_path / "micromamba"
    micromamba.write_bytes(b"binary")
    for requests in (("seqtk>=1.4",), ("seqtk==1.4", "seqtk==1.4"), ()):
        with pytest.raises(ValueError):
            environments.solve_conda_environment(
                requests,
                prefix=tmp_path / ("prefix-" + str(len(requests))),
                micromamba=micromamba,
            )
    assert not any(path.name.startswith("prefix-") for path in tmp_path.iterdir())


def test_generated_solve_timeout_is_bounded_before_prefix_reservation(tmp_path: Path) -> None:
    micromamba = tmp_path / "micromamba"
    micromamba.write_bytes(b"binary")

    for timeout in (0, -1, float("inf"), 3601):
        with pytest.raises(ValueError, match="solve timeout"):
            environments.solve_conda_environment(
                ("seqtk==1.4",),
                prefix=tmp_path / f"invalid-timeout-{timeout}",
                micromamba=micromamba,
                timeout_seconds=timeout,
            )
