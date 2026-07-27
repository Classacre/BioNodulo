"""Region/target contigs must name a sequence the workflow's own genome has.

This is a recurring failure class, not a one-off: a template's reference gets
swapped and a hardcoded `chr9:1-1000` or `NC_000913.3:1-50000` is left behind.
Nothing rejects it at submit time, so a spot VM boots, the pipeline runs for
minutes, and the region node dies -- after the credit is spent.

Contig names are asserted against the CONTIG WE EXPECT the pinned URL to serve,
recorded here from a real download. That keeps the check offline and fast while
still failing if either side drifts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# genome URL substring -> the contig names that FASTA actually contains.
# Verified by downloading each and reading its headers.
KNOWN_GENOME_CONTIGS = {
    "sarscov2/genome/genome.fasta": {"MT192765.1"},
    "zenodo.org/record/582600/files/wildtype.fna": {"Wildtype"},
}


def _templates() -> list[tuple[str, dict]]:
    return [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((ROOT / "templates").glob("*.json"))
    ]


def _genome_contigs(workflow: dict) -> set[str] | None:
    """Return the contig set of this workflow's reference, if we know it."""
    for node in workflow.get("nodes", []):
        params = node.get("params")
        if not isinstance(params, dict):
            continue
        reference = str(params.get("reference", ""))
        for marker, contigs in KNOWN_GENOME_CONTIGS.items():
            if marker in reference:
                return contigs
    return None


@pytest.mark.parametrize("name,workflow", _templates(), ids=lambda value: value if isinstance(value, str) else "")
def test_region_contigs_exist_in_the_referenced_genome(name: str, workflow: dict) -> None:
    contigs = _genome_contigs(workflow)
    if contigs is None:
        pytest.skip(f"{name}: reference genome not in the verified set")

    for node in workflow.get("nodes", []):
        params = node.get("params")
        if not isinstance(params, dict):
            continue
        for key in ("region", "target", "contig", "chromosome"):
            value = params.get(key)
            if not value:
                continue
            contig = str(value).split(":", 1)[0]
            assert contig in contigs, (
                f"{name}: node {node['id']} {key}={value!r} names contig {contig!r}, "
                f"but this workflow's genome contains {sorted(contigs)}. "
                "A reference was probably swapped without updating the region."
            )
