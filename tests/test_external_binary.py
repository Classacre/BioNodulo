"""Vendor-only binaries must actually be provisioned, not just declared.

Dorado declared ENVIRONMENT["provisioning"] == "external_worker_binary" long
before anything acted on it, so every ONT run died as `exit code 127` -- an
error that names neither the tool nor the reason.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from bionodulo.execution import external_binary


class _Vendor:
    REQUIRED_EXECUTABLES = ["toolx"]
    ENVIRONMENT = {
        "provisioning": "external_worker_binary",
        "source": "https://vendor.example/toolx-1.2.3-linux-x64.tar.gz",
        "version": "1.2.3",
        "platform": "linux-64",
    }


class _Conda:
    REQUIRED_EXECUTABLES = ["samtools"]
    ENVIRONMENT = {"type": "pixi", "name": "aligners"}


def _make_tarball(destination: Path, *, executable_name: str = "toolx") -> None:
    """Build a vendor-shaped tarball: versioned root, bin/<exe> inside."""
    staging = destination.parent / "src" / "toolx-1.2.3-linux-x64" / "bin"
    staging.mkdir(parents=True, exist_ok=True)
    binary = staging / executable_name
    binary.write_text("#!/bin/sh\necho toolx\n", encoding="utf-8")
    binary.chmod(0o755)
    with tarfile.open(destination, "w:gz") as handle:
        handle.add(staging.parent, arcname="toolx-1.2.3-linux-x64")


@pytest.fixture
def _isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "extbin"
    monkeypatch.setenv("EXTERNAL_BINARY_DIR", str(root))
    monkeypatch.delenv("REFERENCE_CACHE_BUCKET", raising=False)
    # conftest sets this suite-wide so no test can start a 4 GB download; these
    # tests provision against a stubbed `_download`, so they opt back in.
    monkeypatch.delenv("BIONODULO_EXTERNAL_BINARY_OFFLINE", raising=False)
    return root


def test_a_conda_node_is_left_alone(_isolated_root: Path) -> None:
    assert external_binary.spec_for(_Conda) is None
    assert external_binary.provision(_Conda, "samtools") is None


def test_the_binary_is_unpacked_and_its_directory_returned(
    tmp_path: Path, _isolated_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball = tmp_path / "toolx.tar.gz"
    _make_tarball(tarball)

    calls: list[str] = []

    def _fake_download(url: str, destination: Path) -> None:
        calls.append(url)
        destination.write_bytes(tarball.read_bytes())

    monkeypatch.setattr(external_binary, "_download", _fake_download)

    bin_dir = external_binary.provision(_Vendor, "toolx")

    assert bin_dir is not None
    assert (bin_dir / "toolx").is_file()
    assert calls == [_Vendor.ENVIRONMENT["source"]]


def test_a_second_call_reuses_the_download(
    tmp_path: Path, _isolated_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 4 GB vendor tarball must not be re-fetched per node or per run."""
    tarball = tmp_path / "toolx.tar.gz"
    _make_tarball(tarball)
    calls: list[str] = []

    def _fake_download(url: str, destination: Path) -> None:
        calls.append(url)
        destination.write_bytes(tarball.read_bytes())

    monkeypatch.setattr(external_binary, "_download", _fake_download)

    first = external_binary.provision(_Vendor, "toolx")
    second = external_binary.provision(_Vendor, "toolx")

    assert first == second
    assert len(calls) == 1


def test_a_tarball_without_the_executable_fails_loudly(
    tmp_path: Path, _isolated_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Better an explicit error here than the tool's own exit 127 later."""
    tarball = tmp_path / "wrong.tar.gz"
    _make_tarball(tarball, executable_name="somethingelse")

    monkeypatch.setattr(
        external_binary,
        "_download",
        lambda url, destination: destination.write_bytes(tarball.read_bytes()),
    )

    with pytest.raises(RuntimeError, match="was not found"):
        external_binary.provision(_Vendor, "toolx")


def test_partial_extraction_is_not_left_behind(
    tmp_path: Path, _isolated_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball = tmp_path / "wrong.tar.gz"
    _make_tarball(tarball, executable_name="somethingelse")
    monkeypatch.setattr(
        external_binary,
        "_download",
        lambda url, destination: destination.write_bytes(tarball.read_bytes()),
    )

    with pytest.raises(RuntimeError):
        external_binary.provision(_Vendor, "toolx")

    identity = external_binary.cache_id(external_binary.spec_for(_Vendor))
    assert not (_isolated_root / f"{identity}.partial").exists()


def test_offline_mode_leaves_path_untouched(
    _isolated_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard the suite relies on: never download, never raise."""
    monkeypatch.setenv("BIONODULO_EXTERNAL_BINARY_OFFLINE", "1")

    def _must_not_run(url: str, destination: Path) -> None:  # pragma: no cover
        raise AssertionError("offline mode must not download")

    monkeypatch.setattr(external_binary, "_download", _must_not_run)

    assert external_binary.provision(_Vendor, "toolx") is None


def test_an_executable_already_on_path_is_used_as_is(
    tmp_path: Path, _isolated_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worker image may bake the binary in; do not re-download 4 GB."""
    bin_dir = tmp_path / "prebaked"
    bin_dir.mkdir()
    binary = bin_dir / "toolx"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    def _must_not_run(url: str, destination: Path) -> None:  # pragma: no cover
        raise AssertionError("an on-PATH binary must not be re-downloaded")

    monkeypatch.setattr(external_binary, "_download", _must_not_run)

    assert external_binary.provision(_Vendor, "toolx") == bin_dir


def test_every_vendor_binary_node_routes_its_env_through_the_helper() -> None:
    """A node with its own `run()` bypasses CommandNode's provisioning.

    That is exactly what kept Dorado at exit 127 after provisioning was added:
    `CommandNode.run` gained the hook, but dorado_basecaller overrides `run()`
    and passed `env=self.__class__.ENV_VARS` straight through.
    """
    import inspect

    from bionodulo.nodes.registry import NodeRegistry

    registry = NodeRegistry()
    registry.load_builtin_nodes()

    offenders: list[str] = []
    for node_id, node_class in registry._nodes.items():
        if external_binary.spec_for(node_class) is None:
            continue
        run = node_class.__dict__.get("run")
        if run is None:
            continue  # inherits CommandNode.run, which is already wired
        source = inspect.getsource(run)
        if "env_with_binary" not in source:
            offenders.append(node_id)

    assert not offenders, (
        "these nodes need a vendor binary and override run() without calling "
        "env_with_binary, so the binary will be absent: " + ", ".join(sorted(offenders))
    )


def test_dorado_declares_a_provisionable_spec() -> None:
    """The real node this module exists for."""
    from bionodulo.nodes.builtin.long_read_family.dorado_basecaller import (
        DoradoBasecallerNode,
    )

    spec = external_binary.spec_for(DoradoBasecallerNode)
    assert spec is not None
    assert spec["source"].endswith("-linux-x64.tar.gz")
    assert spec["version"] == DoradoBasecallerNode.VERSION
    assert DoradoBasecallerNode.REQUIRED_EXECUTABLES == ["dorado"]
