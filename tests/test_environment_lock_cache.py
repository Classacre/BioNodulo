"""Locks may come from a cache, not only from committed repo bundles.

Cloud workers refuse to solve environments at runtime, so every run needs an
exact ``pixi.toml``/``pixi.lock`` pair. Committing one bundle per environment
only works for the curated templates: the moment a user edits a workflow into a
different package set, the environment ID is unknown and the run dies *after* a
VM is already provisioned.

These tests pin the seam that lets a lock be supplied from elsewhere (an
object-storage cache populated by solving once at submit time) while keeping the
worker's rule intact — it still never solves, it only installs a lock it was
handed, and a stale or partial bundle is still a hard error.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from bionodulo.environments import manifest as environment_manifest
from bionodulo.environments.manifest import (
    WorkflowEnvironmentPlan,
    _manifest_text_for_plan,
    get_env_id,
    get_environment_plan_id,
    materialize_committed_environment,
    materialize_committed_lock,
    set_lock_cache,
)

PACKAGES = ["samtools", "bwa"]


@pytest.fixture(autouse=True)
def _clear_cache():
    """No test may leak a cache into another."""
    set_lock_cache(None)
    yield
    set_lock_cache(None)


def _plan() -> WorkflowEnvironmentPlan:
    return WorkflowEnvironmentPlan(default_packages=tuple(PACKAGES), named_environments={})


def test_no_cache_and_no_committed_bundle_still_returns_none(tmp_path: Path) -> None:
    """Unchanged behaviour: an unknown package set has no lock."""
    assert materialize_committed_lock(tmp_path, ["definitely-not-a-real-package-xyz"]) is None


def test_cache_supplies_a_lock_when_no_committed_bundle_exists(tmp_path: Path) -> None:
    packages = ["definitely-not-a-real-package-xyz"]
    manifest_text = environment_manifest._manifest_text(packages)
    lock_bytes = b"version: 6\n# solved at submit time\n"
    seen: list[tuple[str, str]] = []

    def cache(env_id: str, platform: str):
        seen.append((env_id, platform))
        return manifest_text, lock_bytes

    set_lock_cache(cache)
    digest = materialize_committed_lock(tmp_path, packages)

    assert digest == hashlib.sha256(lock_bytes).hexdigest()
    assert (tmp_path / "pixi.toml").read_text(encoding="utf-8") == manifest_text
    assert (tmp_path / "pixi.lock").read_bytes() == lock_bytes
    assert seen == [(get_env_id(packages), "linux-64")]


def test_committed_bundle_wins_over_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The repo is the source of truth for curated environments."""
    called = False

    def cache(env_id: str, platform: str):
        nonlocal called
        called = True
        return "poisoned", b"poisoned"

    # Stand up a committed bundle for a package set that has none, so this
    # asserts precedence rather than depending on which locks happen to exist.
    locks_root = tmp_path / "locks"
    bundle = locks_root / get_env_id(PACKAGES)
    bundle.mkdir(parents=True)
    (bundle / "pixi.toml").write_text(
        environment_manifest._manifest_text(PACKAGES), encoding="utf-8"
    )
    (bundle / "pixi.lock").write_bytes(b"committed-lock")
    monkeypatch.setattr(environment_manifest, "_COMMITTED_LOCKS_ROOT", locks_root)

    set_lock_cache(cache)
    env_dir = tmp_path / "env"
    digest = materialize_committed_lock(env_dir, PACKAGES)

    assert called is False, "cache must not be consulted when a bundle is committed"
    assert (env_dir / "pixi.lock").read_bytes() == b"committed-lock"
    assert digest == hashlib.sha256(b"committed-lock").hexdigest()


def test_cache_miss_is_not_an_error(tmp_path: Path) -> None:
    set_lock_cache(lambda env_id, platform: None)
    assert materialize_committed_lock(tmp_path, ["definitely-not-a-real-package-xyz"]) is None


def test_cache_manifest_must_match_the_plan(tmp_path: Path) -> None:
    """A cached bundle whose manifest drifted is a hard error, never installed.

    Same guard the committed path has: the lock must belong to the exact
    environment we asked for.
    """
    set_lock_cache(lambda env_id, platform: ("[project]\nname = 'wrong'\n", b"lock"))
    with pytest.raises(RuntimeError, match="stale|mismatch"):
        materialize_committed_lock(tmp_path, ["definitely-not-a-real-package-xyz"])
    assert not (tmp_path / "pixi.lock").exists()


def test_named_environment_plans_also_consult_the_cache(tmp_path: Path) -> None:
    plan = WorkflowEnvironmentPlan(
        default_packages=("samtools",),
        named_environments=(("tools", ("definitely-not-a-real-package-xyz",)),),
    )
    manifest_text = _manifest_text_for_plan(plan)
    lock_bytes = b"version: 6\n# named env\n"
    seen: list[tuple[str, str]] = []

    def cache(env_id: str, platform: str):
        seen.append((env_id, platform))
        return manifest_text, lock_bytes

    set_lock_cache(cache)
    digest = materialize_committed_environment(tmp_path, plan)

    assert digest == hashlib.sha256(lock_bytes).hexdigest()
    assert seen == [(get_environment_plan_id(plan), "linux-64")]


def test_cache_is_asked_for_the_target_platform(tmp_path: Path) -> None:
    """Platform namespacing: an aarch64 lock must never satisfy a linux-64 run.

    The environment ID deliberately does not hash the platform, so the cache
    key must carry it or a Graviton-solved lock could be served to an x86 run.
    """
    packages = ["definitely-not-a-real-package-xyz"]
    manifest_text = environment_manifest._manifest_text(packages)
    seen: list[str] = []

    def cache(env_id: str, platform: str):
        seen.append(platform)
        return manifest_text, b"lock"

    set_lock_cache(cache)
    materialize_committed_lock(tmp_path, packages, platform="linux-aarch64")
    assert seen == ["linux-aarch64"]
