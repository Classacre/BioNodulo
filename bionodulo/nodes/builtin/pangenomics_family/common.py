"""Shared staging and input-normalization helpers for pangenomics nodes."""

from __future__ import annotations

import errno
import os
import re
import shutil
from pathlib import Path
from typing import Any


_LINK_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.ENOSYS}
for _errno_name in ("ENOTSUP", "EOPNOTSUPP"):
    _errno_value = getattr(errno, _errno_name, None)
    if _errno_value is not None:
        _LINK_FALLBACK_ERRNOS.add(_errno_value)


def _stage_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        os.link(source, target)
    except OSError as exc:
        if exc.errno not in _LINK_FALLBACK_ERRNOS:
            raise
        shutil.copy2(source, target)


def _split_path_list(value: Any) -> list[str]:
    if isinstance(value, list | tuple):
        return [os.fsdecode(os.fspath(item)) for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[\n,]+", str(value or "")) if item.strip()]


def _path_value(value: Any) -> str:
    try:
        result = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return result if result.strip() else ""


def _positive_int(value: Any, name: str, default: int) -> int | str:
    value = default if value in (None, "") else value
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{name} must be an integer"
    if value < 1:
        return f"{name} must be at least 1"
    return value


def _non_negative_int(value: Any, name: str, default: int = 0) -> int | str:
    value = default if value in (None, "") else value
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{name} must be an integer"
    if value < 0:
        return f"{name} must be non-negative"
    return value


def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub(r"\.(gz|bz2|xz|zip)$", "", stem)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-")
    return stem or fallback
