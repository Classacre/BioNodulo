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


def test_documented_template_catalog_matches_template_directory() -> None:
    catalog = _template_catalog()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "templates.md").read_text(encoding="utf-8")
    template_count = len(catalog)

    assert "docs/templates.md" in readme
    assert f"{template_count} bundled workflow templates" in guide

    for template in catalog:
        assert f'[{template["name"]}](../templates/{template["filename"]})' in guide

    for category in {"Long Read", "Proteomics", "Epigenomics"}:
        assert category in guide
