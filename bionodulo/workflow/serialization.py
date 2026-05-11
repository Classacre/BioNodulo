"""Workflow serialization - save and load workflows as JSON.

Provides functions to persist workflows to disk and restore them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bionodulo.workflow.schema import Workflow


def save_workflow(
    workflow: Workflow | dict[str, Any],
    path: Path,
    indent: int = 2,
) -> None:
    """Save a workflow to a JSON file.

    Args:
        workflow: Workflow object or dict to serialize.
        path: Destination file path (.json).
        indent: JSON indentation level.
    """
    if isinstance(workflow, Workflow):
        data = workflow.model_dump(by_alias=True)
    else:
        data = workflow

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=indent, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def load_workflow(path: Path) -> Workflow:
    """Load a workflow from a JSON file.

    Args:
        path: Path to the workflow JSON file.

    Returns:
        Parsed Workflow model.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the JSON is invalid or cannot be parsed.
    """
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")

    content = path.read_text(encoding="utf-8")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in workflow file: {exc}") from exc

    return Workflow.model_validate(data)


def workflow_to_json(workflow: Workflow, indent: int = 2) -> str:
    """Serialize a workflow to a JSON string."""
    return json.dumps(
        workflow.model_dump(by_alias=True),
        indent=indent,
        ensure_ascii=False,
        default=str,
    )


def workflow_from_json(json_str: str) -> Workflow:
    """Deserialize a workflow from a JSON string."""
    data = json.loads(json_str)
    return Workflow.model_validate(data)
