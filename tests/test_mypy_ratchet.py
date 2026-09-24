"""The type-checking baseline requires a completed mypy scan."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts import mypy_ratchet


@pytest.mark.parametrize(
    ("status", "output"),
    [
        (1, "torch.pyi: error: Cannot decode file\nFound 1 error in 1 file (errors prevented further checking)\n"),
        (1, "Found 1 error in 1 file (checked 1 source file)\nerrors prevented further checking\n"),
        (2, "usage: mypy [options]\n"),
        (0, "Found 1 error in 1 file (checked 1555 source files)\n"),
    ],
)
def test_incomplete_mypy_scan_never_lowers_baseline(monkeypatch, status: int, output: str) -> None:
    monkeypatch.setattr(
        mypy_ratchet.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=status, stdout=output, stderr=""),
    )
    with pytest.raises(SystemExit, match="did not complete a full scan"):
        mypy_ratchet.run_mypy()


@pytest.mark.parametrize(
    ("status", "output", "expected"),
    [
        (1, "Found 530 errors in 182 files (checked 1555 source files)\n", 530),
        (0, "Success: no issues found in 1555 source files\n", 0),
    ],
)
def test_completed_mypy_scan_is_counted(monkeypatch, status: int, output: str, expected: int) -> None:
    monkeypatch.setattr(
        mypy_ratchet.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=status, stdout=output, stderr=""),
    )
    assert mypy_ratchet.run_mypy()[0] == expected


def test_mypy_language_level_matches_ci() -> None:
    assert mypy_ratchet.MYPY_ARGS[-2:] == ["--python-version", "3.11"]
