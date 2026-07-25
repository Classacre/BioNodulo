"""Deterministic sibling staging for annotation tools."""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path


_LINK_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.ENOSYS}
for _errno_name in ("ENOTSUP", "EOPNOTSUPP"):
    _errno_value = getattr(errno, _errno_name, None)
    if _errno_value is not None:
        _LINK_FALLBACK_ERRNOS.add(_errno_value)


def stage_file(source: str | os.PathLike[str], destination: Path) -> Path:
    """Hard-link one input when possible, otherwise copy it byte-for-byte."""
    source_path = Path(os.fsdecode(os.fspath(source)))
    destination.parent.mkdir(parents=True, exist_ok=True)

    source_lexical = os.path.abspath(os.path.normpath(os.fspath(source_path)))
    destination_lexical = os.path.abspath(os.path.normpath(os.fspath(destination)))
    if source_lexical == destination_lexical:
        return destination
    if destination.exists() and os.path.samefile(source_path, destination):
        return destination
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    try:
        os.link(source_path, destination)
    except OSError as exc:
        if exc.errno not in _LINK_FALLBACK_ERRNOS:
            raise
        shutil.copy2(source_path, destination)
    return destination


def stage_named_bundle(
    inputs: dict[str, object],
    *,
    destination_dir: Path,
    names: dict[str, str],
) -> None:
    """Stage path inputs under exact sibling names and rewrite the input mapping."""
    for key, filename in names.items():
        staged = stage_file(os.fspath(inputs[key]), destination_dir / filename)
        inputs[key] = str(staged)
