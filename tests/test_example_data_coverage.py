"""Guarantee every example-data path referenced by a template is fetchable.

Templates reference `examples/data/<category>/<file-or-dir>` paths that the input
node materialises on demand from EXAMPLE_DATA_MANIFEST (download URL — or, for
two spatial CSVs with no public source, a generator). This test fails if a
template references example data with no manifest coverage, and asserts the
"real URLs, not synthetic" contract: only the two spatial CSVs may be generators.
"""

from __future__ import annotations

import re
from pathlib import Path

from bionodulo.manager.example_data import EXAMPLE_DATA_MANIFEST

ROOT = Path(__file__).resolve().parents[1]
_REF_RE = re.compile(r"examples/data/([A-Za-z0-9_./-]+)")


def _template_refs() -> set[str]:
    refs: set[str] = set()
    for tmpl in (ROOT / "templates").glob("*.json"):
        for m in _REF_RE.finditer(tmpl.read_text(encoding="utf-8")):
            refs.add("examples/data/" + m.group(1).rstrip("/"))
    return refs


def test_every_template_example_path_is_in_manifest() -> None:
    by_cat_file = {(d.category, d.filename) for d in EXAMPLE_DATA_MANIFEST}
    categories = {d.category for d in EXAMPLE_DATA_MANIFEST}
    uncovered: list[str] = []
    for ref in sorted(_template_refs()):
        parts = ref.split("/")  # examples / data / <category> / [name...]
        category = parts[2]
        name = "/".join(parts[3:]) if len(parts) > 3 else None
        if name is None:
            if category not in categories:  # category-level directory ref
                uncovered.append(ref)
        elif (category, name) in by_cat_file:
            continue
        elif any(d.category == category and d.filename.startswith(name + "/") for d in EXAMPLE_DATA_MANIFEST):
            continue  # directory ref composed of nested entries (pod5, visium_outs, bismark_genome)
        else:
            uncovered.append(ref)
    assert not uncovered, f"template example paths missing from manifest: {uncovered}"


def test_manifest_is_all_real_urls_no_synthetic() -> None:
    # Every example-data entry must be a real public URL — zero synthetic generators.
    for d in EXAMPLE_DATA_MANIFEST:
        assert d.generator is None, f"{d.category}/{d.filename} uses a synthetic generator"
        assert d.url and d.url.startswith(("http://", "https://")), f"{d.category}/{d.filename} has no URL"


def test_no_example_data_files_are_committed() -> None:
    data_dir = ROOT / "examples" / "data"
    committed_files = [p for p in data_dir.rglob("*") if p.is_file()] if data_dir.exists() else []
    assert not committed_files, f"example data files present on disk: {committed_files[:5]}"
