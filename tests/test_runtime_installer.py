"""pixi must install on Windows, which the shell-script approach never could.

The reported failure was "failed to install pixi ... HTTP Error 403: Forbidden"
on a Windows laptop. Three independent causes, all fixed by fetching the release
binary instead of running the POSIX install script.
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from bionodulo.manager import runtime_installer as ri


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Windows", "AMD64", "pixi-x86_64-pc-windows-msvc.zip"),
        ("Windows", "ARM64", "pixi-aarch64-pc-windows-msvc.zip"),
        ("Linux", "x86_64", "pixi-x86_64-unknown-linux-musl.tar.gz"),
        ("Linux", "aarch64", "pixi-aarch64-unknown-linux-musl.tar.gz"),
        ("Darwin", "arm64", "pixi-aarch64-apple-darwin.tar.gz"),
        ("Darwin", "x86_64", "pixi-x86_64-apple-darwin.tar.gz"),
    ],
)
def test_every_supported_platform_maps_to_a_real_asset(
    monkeypatch: pytest.MonkeyPatch, system: str, machine: str, expected: str
) -> None:
    """Windows reports AMD64/ARM64; the release names use x86_64/aarch64."""
    monkeypatch.setattr(ri.platform, "system", lambda: system)
    monkeypatch.setattr(ri.platform, "machine", lambda: machine)

    assert ri._pixi_asset_name() == expected


def test_an_unsupported_platform_is_reported_rather_than_guessed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ri.platform, "system", lambda: "Plan9")
    monkeypatch.setattr(ri.platform, "machine", lambda: "sparc")

    assert ri._pixi_asset_name() is None


def test_windows_gets_a_zip_and_everyone_else_a_tarball() -> None:
    """The extractor branches on suffix, so this pairing is load-bearing."""
    for (system, _machine), asset in ri._PIXI_ASSETS.items():
        if system == "Windows":
            assert asset.endswith(".zip")
        else:
            assert asset.endswith(".tar.gz")


def test_the_executable_is_pulled_out_of_a_zip(tmp_path: Path) -> None:
    archive = tmp_path / "pixi.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("pixi.exe", b"windows-binary")
        zf.writestr("README.md", b"noise")
    target = tmp_path / "bin" / "pixi.exe"
    target.parent.mkdir()

    ri._extract_pixi(archive, target)

    assert target.read_bytes() == b"windows-binary"


def test_the_executable_is_pulled_out_of_a_tarball(tmp_path: Path) -> None:
    archive = tmp_path / "pixi.tar.gz"
    payload = b"unix-binary"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo("pixi")
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))
    target = tmp_path / "bin" / "pixi"
    target.parent.mkdir()

    ri._extract_pixi(archive, target)

    assert target.read_bytes() == payload


def test_a_missing_executable_fails_loudly(tmp_path: Path) -> None:
    """Silently writing nothing would surface much later as "pixi not found"."""
    archive = tmp_path / "pixi.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo("something-else")
        info.size = 0
        tf.addfile(info, io.BytesIO(b""))
    target = tmp_path / "pixi"

    with pytest.raises(RuntimeError, match="not found inside"):
        ri._extract_pixi(archive, target)


def test_a_user_agent_is_set() -> None:
    """GitHub answers urllib's default User-Agent with 403 Forbidden."""
    assert ri._USER_AGENT
    assert "python-urllib" not in ri._USER_AGENT.lower()


def test_no_shell_is_invoked_anywhere_in_the_installer() -> None:
    """Stock Windows has no bash; the old installer shelled out to it.

    Comments are stripped first: the module explains the old approach, and
    matching that prose would make this pass or fail for the wrong reason.
    """
    code = "\n".join(
        line
        for line in Path(ri.__file__).read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )

    assert "install.sh" not in code
    assert '"bash"' not in code
    assert "pixi.sh/install" not in code
