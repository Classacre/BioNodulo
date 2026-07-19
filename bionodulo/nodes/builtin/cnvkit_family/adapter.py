"""Shared source-pinned CNVkit contracts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


CNVKIT_GIT_URL = "https://github.com/etal/cnvkit.git"
CNVKIT_GIT_COMMIT = "dd834b0b5b482f174d1dcb7c35b358087309c6b3"
CNVKIT_CITATION_DOI = "10.1371/journal.pcbi.1004873"


def output_path(inputs: dict[str, Any], filename: str) -> str:
    output_dir = inputs.get("output", inputs.get("output_dir", "."))
    return str(Path(str(output_dir)) / filename)


def plan_output(node_id: str, output_dir: str | Path, filename: str) -> list[Path]:
    node_dir = Path(output_dir) / node_id
    node_dir.mkdir(parents=True, exist_ok=True)
    return [node_dir / filename]


def optional_positive_int(inputs: dict[str, Any], field: str) -> bool | str:
    value = inputs.get(field)
    if value is None or str(value).strip() == "":
        return True
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return f"{field} must be an integer"
    if parsed < 1:
        return f"{field} must be at least 1"
    return True


class CNVkitCommandNode(CommandNode):
    """Common metadata for CNVkit 0.9.12 operations."""

    REQUIRED_CONDA_PACKAGES = ["cnvkit"]
    REQUIRED_EXECUTABLES = ["cnvkit.py"]
    REQUIRES_EXTERNAL_TOOLS = True
    CATEGORY = "variant"
    VERSION = "0.9.12"
    GIT_URL = CNVKIT_GIT_URL
    GIT_COMMIT = CNVKIT_GIT_COMMIT
    PACKAGE_AUTHORITY = "Bioconda cnvkit 0.9.12"
    CITATION_DOIS = [CNVKIT_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{CNVKIT_CITATION_DOI}"]
    CITATION_TEXT = (
        "CNVkit: Genome-Wide Copy Number Detection and Visualization from Targeted DNA Sequencing."
    )
