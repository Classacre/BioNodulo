"""Validation for tools that discover colocated reference sidecars."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _lexical_path(value: Any, *, key: str) -> Path | str:
    try:
        raw_path = os.fspath(value)
    except TypeError:
        return f"Input '{key}' must be a non-empty path-like value"
    decoded_path = os.fsdecode(raw_path)
    if not decoded_path.strip():
        return f"Input '{key}' must be a non-empty path-like value"
    return Path(os.path.abspath(os.path.normpath(decoded_path)))


def validate_colocated_reference_index(
    inputs: Mapping[str, Any],
    *,
    reference_key: str = "reference",
    index_key: str = "reference_index",
) -> bool | str:
    """Require the exact ``<reference>.fai`` path without filesystem access."""
    reference_path = _lexical_path(inputs.get(reference_key), key=reference_key)
    if isinstance(reference_path, str):
        return reference_path

    expected_index = Path(f"{reference_path}.fai")
    index_path = _lexical_path(inputs.get(index_key), key=index_key)
    if isinstance(index_path, str):
        return f"{index_path}; expected '{expected_index}' for input '{reference_key}'"
    if index_path != expected_index:
        return (
            f"Input '{index_key}' must be the exact colocated index for input "
            f"'{reference_key}'; expected '{expected_index}'"
        )
    return True


def validate_colocated_sequence_dictionary(
    inputs: Mapping[str, Any],
    *,
    reference_key: str = "reference",
    dictionary_key: str = "sequence_dictionary",
) -> bool | str:
    """Require GATK's extension-replaced ``<reference>.dict`` sibling."""
    reference_path = _lexical_path(inputs.get(reference_key), key=reference_key)
    if isinstance(reference_path, str):
        return reference_path
    if not reference_path.suffix:
        return f"Input '{reference_key}' must have a FASTA filename extension"

    expected_dictionary = reference_path.with_suffix(".dict")
    dictionary_path = _lexical_path(inputs.get(dictionary_key), key=dictionary_key)
    if isinstance(dictionary_path, str):
        return (
            f"{dictionary_path}; expected '{expected_dictionary}' for input "
            f"'{reference_key}'"
        )
    if dictionary_path != expected_dictionary:
        return (
            f"Input '{dictionary_key}' must be the exact colocated sequence "
            f"dictionary for input '{reference_key}'; expected "
            f"'{expected_dictionary}'"
        )
    return True
