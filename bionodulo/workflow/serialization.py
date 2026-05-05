from __future__ import annotations

import json
from pathlib import Path

from bionodulo.workflow.schema import Workflow


def load_workflow(path: Path) -> Workflow:
    return Workflow.model_validate_json(path.read_text(encoding="utf-8"))


def save_workflow(workflow: Workflow, path: Path) -> None:
    path.write_text(json.dumps(workflow.model_dump(by_alias=True), indent=2), encoding="utf-8")
