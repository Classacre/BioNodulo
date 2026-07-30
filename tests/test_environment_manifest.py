from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

from bionodulo.environments.constants import (
    EXECUTABLE_TO_CONDA_PACKAGE,
    PACKAGE_BUILD_CONSTRAINTS,
    PACKAGE_MIN_VERSIONS,
)
from bionodulo.environments import manifest as environment_manifest
from bionodulo.environments.manifest import (
    WorkflowEnvironmentPlan,
    _manifest_text_for_plan,
    ensure_workflow_env,
    generate_manifest,
    get_env_dir,
    get_env_id,
    get_environment_plan_id,
    is_env_ready,
    is_env_ready_for_lock,
    mark_env_lock_installed,
    materialize_committed_lock,
    workflow_to_environment_plan,
    workflow_to_packages,
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
    assert PACKAGE_BUILD_CONSTRAINTS["macs2"] == "py311hdad781d_1"


def test_current_family_environment_contracts_are_exact() -> None:
    assert {
        executable: EXECUTABLE_TO_CONDA_PACKAGE[executable]
        for executable in ("HiC-Pro", "juicer.sh", "maxquant", "diann")
    } == {
        "HiC-Pro": "",
        "juicer.sh": "",
        "maxquant": "maxquant",
        "diann": "",
    }
    assert {
        package: PACKAGE_MIN_VERSIONS[package]
        for package in (
            "methyldackel",
            "cooler",
            "cooltools",
            "bioconductor-dss",
            "maxquant",
            "msfragger",
            "fragpipe",
            "comet-ms",
            "openms",
            "vg",
            "vcflib",
            "panacus",
            "panaroo",
            "minigraph",
            "cactus",
            "htslib",
        )
    } == {
        "methyldackel": "0.6.1",
        "cooler": "0.10.2",
        "cooltools": "0.7.0",
        "bioconductor-dss": "2.58.0",
        "maxquant": "2.0.3.0",
        "msfragger": "4.2",
        "fragpipe": "24.0",
        "comet-ms": "2024011",
        "openms": "3.5.0",
        "vg": "1.63.1",
        "vcflib": "1.0.9",
        "panacus": "0.3.3",
        "panaroo": "1.5.0",
        "minigraph": "0.21",
        "cactus": "2.9.9",
        "htslib": "1.23.1",
    }
    assert "hic-pro" not in PACKAGE_MIN_VERSIONS
    assert "juicer" not in PACKAGE_MIN_VERSIONS
    assert "diann" not in PACKAGE_MIN_VERSIONS


def test_mageck_helper_executables_resolve_to_the_mageck_package() -> None:
    assert {
        executable: EXECUTABLE_TO_CONDA_PACKAGE[executable]
        for executable in ("mageck", "RRA", "mageckGSEA")
    } == {
        "mageck": "mageck",
        "RRA": "mageck",
        "mageckGSEA": "mageck",
    }


def test_environment_id_changes_with_effective_package_constraint(monkeypatch) -> None:
    monkeypatch.setitem(PACKAGE_MIN_VERSIONS, "samtools", ">=1.15")
    old_id = get_env_id(["samtools"])

    monkeypatch.setitem(PACKAGE_MIN_VERSIONS, "samtools", "==1.23.1")

    assert get_env_id(["samtools"]) != old_id


def test_environment_id_changes_with_effective_package_build(monkeypatch) -> None:
    old_id = get_env_id(["macs2"])

    monkeypatch.setitem(PACKAGE_BUILD_CONSTRAINTS, "macs2", "py311haab0aaa_5")

    assert get_env_id(["macs2"]) != old_id


def test_manifest_renders_exact_macs2_build_constraint() -> None:
    manifest = tomllib.loads(environment_manifest._manifest_text(["macs2"]))

    assert manifest["dependencies"]["macs2"] == {
        "version": "2.2.9.1",
        "build": "py311hdad781d_1",
    }


def test_environment_id_still_normalizes_order_case_and_duplicates() -> None:
    assert get_env_id(["samtools", "bcftools"]) == get_env_id(
        [" BCFTOOLS ", "samtools", "SAMTOOLS"]
    )


def test_committed_samtools_manifests_use_explicit_exact_constraint() -> None:
    locks_root = (
        Path(__file__).resolve().parents[1]
        / "bionodulo"
        / "environments"
        / "locks"
    )
    expected_environment_ids = {
        "49242a6d8b2706ab",
        "4997531d441c35bf",
        "5789cfdfd03011a4",
        "5f56c77e87adf0dc",
        "a3e1f5870a14637e",
        "a6d14540abf27c14",
        "a8aef18369bd202f",
        "e7d71a57eedc92e4",
    }
    actual_environment_ids = set()

    for manifest_path in locks_root.glob("*/pixi.toml"):
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        if "samtools" not in manifest.get("dependencies", {}):
            continue
        assert manifest["dependencies"]["samtools"] == "==1.23.1"
        actual_environment_ids.add(manifest_path.parent.name)

    assert actual_environment_ids == expected_environment_ids


def test_committed_macs2_manifest_pins_known_good_bioconda_build() -> None:
    locks_root = (
        Path(__file__).resolve().parents[1]
        / "bionodulo"
        / "environments"
        / "locks"
    )
    manifest = tomllib.loads(
        (locks_root / "49242a6d8b2706ab/pixi.toml").read_text(encoding="utf-8")
    )

    assert "macs2" not in manifest["dependencies"]
    assert manifest["feature"]["macs2"]["dependencies"]["macs2"] == {
        "version": "2.2.9.1",
        "build": "py311hdad781d_1",
    }
    assert manifest["environments"]["macs2"] == {
        "features": ["macs2"],
        "no-default-feature": True,
    }


def test_committed_chip_lock_isolates_macs2_from_deeptools_numpy() -> None:
    lock_path = (
        Path(__file__).resolve().parents[1]
        / "bionodulo/environments/locks/49242a6d8b2706ab/pixi.lock"
    )
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))

    def conda_urls(environment_name: str) -> set[str]:
        return {
            package["conda"]
            for package in lock["environments"][environment_name]["packages"]["linux-64"]
            if "conda" in package
        }

    default_urls = conda_urls("default")
    macs2_urls = conda_urls("macs2")

    assert any("/deeptools-3.5.6-" in url for url in default_urls)
    assert any("/numpy-2.4.6-" in url for url in default_urls)
    assert not any("/macs2-" in url for url in default_urls)
    assert any(
        url.endswith("/macs2-2.2.9.1-py311hdad781d_1.tar.bz2")
        for url in macs2_urls
    )
    assert any("/numpy-1.26.4-" in url for url in macs2_urls)
    assert not any("/deeptools-" in url for url in macs2_urls)


def test_named_environment_plan_partitions_manta_without_changing_flat_requirements() -> None:
    class SamtoolsNode:
        REQUIRED_CONDA_PACKAGES = ["samtools"]
        REQUIRED_EXECUTABLES: list[str] = []
        REQUIRED_R_PACKAGES: list[str] = []
        ENVIRONMENT: dict[str, str] = {}

    class MantaNode:
        REQUIRED_CONDA_PACKAGES = ["manta"]
        REQUIRED_EXECUTABLES: list[str] = []
        REQUIRED_R_PACKAGES: list[str] = []
        ENVIRONMENT = {"type": "pixi", "name": "manta"}

    class Registry:
        @staticmethod
        def get(node_type: str) -> type | None:
            return {"samtools": SamtoolsNode, "manta": MantaNode}.get(node_type)

    workflow = {
        "nodes": [
            {"id": "sort", "type": "samtools"},
            {"id": "sv", "type": "manta"},
        ],
        "edges": [],
    }
    plan = workflow_to_environment_plan(workflow, Registry())

    assert plan == WorkflowEnvironmentPlan(
        default_packages=("samtools",),
        named_environments=(("manta", ("manta",)),),
    )
    assert workflow_to_packages(workflow, Registry()) == ["manta", "samtools"]
    assert get_environment_plan_id(plan) != get_env_id(["manta", "samtools"])
    assert _manifest_text_for_plan(plan).splitlines()[-5:] == [
        "[feature.manta.dependencies]",
        'manta = "1.6.0"',
        "",
        "[environments]",
        'manta = { features = ["manta"], no-default-feature = true }',
    ]


def test_named_environment_readiness_requires_every_planned_prefix(tmp_path: Path) -> None:
    (tmp_path / ".pixi/envs/default/bin").mkdir(parents=True)
    assert is_env_ready(tmp_path, ("default", "manta")) is False
    (tmp_path / ".pixi/envs/manta/bin").mkdir(parents=True)
    assert is_env_ready(tmp_path, ("default", "manta")) is True


def test_named_environment_manifest_drives_status_and_package_listing(tmp_path: Path) -> None:
    plan = WorkflowEnvironmentPlan(
        default_packages=("samtools",),
        named_environments=(("manta", ("manta",)),),
    )
    environment_manifest.generate_environment_manifest(tmp_path, plan)
    (tmp_path / ".pixi/envs/default/bin").mkdir(parents=True)
    assert is_env_ready(tmp_path) is False

    (tmp_path / ".pixi/envs/manta/bin").mkdir(parents=True)
    assert is_env_ready(tmp_path) is True
    assert environment_manifest.get_env_packages(tmp_path) == [
        {"name": "manta", "version": "*"},
        {"name": "samtools", "version": "*"},
    ]


@pytest.mark.parametrize(
    ("packages", "environment_id"),
    [
        (["samtools"], "a8aef18369bd202f"),
        (["fastp", "fastqc", "multiqc"], "fba79120211a36f0"),
    ],
)
def test_committed_locks_materialize_exact_repository_bytes(
    tmp_path: Path,
    packages: list[str],
    environment_id: str,
) -> None:
    digest = materialize_committed_lock(tmp_path, packages)
    source = (
        Path(__file__).resolve().parents[1]
        / "bionodulo/environments/locks"
        / environment_id
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
        / "bionodulo/environments/locks/a8aef18369bd202f/pixi.lock"
    )
    digest = hashlib.sha256(source_lock.read_bytes()).hexdigest()
    assert lock_calls == []
    assert install_calls == [True]
    assert job.progress.status == "completed"
    assert job.progress.message == f"Environment {get_env_id(['samtools'])[:8]} ready with 1 packages"
    assert (env_dir / "pixi.lock").read_bytes() == source_lock.read_bytes()
    assert (env_dir / ".bionodulo-lock-sha256").read_text(encoding="ascii").strip() == digest
    assert is_env_ready_for_lock(env_dir, digest) is True


@pytest.mark.asyncio
async def test_dependency_installer_installs_all_named_environments_from_one_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DefaultNode:
        REQUIRED_CONDA_PACKAGES = ["samtools"]
        REQUIRED_EXECUTABLES: list[str] = []
        REQUIRED_R_PACKAGES: list[str] = []
        ENVIRONMENT: dict[str, str] = {}

    class MantaNode:
        REQUIRED_CONDA_PACKAGES = ["manta"]
        REQUIRED_EXECUTABLES: list[str] = []
        REQUIRED_R_PACKAGES: list[str] = []
        ENVIRONMENT = {"type": "pixi", "name": "manta"}

    class Registry:
        @staticmethod
        def get(node_type: str) -> type | None:
            return {"default": DefaultNode, "manta": MantaNode}.get(node_type)

    workflow = {
        "nodes": [
            {"id": "default", "type": "default"},
            {"id": "manta", "type": "manta"},
        ],
        "edges": [],
    }
    registry = Registry()
    plan = workflow_to_environment_plan(workflow, registry)
    committed_root = tmp_path / "committed"
    bundle = committed_root / get_environment_plan_id(plan)
    environment_manifest.generate_environment_manifest(bundle, plan)
    (bundle / "pixi.lock").write_text("version: 7\n", encoding="utf-8")
    monkeypatch.setattr(environment_manifest, "_COMMITTED_LOCKS_ROOT", committed_root)

    install_calls: list[tuple[bool, bool]] = []

    async def unexpected_lock(*_args: Any, **_kwargs: Any) -> tuple[bool, str]:
        raise AssertionError("a committed multi-environment lock must not be solved")

    async def fake_install(
        env_dir: str | Path,
        *_args: Any,
        locked: bool = False,
        all_environments: bool = False,
        **_kwargs: Any,
    ) -> tuple[bool, str]:
        install_calls.append((locked, all_environments))
        for name in plan.environment_names:
            (Path(env_dir) / ".pixi" / "envs" / name / "bin").mkdir(parents=True)
        return True, "installed"

    monkeypatch.setattr(environment_manifest, "run_pixi_lock", unexpected_lock)
    monkeypatch.setattr(environment_manifest, "run_pixi_install", fake_install)
    installer = DependencyInstaller()
    job_id = await installer.install_workflow_env(workflow, registry, tmp_path / "workspace")
    job = installer.get_job(job_id)
    assert job is not None and job._task is not None
    await job._task

    assert job.progress.status == "completed"
    assert install_calls == [(True, True)]


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

    monkeypatch.setitem(PACKAGE_MIN_VERSIONS, "samtools", "==1.23.1")
    report = resolve_workflow(
        {"nodes": [{"id": "tool_001", "type": "tool"}], "edges": []},
        Registry(),
        tmp_path,
    )
    selected_env_dir = get_env_dir(report.env_id, tmp_path)

    assert report.required_packages == ["samtools"]
    assert selected_env_dir != old_env_dir
    assert report.env_ready is False
