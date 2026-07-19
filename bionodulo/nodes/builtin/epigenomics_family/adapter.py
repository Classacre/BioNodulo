"""Shared helpers for evidence-pinned epigenomics command nodes."""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .evidence import NODE_EVIDENCE


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


def safe_output_stem(value: Any, default: str) -> str:
    """Create a deterministic filename stem from a user-facing label."""
    stem = "_".join(str(value or "").strip().split())
    stem = "".join(char if char.isalnum() or char in "._-" else "_" for char in stem)
    return stem.strip("._-") or default


def split_values(value: Any, *, commas: bool = True) -> list[str]:
    """Normalize list-like UI values without shell parsing."""
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple)) else [value]
    result: list[str] = []
    for item in values:
        text = str(item).replace("\n", ",")
        if commas:
            text = text.replace(",", " ")
        result.extend(part for part in text.split() if part)
    return result


def split_path_list(value: Any) -> list[str]:
    """Split comma/newline-delimited paths while preserving spaces inside paths."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace("\n", ",").split(",") if part.strip()]


def stage_file(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
    """Hard-link one explicit artifact, copying across unsupported filesystems."""
    source_path = Path(source)
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    source_lexical = os.path.abspath(os.path.normpath(os.fspath(source_path)))
    target_lexical = os.path.abspath(os.path.normpath(os.fspath(target_path)))
    if source_lexical == target_lexical:
        return
    if (
        source_path.exists()
        and target_path.exists()
        and not target_path.is_symlink()
        and os.path.samefile(source_path, target_path)
    ):
        return
    if target_path.exists() or target_path.is_symlink():
        target_path.unlink()
    try:
        os.link(source_path, target_path)
    except OSError as exc:
        if exc.errno not in _LINK_FALLBACK_ERRNOS:
            raise
        shutil.copy2(source_path, target_path)


class EpigenomicsCommandNode(CommandNode):
    """Attach one exact upstream evidence record to every focused owner."""

    CATEGORY = "epigenomics"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = "Input validation or a non-zero external command fails the node."

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        node_id = cls.__dict__.get("NODE_ID", "")
        if not node_id:
            return
        evidence = NODE_EVIDENCE[node_id]
        cls.VERSION = evidence.version
        cls.GIT_URL = evidence.git_url
        cls.GIT_COMMIT = evidence.git_commit
        cls.SOURCE_REF = evidence.source_ref
        cls.SOURCE_PATHS = evidence.source_paths
        cls.SOURCE_URLS = evidence.source_urls
        cls.SOURCE_URL = evidence.source_urls[0]
        cls.DOCUMENTATION_URL = evidence.documentation_url
        cls.PACKAGE_CONSTRAINTS = evidence.package_constraints
        cls.PACKAGE_CONSTRAINT = "; ".join(evidence.package_constraints)


class SparseOutputEpigenomicsNode(EpigenomicsCommandNode):
    """Return only artifacts actually produced by an input-selected mode."""

    @classmethod
    def MAP_PLANNED_OUTPUTS(
        cls,
        inputs: dict[str, Any],
        planned_paths: list[Path],
    ) -> dict[str, Path]:
        raise NotImplementedError

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        original_inputs = dict(kwargs)
        planned = await super().run(**kwargs)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS(
            original_inputs,
            [Path(path) for path in planned],
        )
        return {"outputs": {name: str(path) for name, path in mapped.items()}}
