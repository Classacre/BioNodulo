from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from bionodulo.environments.constants import (
    EXECUTABLE_TO_CONDA_PACKAGE,
    PACKAGE_MIN_VERSIONS,
)
from bionodulo.environments import manifest as environment_manifest
from bionodulo.environments.manifest import (
    ensure_workflow_env,
    generate_manifest,
    get_env_dir,
    get_env_id,
    is_env_ready,
    is_env_ready_for_lock,
    mark_env_lock_installed,
    materialize_committed_lock,
)
from bionodulo.manager.resolver import resolve_workflow
from bionodulo.manager.installer import DependencyInstaller


def test_wave_two_environment_contracts_are_exact() -> None:
    assert {
        package: PACKAGE_MIN_VERSIONS[package]
        for package in ("bowtie2", "hisat2", "bismark", "spades", "megahit", "quast")
    } == {
        "bowtie2": "2.5.5",
        "hisat2": "2.2.2",
        "bismark": "3.1.0",
        "spades": "4.2.0",
        "megahit": "1.2.9",
        "quast": "5.3.0",
    }
    assert EXECUTABLE_TO_CONDA_PACKAGE["bismark_genome_preparation"] == "bismark"


def test_wave_three_environment_contracts_are_exact() -> None:
    assert {
        package: PACKAGE_MIN_VERSIONS[package]
        for package in (
            "salmon",
            "kallisto",
            "subread",
            "qualimap",
            "macs2",
            "deeptools",
            "bedtools",
            "odgi",
            "pggb",
        )
    } == {
        "salmon": "2.3.4",
        "kallisto": "0.52.0",
        "subread": "2.1.1",
        "qualimap": "2.3",
        "macs2": "2.2.9.1",
        "deeptools": "3.5.6",
        "bedtools": "2.31.1",
        "odgi": "0.9.2",
        "pggb": "0.7.4",
    }


def test_environment_id_changes_with_effective_package_constraint(monkeypatch) -> None:
    monkeypatch.setitem(PACKAGE_MIN_VERSIONS, "samtools", ">=1.15")
    old_id = get_env_id(["samtools"])

    monkeypatch.setitem(PACKAGE_MIN_VERSIONS, "samtools", "1.23.1")

    assert get_env_id(["samtools"]) != old_id


def test_environment_id_still_normalizes_order_case_and_duplicates() -> None:
    assert get_env_id(["samtools", "bcftools"]) == get_env_id(
        [" BCFTOOLS ", "samtools", "SAMTOOLS"]
    )


def test_committed_samtools_lock_materializes_exact_repository_bytes(tmp_path: Path) -> None:
    digest = materialize_committed_lock(tmp_path, ["samtools"])
    source = (
        Path(__file__).resolve().parents[1]
        / "bionodulo/environments/locks/40db091121c94941"
    )

    assert digest is not None
    assert (tmp_path / "pixi.toml").read_bytes() == (source / "pixi.toml").read_bytes()
    assert (tmp_path / "pixi.lock").read_bytes() == (source / "pixi.lock").read_bytes()


def test_committed_lock_readiness_requires_matching_digest_marker(tmp_path: Path) -> None:
    digest = materialize_committed_lock(tmp_path, ["samtools"])
    (tmp_path / ".pixi/envs/default/bin").mkdir(parents=True)

    assert digest is not None
    assert is_env_ready_for_lock(tmp_path, digest) is False
    mark_env_lock_installed(tmp_path, digest)
    assert is_env_ready_for_lock(tmp_path, digest) is True


@pytest.mark.asyncio
async def test_local_environment_installs_committed_lock_without_solving(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_calls: list[bool] = []

    async def unexpected_lock(*_args: Any, **_kwargs: Any) -> tuple[bool, str]:
        raise AssertionError("committed environments must not run pixi lock")

    async def fake_install(
        env_dir: str | Path,
        *_args: Any,
        locked: bool = False,
        **_kwargs: Any,
    ) -> tuple[bool, str]:
        install_calls.append(locked)
        (Path(env_dir) / ".pixi/envs/default/bin").mkdir(parents=True)
        return True, "installed"

    monkeypatch.setattr(environment_manifest, "run_pixi_lock", unexpected_lock)
    monkeypatch.setattr(environment_manifest, "run_pixi_install", fake_install)

    result = await ensure_workflow_env(tmp_path, ["samtools"])

    assert result["ready"] is True
    assert install_calls == [True]
    digest = materialize_committed_lock(tmp_path, ["samtools"])
    assert is_env_ready_for_lock(tmp_path, digest) is True


@pytest.mark.asyncio
async def test_dependency_installer_uses_committed_lock_without_solving(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SamtoolsNode:
        REQUIRED_CONDA_PACKAGES = ["samtools"]
        REQUIRED_EXECUTABLES: list[str] = []
        REQUIRED_R_PACKAGES: list[str] = []

    class Registry:
        @staticmethod
        def get(_node_type: str) -> type[SamtoolsNode]:
            return SamtoolsNode

    lock_calls: list[bool] = []
    install_calls: list[bool] = []

    async def unexpected_lock(*_args: Any, **_kwargs: Any) -> tuple[bool, str]:
        lock_calls.append(True)
        raise AssertionError("committed environments must not run pixi lock")

    async def fake_install(
        env_dir: str | Path,
        *_args: Any,
        locked: bool = False,
        **_kwargs: Any,
    ) -> tuple[bool, str]:
        install_calls.append(locked)
        (Path(env_dir) / ".pixi/envs/default/bin").mkdir(parents=True)
        return True, "installed"

    monkeypatch.setattr(environment_manifest, "run_pixi_lock", unexpected_lock)
    monkeypatch.setattr(environment_manifest, "run_pixi_install", fake_install)

    installer = DependencyInstaller()
    job_id = await installer.install_workflow_env(
        {"nodes": [{"type": "samtools_faidx"}], "edges": []},
        Registry(),
        tmp_path,
    )
    job = installer.get_job(job_id)
    assert job is not None and job._task is not None
    await job._task

    env_dir = tmp_path / "envs" / get_env_id(["samtools"])
    source_lock = (
        Path(__file__).resolve().parents[1]
        / "bionodulo/environments/locks/40db091121c94941/pixi.lock"
    )
    digest = hashlib.sha256(source_lock.read_bytes()).hexdigest()
    assert lock_calls == []
    assert install_calls == [True]
    assert job.progress.status == "completed"
    assert job.progress.message == f"Environment {get_env_id(['samtools'])[:8]} ready with 1 packages"
    assert (env_dir / "pixi.lock").read_bytes() == source_lock.read_bytes()
    assert (env_dir / ".bionodulo-lock-sha256").read_text(encoding="ascii").strip() == digest
    assert is_env_ready_for_lock(env_dir, digest) is True


def test_resolver_does_not_reuse_ready_environment_from_old_constraint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class ToolNode:
        REQUIRED_EXECUTABLES: list[str] = []
        REQUIRED_CONDA_PACKAGES = ["samtools"]
        REQUIRED_R_PACKAGES: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
            return {"required": {}, "optional": {}, "hidden": {}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return ToolNode if node_type == "tool" else None

    monkeypatch.setitem(PACKAGE_MIN_VERSIONS, "samtools", ">=1.15")
    old_env_dir = get_env_dir(get_env_id(["samtools"]), tmp_path)
    generate_manifest(old_env_dir, ["samtools"])
    (old_env_dir / ".pixi" / "envs" / "default" / "bin").mkdir(parents=True)
    assert is_env_ready(old_env_dir) is True

    monkeypatch.setitem(PACKAGE_MIN_VERSIONS, "samtools", "1.23.1")
    report = resolve_workflow(
        {"nodes": [{"id": "tool_001", "type": "tool"}], "edges": []},
        Registry(),
        tmp_path,
    )
    selected_env_dir = get_env_dir(report.env_id, tmp_path)

    assert report.required_packages == ["samtools"]
    assert selected_env_dir != old_env_dir
    assert report.env_ready is False
