"""A workflow environment that cannot install here must say why, usefully.

On Windows, pixi reports:

    The workspace does not support 'win-64' on this machine.
    Add it with 'pixi workspace platform add win-64'.

That advice cannot work. bioconda publishes no Windows packages at all -- blast
and samtools exist only for linux-64, linux-aarch64, osx-64 and osx-arm64 -- so
adding the platform swaps a clear install failure for a confusing solve failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.environments import manifest as m


def test_windows_is_named_as_the_real_constraint() -> None:
    reason = m.explain_unsupported_platform(["linux-64"], "win-64")

    assert "bioconda" in reason
    assert "Windows" in reason
    # The actionable routes out, not pixi's dead-end suggestion.
    assert "cloud" in reason.lower()
    assert "WSL2" in reason
    assert "platform add" not in reason


def test_other_mismatches_get_a_generic_but_honest_message() -> None:
    reason = m.explain_unsupported_platform(["linux-64"], "osx-arm64")

    assert "linux-64" in reason
    assert "osx-arm64" in reason
    # bioconda DOES ship macOS builds, so do not blame the channel here.
    assert "bioconda" not in reason


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Windows", "AMD64", "win-64"),
        ("Darwin", "arm64", "osx-arm64"),
        ("Darwin", "x86_64", "osx-64"),
        ("Linux", "x86_64", "linux-64"),
        ("Linux", "aarch64", "linux-aarch64"),
    ],
)
def test_host_subdir_matches_conda_naming(
    monkeypatch: pytest.MonkeyPatch, system: str, machine: str, expected: str
) -> None:
    import platform as real_platform

    monkeypatch.setattr(real_platform, "system", lambda: system)
    monkeypatch.setattr(real_platform, "machine", lambda: machine)

    assert m.host_conda_subdir() == expected


def test_platforms_are_read_from_the_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "pixi.toml"
    manifest.write_text(
        '[workspace]\nname = "x"\nplatforms = ["linux-64", "osx-arm64"]\n',
        encoding="utf-8",
    )

    assert m.manifest_platforms(manifest) == ["linux-64", "osx-arm64"]


def test_a_manifest_without_platforms_yields_nothing(tmp_path: Path) -> None:
    """No declaration means no claim to check, so the guard must not fire."""
    manifest = tmp_path / "pixi.toml"
    manifest.write_text('[workspace]\nname = "x"\n', encoding="utf-8")

    assert m.manifest_platforms(manifest) == []


def test_a_missing_manifest_does_not_raise(tmp_path: Path) -> None:
    assert m.manifest_platforms(tmp_path / "absent.toml") == []


def test_no_committed_lock_targets_windows() -> None:
    """Documents why the desktop app cannot run workflows natively on Windows.

    macOS support was added later, so this no longer asserts linux-only -- but
    win-64 can never appear, because bioconda publishes no Windows packages.
    """
    locks = Path(m.__file__).resolve().parents[1] / "environments" / "locks"
    manifests = sorted(locks.glob("*/pixi.toml"))
    assert manifests, "expected committed environment locks"

    for manifest in manifests:
        declared = m.manifest_platforms(manifest)
        assert declared[0] == "linux-64", manifest.parent.name
        assert "win-64" not in declared, manifest.parent.name
