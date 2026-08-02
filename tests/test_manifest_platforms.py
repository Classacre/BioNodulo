"""Generated manifests declare the platforms each environment can solve for.

Environments were locked for linux-64 only, so the macOS desktop app could not
install anything even though bioconda ships osx-64 and osx-arm64 builds for
most of these tools.

macOS support is *recorded*, not predicted. Three unrelated mechanisms make it
unpredictable from package names: a version pin whose exact version has no
macOS build (blast 2.17.0), a linux-only build string (macs2 py311hdad781d_1),
and a transitive dead end (bcftools 1.24 -> htslib >=1.24). Each looks fine in
isolation. scripts/solve_macos_locks.py asks the solver and writes the answer
into platform_support.py.

The platform list must stay a pure function of the environment id: committed
manifests are compared to generated text byte-for-byte, so a list that varied
by host would mark every committed lock stale on other machines.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.environments import manifest as m
from bionodulo.environments.platform_support import ENVIRONMENT_PLATFORMS

LOCKS = Path(m.__file__).resolve().parent / "locks"


def _platforms_of(text: str) -> list[str]:
    line = next(entry for entry in text.splitlines() if entry.startswith("platforms ="))
    return [p.strip().strip('"') for p in line.split("[", 1)[1].rstrip("]").split(",")]


def _committed_manifests() -> list[Path]:
    manifests = sorted(LOCKS.glob("*/pixi.toml"))
    assert manifests, "expected committed environment locks"
    return manifests


def test_generated_text_reproduces_every_committed_manifest_exactly() -> None:
    """The byte-for-byte contract that keeps committed locks usable.

    If this fails, `_lock_from_cache` treats committed locks as stale and every
    cloud run silently re-solves instead of installing the attested lock.
    """
    for manifest in _committed_manifests():
        text = manifest.read_text(encoding="utf-8")
        packages = [
            line.split("=", 1)[0].strip()
            for line in text.split("[dependencies]", 1)[-1].splitlines()
            if "=" in line and not line.startswith("[")
        ]
        rendered = m._manifest_text(packages)

        assert _platforms_of(rendered) == _platforms_of(text), manifest.parent.name


def test_an_unrecorded_environment_falls_back_to_linux_only() -> None:
    """A newly-invented package set must still be cloud-runnable, and must not
    claim macOS support nobody has proven."""
    assert m._platforms_for_env("0000000000000000") == ["linux-64"]


def test_linux_is_present_in_every_recorded_environment() -> None:
    """The cloud runs linux-64; no recording may ever drop it."""
    for env_id, platforms in ENVIRONMENT_PLATFORMS.items():
        assert platforms[0] == "linux-64", env_id


def test_recorded_platforms_are_ordered_and_known() -> None:
    for env_id, platforms in ENVIRONMENT_PLATFORMS.items():
        assert set(platforms) <= set(m.SUPPORTED_LOCK_PLATFORMS), env_id
        ordered = [p for p in m.SUPPORTED_LOCK_PLATFORMS if p in platforms]
        assert list(platforms) == ordered, env_id


def test_windows_is_never_recorded() -> None:
    """bioconda publishes no win-64 packages, so a win-64 entry could only be a
    mistake -- and would produce an unsolvable manifest."""
    assert "win-64" not in m.SUPPORTED_LOCK_PLATFORMS
    for env_id, platforms in ENVIRONMENT_PLATFORMS.items():
        assert "win-64" not in platforms, env_id


def test_every_recording_matches_a_committed_lock() -> None:
    """A stale entry would grant macOS support to an environment that no longer
    exists, or mask a renamed one."""
    committed = {p.parent.name for p in _committed_manifests()}

    assert set(ENVIRONMENT_PLATFORMS) <= committed


def test_each_committed_manifest_declares_its_recorded_platforms() -> None:
    for manifest in _committed_manifests():
        env_id = manifest.parent.name
        recorded = list(ENVIRONMENT_PLATFORMS.get(env_id, ("linux-64",)))

        assert _platforms_of(manifest.read_text(encoding="utf-8")) == recorded, env_id


def test_a_lock_covers_every_platform_its_manifest_declares() -> None:
    """A manifest promising osx-arm64 with no osx-arm64 entries in the lock
    would send a Mac user down the solve path the worker rule forbids."""
    for manifest in _committed_manifests():
        declared = _platforms_of(manifest.read_text(encoding="utf-8"))
        lock = (manifest.parent / "pixi.lock").read_text(encoding="utf-8")

        for platform in declared:
            assert f"{platform}:" in lock, f"{manifest.parent.name} missing {platform}"


@pytest.mark.parametrize("platform", ["osx-64", "osx-arm64"])
def test_macos_support_actually_exists(platform: str) -> None:
    """Guards the point of the exercise: if a pin bump silently drops macOS
    everywhere, this fails instead of the desktop app failing for users."""
    covered = [e for e, p in ENVIRONMENT_PLATFORMS.items() if platform in p]

    assert covered, f"no environment supports {platform} any more"
