"""Guarantee every example-data path referenced by a template is fetchable.

Templates reference `examples/data/<category>/<file>` paths that the input node
materialises on demand from EXAMPLE_DATA_MANIFEST (download URL or run generator).
This test fails if a template references example data with no manifest entry, so
the "no committed example files; fetch/generate instead" contract can't silently
regress.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from bionodulo.manager.example_data import EXAMPLE_DATA_MANIFEST

ROOT = Path(__file__).resolve().parents[1]
_REF_RE = re.compile(r"examples/data/([A-Za-z0-9_./-]+)")


def _manifest_index() -> tuple[set[tuple[str, str]], set[str]]:
    by_cat_file = {(d.category, d.filename) for d in EXAMPLE_DATA_MANIFEST}
    categories = {d.category for d in EXAMPLE_DATA_MANIFEST}
    return by_cat_file, categories


def _template_refs() -> set[str]:
    refs: set[str] = set()
    for tmpl in (ROOT / "templates").glob("*.json"):
        for m in _REF_RE.finditer(tmpl.read_text(encoding="utf-8")):
            refs.add("examples/data/" + m.group(1).rstrip("/"))
    return refs


def test_every_template_example_path_is_in_manifest() -> None:
    by_cat_file, categories = _manifest_index()
    uncovered: list[str] = []
    for ref in sorted(_template_refs()):
        parts = ref.split("/")  # examples / data / <category> / [file...]
        category = parts[2]
        filename = parts[3] if len(parts) > 3 else None
        if filename is None:
            # category-level directory reference (e.g. single_cell)
            if category not in categories:
                uncovered.append(ref)
        elif (category, filename) not in by_cat_file:
            uncovered.append(ref)
    assert not uncovered, f"template example paths missing from manifest: {uncovered}"


def test_all_generators_produce_nonempty_output() -> None:
    tmp = Path(tempfile.mkdtemp())
    for spec in EXAMPLE_DATA_MANIFEST:
        if spec.generator is None:
            continue
        dest = tmp / spec.category / spec.filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        spec.generator(dest)
        assert dest.exists(), f"{spec.category}/{spec.filename} not created"
        if dest.is_dir():
            size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
        else:
            size = dest.stat().st_size
        assert size > 0, f"{spec.category}/{spec.filename} is empty"


def test_gzip_fastq_generators_are_valid_fastq() -> None:
    import gzip

    tmp = Path(tempfile.mkdtemp())
    for spec in EXAMPLE_DATA_MANIFEST:
        if spec.generator is None or not spec.filename.endswith(".fastq.gz"):
            continue
        dest = tmp / spec.filename
        spec.generator(dest)
        with gzip.open(dest, "rt", encoding="utf-8") as fh:
            lines = fh.readlines()
        assert lines and len(lines) % 4 == 0, f"{spec.filename} not 4-line FASTQ records"
        assert lines[0].startswith("@") and lines[2].startswith("+"), spec.filename


def test_crispr_sgrna_library_has_required_columns() -> None:
    tmp = Path(tempfile.mkdtemp()) / "lib.tsv"
    spec = next(d for d in EXAMPLE_DATA_MANIFEST if d.filename == "sgrna_library.tsv")
    spec.generator(tmp)
    header = tmp.read_text(encoding="utf-8").splitlines()[0].split("\t")
    assert header == ["sgRNA", "sequence", "gene"]


def test_no_example_data_files_are_committed() -> None:
    # The examples/data tree must stay out of git (fetched/generated at runtime).
    committed = list((ROOT / "examples" / "data").rglob("*")) if (ROOT / "examples" / "data").exists() else []
    committed_files = [p for p in committed if p.is_file()]
    assert not committed_files, f"example data files present on disk: {committed_files[:5]}"
