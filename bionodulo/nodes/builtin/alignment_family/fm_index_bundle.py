"""Validated sibling-prefix bundles used by Bowtie2 and HISAT2."""

from __future__ import annotations

import errno
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IndexBundle:
    """One complete index prefix and the suffix family it uses."""

    prefix: Path
    suffixes: tuple[str, ...]


_LINK_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.ENOSYS}
for _errno_name in ("ENOTSUP", "EOPNOTSUPP"):
    _errno_value = getattr(errno, _errno_name, None)
    if _errno_value is not None:
        _LINK_FALLBACK_ERRNOS.add(_errno_value)


def path_value(value: Any) -> str | None:
    """Return a non-empty filesystem path, or ``None`` for invalid input."""
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


def read_paths(inputs: dict[str, Any]) -> list[str]:
    """Return one single-end read or an ordered pair from node inputs."""
    value = inputs.get("reads")
    if value is None:
        value = [item for item in (inputs.get("r1"), inputs.get("r2")) if item]
    if isinstance(value, (str, os.PathLike)):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []

    reads: list[str] = []
    for item in value:
        path = path_value(item)
        if path is None:
            return []
        reads.append(path)
    return reads


def index_members(prefix: Path, suffixes: tuple[str, ...]) -> tuple[Path, ...]:
    """Return every required sibling for an index prefix."""
    return tuple(Path(f"{prefix}{suffix}") for suffix in suffixes)


def _is_complete(prefix: Path, suffixes: tuple[str, ...]) -> bool:
    members = index_members(prefix, suffixes)
    return all(member.is_file() and member.stat().st_size > 0 for member in members)


def _recognized_members(directory: Path, suffix_families: tuple[tuple[str, ...], ...]) -> bool:
    suffixes = tuple(suffix for family in suffix_families for suffix in family)
    return any(item.is_file() and item.name.endswith(suffixes) for item in directory.iterdir())


def find_index_bundle(
    index_dir: str | os.PathLike[str],
    *,
    label: str,
    suffix_families: tuple[tuple[str, ...], ...],
) -> IndexBundle:
    """Resolve exactly one complete small or large index in a directory."""
    directory = Path(index_dir)
    if not directory.exists():
        raise FileNotFoundError(f"{label} index directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"{label} index input is not a directory: {directory}")

    candidates: list[IndexBundle] = []
    for suffixes in suffix_families:
        lead_suffix = suffixes[0]
        for item in sorted(directory.iterdir()):
            if not item.is_file() or not item.name.endswith(lead_suffix):
                continue
            prefix = Path(str(item)[: -len(lead_suffix)])
            if _is_complete(prefix, suffixes):
                candidates.append(IndexBundle(prefix=prefix, suffixes=suffixes))

    if not candidates:
        required = " or ".join(", ".join(f"*{suffix}" for suffix in family) for family in suffix_families)
        raise FileNotFoundError(f"{label} index directory {directory} has no complete sibling prefix ({required})")
    if len(candidates) != 1:
        names = ", ".join(
            f"{candidate.prefix.name} ({candidate.suffixes[0].rsplit('.', 1)[-1]})" for candidate in candidates
        )
        raise ValueError(f"{label} index directory {directory} contains multiple complete prefixes: {names}")
    return candidates[0]


def planned_or_complete_prefix(
    index_dir: str | os.PathLike[str],
    *,
    label: str,
    suffix_families: tuple[tuple[str, ...], ...],
    planned_name: str = "index",
) -> Path:
    """Resolve a real bundle, or its deterministic prefix during a graph dry-run."""
    directory = Path(index_dir)
    try:
        return find_index_bundle(
            directory,
            label=label,
            suffix_families=suffix_families,
        ).prefix
    except FileNotFoundError:
        if not directory.exists():
            return directory / planned_name
        if directory.is_dir() and not _recognized_members(directory, suffix_families):
            return directory / planned_name
        raise


def stage_file(source: Path, target: Path) -> None:
    """Hard-link a local input, copying only across unsupported filesystems."""
    target.parent.mkdir(parents=True, exist_ok=True)
    source_lexical = os.path.abspath(os.path.normpath(os.fspath(source)))
    target_lexical = os.path.abspath(os.path.normpath(os.fspath(target)))
    if source_lexical == target_lexical:
        return
    if not target.is_symlink() and target.exists() and os.path.samefile(source, target):
        return
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        os.link(source, target)
    except OSError as exc:
        if exc.errno not in _LINK_FALLBACK_ERRNOS:
            raise
        shutil.copy2(source, target)


def stage_bundle(bundle: IndexBundle, target_prefix: Path) -> None:
    """Stage all members of one validated bundle under a safe local prefix."""
    for source in index_members(bundle.prefix, bundle.suffixes):
        suffix = str(source)[len(str(bundle.prefix)) :]
        stage_file(source, Path(f"{target_prefix}{suffix}"))
