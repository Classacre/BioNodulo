"""Deterministic staging for command inputs with filename-discovered sidecars.

Several upstream tools accept only the primary path and discover indexes by
looking for a sibling filename.  Cloud uploads can materialize each declared
input in a different directory, so validating the lexical relationship is not
enough: the pair must be placed beside one another before the command runs.
"""

from __future__ import annotations

import errno
import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


_LINK_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.ENOSYS}
for _errno_name in ("ENOTSUP", "EOPNOTSUPP"):
    _errno_value = getattr(errno, _errno_name, None)
    if _errno_value is not None:
        _LINK_FALLBACK_ERRNOS.add(_errno_value)


def stage_file(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> Path:
    """Hard-link one input artifact, copying across unsupported filesystems.

    The replacement is assembled in the destination directory and atomically
    installed with ``os.replace``.  A failed cross-filesystem copy therefore
    cannot leave a truncated sidecar at the name that the tool will discover.
    """
    source_path = Path(source)
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    source_lexical = os.path.abspath(os.path.normpath(os.fspath(source_path)))
    target_lexical = os.path.abspath(os.path.normpath(os.fspath(target_path)))
    if source_lexical == target_lexical:
        return target_path
    if source_path.exists() and target_path.exists() and not target_path.is_symlink():
        try:
            if os.path.samefile(source_path, target_path):
                return target_path
        except OSError:
            # A concurrent removal/replace is handled by the atomic install
            # below; do not turn it into a false successful staging result.
            pass

    temporary_fd, temporary_name = tempfile.mkstemp(
        dir=target_path.parent,
        prefix=f".{target_path.name}.",
        suffix=".staging",
    )
    os.close(temporary_fd)
    temporary_path = Path(temporary_name)
    try:
        # mkstemp creates the placeholder, while os.link requires a missing
        # destination.  Remove only that private placeholder before linking.
        temporary_path.unlink()
        try:
            os.link(source_path, temporary_path)
        except OSError as exc:
            if exc.errno not in _LINK_FALLBACK_ERRNOS:
                raise
            shutil.copy2(source_path, temporary_path)
        os.replace(temporary_path, target_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return target_path


def _path_list(value: Any, *, split_commas: bool = False) -> list[str]:
    """Normalize scalar/list path values while preserving user ordering."""
    if value is None:
        return []
    if isinstance(value, (str, bytes, os.PathLike)):
        decoded = os.fsdecode(os.fspath(value))
        values: Iterable[Any] = decoded.split(",") if split_commas else (decoded,)
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        values = value
    else:
        return []
    return [os.fsdecode(os.fspath(item)).strip() for item in values if os.fsdecode(os.fspath(item)).strip()]


def _suffixes(path: Path) -> str:
    """Return compound suffixes needed for a stable canonical basename."""
    return "".join(path.suffixes)


def _canonical_name(path: Path, role: str) -> str:
    suffixes = _suffixes(path)
    return f"{role}{suffixes}" if suffixes else role


def stage_bam_pair(
    inputs: dict[str, Any],
    destination: Path,
    *,
    bam_key: str,
    index_key: str,
    role: str,
) -> None:
    """Stage one BAM/CRAM and its explicit index under a canonical role name."""
    bam_value = inputs.get(bam_key)
    index_value = inputs.get(index_key)
    if bam_value in (None, "") and index_value in (None, ""):
        return
    if bam_value in (None, "") or index_value in (None, ""):
        # Validation owns the user-facing error; do not hide malformed pairs.
        return

    bam_source = Path(os.fsdecode(os.fspath(bam_value)))
    index_source = Path(os.fsdecode(os.fspath(index_value)))
    # Structural/dry-run contexts commonly use symbolic paths.  Leave those
    # untouched; a real command still fails normally if its required artifact
    # was not materialized by the workflow input boundary.
    if not bam_source.is_file() or not index_source.is_file():
        return
    bam_target = destination / _canonical_name(bam_source, role)
    # Preserve the explicit index format (BAI/CSI/CRAI), but always use the
    # appended spelling that upstream sibling discovery checks first.
    index_suffix = index_source.suffix.lower() or ".bai"
    index_target = Path(f"{bam_target}{index_suffix}")
    stage_file(bam_source, bam_target)
    stage_file(index_source, index_target)
    inputs[bam_key] = str(bam_target)
    inputs[index_key] = str(index_target)


def stage_reference_bundle(
    inputs: dict[str, Any],
    destination: Path,
    *,
    reference_key: str = "reference",
    index_key: str = "reference_index",
    dictionary_key: str = "sequence_dictionary",
) -> None:
    """Stage FASTA, FAI, and optional extension-replaced ``.dict`` together."""
    reference_value = inputs.get(reference_key)
    index_value = inputs.get(index_key)
    if reference_value in (None, "") and index_value in (None, ""):
        return
    if reference_value in (None, "") or index_value in (None, ""):
        return

    reference_source = Path(os.fsdecode(os.fspath(reference_value)))
    index_source = Path(os.fsdecode(os.fspath(index_value)))
    if not reference_source.is_file() or not index_source.is_file():
        return
    dictionary_value = inputs.get(dictionary_key)
    dictionary_source: Path | None = None
    if dictionary_value not in (None, ""):
        dictionary_source = Path(os.fsdecode(os.fspath(dictionary_value)))
        # Preflight the complete bundle so a missing dictionary cannot leave
        # the FASTA and FAI staged while the declared dictionary remains at a
        # different (and unusable) path.
        if not dictionary_source.is_file():
            return
    reference_target = destination / _canonical_name(reference_source, "reference")
    index_target = Path(f"{reference_target}.fai")
    stage_file(reference_source, reference_target)
    stage_file(index_source, index_target)
    inputs[reference_key] = str(reference_target)
    inputs[index_key] = str(index_target)

    if dictionary_source is not None:
        dictionary_target = reference_target.with_suffix(".dict")
        stage_file(dictionary_source, dictionary_target)
        inputs[dictionary_key] = str(dictionary_target)


def stage_variant_pair(
    inputs: dict[str, Any],
    destination: Path,
    *,
    variant_key: str,
    index_key: str,
    role: str,
    split_commas: bool = False,
) -> None:
    """Stage one or more indexed VCF/BCF resources as sibling pairs."""
    variants = _path_list(inputs.get(variant_key), split_commas=split_commas)
    indexes = _path_list(inputs.get(index_key), split_commas=split_commas)
    if not variants and not indexes:
        return
    if len(variants) != len(indexes):
        return

    # Preflight every pair before creating any destination files.  This keeps
    # a malformed multi-resource input from leaving only its first resource
    # materialized after a later pair fails.
    sources = [(Path(variant), Path(index)) for variant, index in zip(variants, indexes, strict=True)]
    if any(not variant.is_file() or not index.is_file() for variant, index in sources):
        return

    staged_variants: list[str] = []
    staged_indexes: list[str] = []
    for ordinal, (variant_source, index_source) in enumerate(sources):
        item_role = role if len(variants) == 1 else f"{role}_{ordinal + 1}"
        variant_target = destination / _canonical_name(variant_source, item_role)
        index_target = Path(f"{variant_target}{index_source.suffix.lower() or '.tbi'}")
        stage_file(variant_source, variant_target)
        stage_file(index_source, index_target)
        staged_variants.append(str(variant_target))
        staged_indexes.append(str(index_target))

    inputs[variant_key] = staged_variants[0] if len(staged_variants) == 1 and not isinstance(inputs.get(variant_key), (list, tuple)) else staged_variants
    inputs[index_key] = staged_indexes[0] if len(staged_indexes) == 1 and not isinstance(inputs.get(index_key), (list, tuple)) else staged_indexes


def stage_variant_sidecars(
    inputs: dict[str, Any],
    outputs: list[Any],
    *,
    bam_pairs: tuple[tuple[str, str, str], ...] = (),
    variant_pairs: tuple[tuple[str, str, str, bool], ...] = (),
) -> None:
    """Stage all declared sidecar pairs for one focused node."""
    if not outputs:
        return
    destination = Path(outputs[0]).parent / "inputs"
    destination.mkdir(parents=True, exist_ok=True)
    stage_reference_bundle(inputs, destination)
    for bam_key, index_key, role in bam_pairs:
        stage_bam_pair(
            inputs,
            destination / "alignments",
            bam_key=bam_key,
            index_key=index_key,
            role=role,
        )
    for variant_key, index_key, role, split_commas in variant_pairs:
        stage_variant_pair(
            inputs,
            destination / "variants",
            variant_key=variant_key,
            index_key=index_key,
            role=role,
            split_commas=split_commas,
        )
