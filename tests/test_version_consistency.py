"""Every declared version agrees.

The version is written in six places, in two spellings: npm's `0.1.0-alpha.7`
and PEP 440's `0.1.0a7`. Bumping them by hand drifted three releases running --
the desktop app shipped as alpha.7 while the editor's title bar still said
alpha.3 and the Python package said 0.1.0a3 -- because a release touched only
the files it needed and nothing checked the rest. A user reported the editor
showing a version that had been superseded twice.

`scripts/set_version.py` writes all five; this fails the build if they diverge.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import set_version  # noqa: E402


def test_every_declared_version_is_identical() -> None:
    versions = set_version.read_versions()

    assert len(versions) == 6, f"expected six declarations, found {sorted(versions)}"
    distinct = set(versions.values())
    assert len(distinct) == 1, (
        "version declarations disagree — run scripts/set_version.py:\n  "
        + "\n  ".join(f"{name}: {value}" for name, value in sorted(versions.items()))
    )


def test_the_python_package_reports_the_same_version() -> None:
    """The runtime value, not just the file it is read from.

    `bionodulo.__version__` reaches users through the HTTP User-Agent and the
    run attestation, so a stale value there misattributes real artefacts.
    """
    import bionodulo

    declared = set_version.read_versions()["pyproject.toml"]

    assert set_version.to_npm(bionodulo.__version__) == declared


@pytest.mark.parametrize(
    ("npm", "pep440"),
    [
        ("0.1.0-alpha.7", "0.1.0a7"),
        ("1.2.3-beta.10", "1.2.3b10"),
        ("2.0.0-rc.1", "2.0.0rc1"),
        ("1.0.0", "1.0.0"),
    ],
)
def test_the_two_spellings_convert_both_ways(npm: str, pep440: str) -> None:
    assert set_version.to_pep440(npm) == pep440
    assert set_version.to_npm(pep440) == npm


def test_an_unrecognised_version_is_left_alone() -> None:
    # Better to pass a value through untouched than to mangle it into something
    # that looks valid and is wrong.
    assert set_version.to_pep440("not-a-version") == "not-a-version"
    assert set_version.to_npm("not-a-version") == "not-a-version"


def test_the_editor_ships_the_declared_version() -> None:
    """The SPA's version is compiled in from web/package.json.

    This is the one a user actually sees, in the loading screen and the title
    bar, and it is the one that was reported stale.
    """
    import json

    declared = set_version.read_versions()["pyproject.toml"]
    web = json.loads((REPO / "web" / "package.json").read_text())["version"]

    assert web == declared
