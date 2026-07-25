"""Official templates must default to real, pinned, public input data.

Templates previously shipped synthetic fixtures under ``templates/data/smoke/``.
That broke in the cloud — the worker image never copies ``templates/`` — and it
taught users nothing about where real data comes from. Inputs now point at
upstream public files, which the input nodes fetch at run time (see
``bionodulo/nodes/builtin/input_family/adapter.py``: "templates ship URLs
directly in their node params and download on run").

The remaining local paths are genuinely synthetic artefacts with no upstream
counterpart. They are listed explicitly so the list cannot grow silently.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"

# Synthetic inputs with no public upstream equivalent. Additions need a
# deliberate decision, not a silent commit.
#
# The tabular and decoy entries were briefly pointed at real upstream files and
# had to be reverted: these inputs carry node-specific schemas that no public
# dataset happens to match — a `gene` column for the heatmap/DESeq2 chain (the
# nf-core counts matrix uses gene_id/gene_name and is TSV), and decoy-tagged
# accessions for Sage (a plain proteome has none). Sequence data has real
# upstream sources; these do not.
ALLOWED_LOCAL_INPUTS = {
    "templates/data/deseq2_gene_sets.json",
    "templates/data/smoke/counts.csv",
    "templates/data/smoke/heatmap_annotation.csv",
    "templates/data/smoke/heatmap_data.csv",
    "templates/data/smoke/sample_info.csv",
    "templates/data/smoke/sgrna_library.tsv",
    "templates/data/smoke/target_decoy.fasta",
}

# Sources that were tried and abandoned because they rot or are unreasonably
# large. Kept as a regression guard.
RETIRED_SOURCES = (
    "OpenGene/fastp/raw/master/testdata/R1.fq",
    "tseemann/shovill/raw/master/test/R1.fq",
    "SRR6357070_1.fastq.gz",
    "SRR6357071_1.fastq.gz",
)


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def _templates() -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(TEMPLATES.glob("*.json"))]


def _input_values() -> set[str]:
    return {
        value
        for template in _templates()
        for node in template["nodes"]
        if node["type"].startswith("input_")
        for value in _strings(node.get("params", {}))
    }


def test_no_unexpected_local_input_paths() -> None:
    """A local path in a template is invisible to the cloud worker."""
    local = {value for value in _input_values() if value.startswith("templates/data/")}
    assert local <= ALLOWED_LOCAL_INPUTS, (
        "template inputs reference local files the worker image does not ship: "
        f"{sorted(local - ALLOWED_LOCAL_INPUTS)}"
    )


def test_allowed_local_inputs_actually_exist() -> None:
    """Don't let the allow-list outlive the files it excuses."""
    for rel in sorted(ALLOWED_LOCAL_INPUTS):
        assert (ROOT / rel).is_file(), f"allow-listed input is missing: {rel}"


def test_remote_inputs_are_pinned_to_an_immutable_ref() -> None:
    """A branch URL can change under us; a commit SHA cannot."""
    unpinned: list[str] = []
    for value in sorted(_input_values()):
        if not value.startswith(("http://", "https://")):
            continue
        if "raw.githubusercontent.com" in value:
            # .../<org>/<repo>/<ref>/<path> — ref must be a 40-char commit SHA.
            match = re.search(r"raw\.githubusercontent\.com/[^/]+/[^/]+/([^/]+)/", value)
            if not match or not re.fullmatch(r"[0-9a-f]{40}", match.group(1)):
                unpinned.append(value)
    assert not unpinned, "GitHub raw inputs must pin a commit SHA:\n  " + "\n  ".join(unpinned)


def test_template_count_is_pinned() -> None:
    assert len(_templates()) == 22


def test_bundled_template_data_is_not_used_beyond_the_allow_list() -> None:
    """Only ``templates/data/`` is in scope here.

    Two other local conventions exist and are deliberately left alone:
      * ``external/…``  — BYOL vendor assets the user must supply (the Cello
        compiler jar, Dorado basecalling models). These are placeholders by
        design; the node fails with a clear "provide your own" error.
      * ``examples/data/…`` — example inputs resolved outside the template
        bundle.
    Neither is shipped in the repo, so neither is affected by moving the
    template fixtures to public URLs.
    """
    bundled = {v for v in _input_values() if v.startswith("templates/")}
    assert bundled <= ALLOWED_LOCAL_INPUTS


def test_retired_sources_are_not_reintroduced() -> None:
    serialized = "\n".join(json.dumps(template) for template in _templates())
    for retired in RETIRED_SOURCES:
        assert retired not in serialized, f"retired input source is back: {retired}"
