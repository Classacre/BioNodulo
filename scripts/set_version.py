#!/usr/bin/env python
"""Set the product version everywhere it is declared.

The version lives in six places, in two spellings: npm's `0.1.0-alpha.7` and
PEP 440's `0.1.0a7`. Bumping them by hand has drifted three releases running --
the desktop app shipped as alpha.7 while the editor's title bar said alpha.3 and
the Python package said 0.1.0a3 -- because a release only ever touched the files
it needed and nothing checked the rest.

    ./.venv/bin/python scripts/set_version.py 0.1.0-alpha.7

`tests/test_version_consistency.py` fails if they diverge again.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: JSON files carrying an npm-style version under a top-level "version" key.
JSON_TARGETS = (
    Path("web/package.json"),
    Path("desktop/package.json"),
    Path("desktop/src-tauri/tauri.conf.json"),
)

CARGO = Path("desktop/src-tauri/Cargo.toml")
PYPROJECT = Path("pyproject.toml")
#: The runtime value. Reaches users through the HTTP User-Agent and the run
#: attestation, so a stale one misattributes real artefacts.
INIT = Path("bionodulo/__init__.py")

_NPM_PRERELEASE = re.compile(r"^(\d+\.\d+\.\d+)-(alpha|beta|rc)\.(\d+)$")
_PEP440_PRERELEASE = re.compile(r"^(\d+\.\d+\.\d+)(a|b|rc)(\d+)$")

_TO_PEP440 = {"alpha": "a", "beta": "b", "rc": "rc"}
_TO_NPM = {v: k for k, v in _TO_PEP440.items()}


def to_pep440(npm_version: str) -> str:
    """`0.1.0-alpha.7` -> `0.1.0a7`; a plain `1.2.3` passes through."""
    match = _NPM_PRERELEASE.match(npm_version)
    if not match:
        return npm_version
    base, kind, number = match.groups()
    return f"{base}{_TO_PEP440[kind]}{number}"


def to_npm(pep440_version: str) -> str:
    """`0.1.0a7` -> `0.1.0-alpha.7`; a plain `1.2.3` passes through."""
    match = _PEP440_PRERELEASE.match(pep440_version)
    if not match:
        return pep440_version
    base, kind, number = match.groups()
    return f"{base}-{_TO_NPM[kind]}.{number}"


def read_versions() -> dict[str, str]:
    """Every declared version, normalised to the npm spelling."""
    found: dict[str, str] = {}
    for rel in JSON_TARGETS:
        found[str(rel)] = json.loads((REPO / rel).read_text())["version"]

    cargo = re.search(r'^version = "([^"]+)"', (REPO / CARGO).read_text(), re.M)
    if cargo:
        found[str(CARGO)] = cargo.group(1)

    pyproject = re.search(r'^version = "([^"]+)"', (REPO / PYPROJECT).read_text(), re.M)
    if pyproject:
        found[str(PYPROJECT)] = to_npm(pyproject.group(1))

    init = re.search(r'^__version__ = "([^"]+)"', (REPO / INIT).read_text(), re.M)
    if init:
        found[str(INIT)] = to_npm(init.group(1))
    return found


def write_version(npm_version: str) -> list[str]:
    """Apply the version everywhere; return the files actually changed."""
    changed: list[str] = []

    for rel in JSON_TARGETS:
        path = REPO / rel
        text = path.read_text()
        # Rewritten textually rather than via json.dump, so key order,
        # indentation and trailing newline survive untouched.
        updated, count = re.subn(
            r'("version"\s*:\s*)"[^"]+"', rf'\1"{npm_version}"', text, count=1
        )
        if count and updated != text:
            path.write_text(updated)
            changed.append(str(rel))

    path = REPO / CARGO
    text = path.read_text()
    updated, count = re.subn(
        r'^version = "[^"]+"', f'version = "{npm_version}"', text, count=1, flags=re.M
    )
    if count and updated != text:
        path.write_text(updated)
        changed.append(str(CARGO))

    path = REPO / PYPROJECT
    text = path.read_text()
    updated, count = re.subn(
        r'^version = "[^"]+"', f'version = "{to_pep440(npm_version)}"', text, count=1, flags=re.M
    )
    if count and updated != text:
        path.write_text(updated)
        changed.append(str(PYPROJECT))

    path = REPO / INIT
    text = path.read_text()
    updated, count = re.subn(
        r'^__version__ = "[^"]+"',
        f'__version__ = "{to_pep440(npm_version)}"',
        text,
        count=1,
        flags=re.M,
    )
    if count and updated != text:
        path.write_text(updated)
        changed.append(str(INIT))

    return changed


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        current = read_versions()
        print("Current versions:")
        for name, value in current.items():
            print(f"  {name:38s} {value}")
        print(f"\nUsage: {Path(__file__).name} <version>   e.g. 0.1.0-alpha.8")
        return 1 if len(set(current.values())) != 1 else 0

    version = argv[1]
    if not re.match(r"^\d+\.\d+\.\d+(-(alpha|beta|rc)\.\d+)?$", version):
        print(f"Not an npm-style version: {version!r}", file=sys.stderr)
        return 2

    for name in write_version(version):
        print(f"updated {name}")
    print(f"\nAll versions now {version} ({to_pep440(version)} for Python).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
