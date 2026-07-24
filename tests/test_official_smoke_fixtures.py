from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
SMOKE = TEMPLATES / "data" / "smoke"


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def test_official_template_smoke_defaults_are_local_small_and_well_formed() -> None:
    templates = [json.loads(path.read_text(encoding="utf-8")) for path in TEMPLATES.glob("*.json")]
    assert len(templates) == 22

    defaults = {
        value
        for template in templates
        for node in template["nodes"]
        if node["type"].startswith("input_")
        for value in _strings(node.get("params", {}))
        if value.startswith("templates/data/smoke/")
    }
    fixtures = {path.relative_to(ROOT).as_posix() for path in SMOKE.iterdir() if path.is_file()}
    assert defaults == fixtures
    size_limits = {
        # PGGB's documented 5 kb segment size requires real sequences longer
        # than the previous 56 bp synthetic records. This is the pinned
        # upstream HLA-DRB1 example from PGGB v0.7.4 (EOF-normalized).
        "templates/data/smoke/haplotypes.fasta": 200_000,
    }
    assert all(
        0 < (ROOT / path).stat().st_size <= size_limits.get(path, 4_096)
        for path in defaults
    )
    assert sum((ROOT / path).stat().st_size for path in defaults) <= 200_000

    serialized = "\n".join(json.dumps(template) for template in templates)
    for retired in (
        "OpenGene/fastp/raw/master/testdata/R1.fq",
        "tseemann/shovill/raw/master/test/R1.fq",
        "SRR6357070_1.fastq.gz",
        "SRR6357071_1.fastq.gz",
    ):
        assert retired not in serialized

    paired_records: list[list[tuple[str, str, str]]] = []
    for path in (SMOKE / "paired_R1.fastq", SMOKE / "paired_R2.fastq"):
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) % 4 == 0
        records = [(lines[i], lines[i + 1], lines[i + 3]) for i in range(0, len(lines), 4)]
        assert len(records) == 8
        assert all(header.startswith("@smoke_pair_") for header, _, _ in records)
        assert all(sequence and set(sequence) <= set("ACGTN") for _, sequence, _ in records)
        assert all(len(sequence) == len(quality) for _, sequence, quality in records)
        paired_records.append(records)
    assert [record[0].removesuffix("/1") for record in paired_records[0]] == [
        record[0].removesuffix("/2") for record in paired_records[1]
    ]

    haplotype_path = SMOKE / "haplotypes.fasta"
    haplotypes = haplotype_path.read_text(encoding="utf-8").splitlines()
    assert sum(line.startswith(">") for line in haplotypes) == 12
