from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _template_catalog() -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for path in sorted((ROOT / "templates").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        catalog.append({
            "filename": path.name,
            "name": data["name"],
            "category": data.get("category"),
        })
    return catalog


def test_readme_template_catalog_matches_template_directory() -> None:
    catalog = _template_catalog()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    template_count = len(catalog)

    assert f"**{template_count} Pre-built Templates**" in readme
    assert f"# {template_count} pre-built workflow templates" in readme

    for template in catalog:
        assert template["name"] in readme

    for category in {"Long Read", "Proteomics", "Epigenomics"}:
        assert category in readme


def test_spec_template_tree_matches_template_directory() -> None:
    catalog = _template_catalog()
    spec = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    for template in catalog:
        assert template["filename"] in spec

    for category in {"Long Read", "Proteomics", "Epigenomics"}:
        assert category in spec
