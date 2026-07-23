from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.catalog.tools.samtools import SPECS, collate, fixmate, flagstat, index, markdup, sort, view
from bionodulo.nodes.catalog.tools.samtools.artifacts import SAMTOOLS_ARTIFACT_REGISTRY
from bionodulo.nodes.contract.execution import ArgvPlan
from bionodulo.nodes.contract.evidence import (
    verify_documentation_proof_content,
    verify_evidence_claim_content,
)


MODULES = (view, collate, fixmate, sort, markdup, index, flagstat)
SOURCE_FILES = {
    view: ("samtools-view.1", "sam_view.c"),
    collate: ("samtools-collate.1", "bamshuf.c"),
    fixmate: ("samtools-fixmate.1", "bam_mate.c"),
    sort: ("samtools-sort.1", "bam_sort.c"),
    markdup: ("samtools-markdup.1", "bam_markdup.c"),
    index: ("samtools-index.1", "bam_index.c"),
    flagstat: ("samtools-flagstat.1", "bam_stat.c"),
}


def test_first_wave_has_one_typed_spec_per_legacy_node() -> None:
    assert tuple(spec.identity.machine_id for spec in SPECS) == (
        "samtools_collate",
        "samtools_fixmate",
        "samtools_flagstat",
        "samtools_index",
        "samtools_markdup",
        "samtools_sort",
        "samtools_view",
    )
    assert all(module.SPEC.identity.machine_id == module.LEGACY_NODE.NODE_ID for module in MODULES)
    assert all(module.SPEC.runtime_binding is not None for module in MODULES)


def test_samtools_contracts_are_deterministic_and_source_pinned() -> None:
    first = {module.SPEC.identity.machine_id: module.SPEC.contract_digest() for module in MODULES}
    second = {module.SPEC.identity.machine_id: module.SPEC.contract_digest() for module in MODULES}
    assert first == second
    for module in MODULES:
        spec = module.SPEC
        assert spec.identity.tool_id == "samtools"
        assert spec.identity.tool_version == "1.23.1"
        assert spec.evidence is not None
        assert spec.evidence.tool_version == "1.23.1"
        assert spec.evidence.sources[0].url is not None
        assert "htslib.org/doc/samtools-" in spec.evidence.sources[0].url
        assert spec.evidence.sources[1].commit == "6efb9b6da35224cf804921dedecf9fb8f411365d"


def test_evidence_digests_verify_against_pinned_checkout_bytes() -> None:
    root = Path("/tmp/bionodulo-samtools-1.23.1")
    if not root.exists():
        pytest.skip("pinned Samtools checkout is unavailable on this host")
    for module in MODULES:
        doc_name, source_name = SOURCE_FILES[module]
        evidence = module.SPEC.evidence
        assert evidence is not None
        manual = evidence.sources[0]
        source_bytes = (root / "doc" / doc_name).read_bytes()
        assert manual.documentation_proof is not None
        verify_documentation_proof_content(
            manual.documentation_proof,
            source_content=source_bytes,
        )
        claim = evidence.claims[0]
        verify_evidence_claim_content(
            claim,
            source_content=source_bytes,
            expected_contract_pointer="/execution_factory",
            contract_value=module.SPEC.execution_factory,
        )
        assert (root / source_name).read_bytes()


def test_samtools_artifact_registry_requires_explicit_alignment_union() -> None:
    assert SAMTOOLS_ARTIFACT_REGISTRY.is_type_compatible("alignment.sam", "alignment.union")
    assert SAMTOOLS_ARTIFACT_REGISTRY.is_type_compatible("alignment.bam", "alignment.union")
    assert not SAMTOOLS_ARTIFACT_REGISTRY.is_type_compatible("alignment.bai", "alignment.union")


@pytest.mark.parametrize(
    ("module", "inputs", "expected_prefix"),
    (
        (view, {"alignment": "input.sam"}, ("samtools", "view")),
        (collate, {"bam": "input.bam"}, ("samtools", "collate")),
        (fixmate, {"bam": "input.bam"}, ("samtools", "fixmate")),
        (sort, {"alignment": "input.sam"}, ("samtools", "sort")),
        (markdup, {"bam": "input.bam"}, ("samtools", "markdup")),
        (index, {"bam": "input.bam"}, ("samtools", "index")),
        (flagstat, {"bam": "input.bam"}, ("samtools", "flagstat")),
    ),
)
def test_build_plan_bridges_to_legacy_argv(module, inputs, expected_prefix, tmp_path: Path) -> None:
    plan = module.build_plan(inputs, tmp_path)
    assert isinstance(plan, ArgvPlan)
    assert plan.token_array()[:2] == expected_prefix
    assert plan.resources.allowed_platforms[0].value == "linux/amd64"


def test_markdup_plan_preserves_source_option_order(tmp_path: Path) -> None:
    plan = markdup.build_plan(
        {
            "bam": "input.bam",
            "threads": 8,
            "remove_duplicates": True,
            "mark_supplementary": True,
            "optical_distance": 100,
            "read_coords": "([0-9]+)_([0-9]+)",
            "clear_existing": True,
        },
        tmp_path,
    )
    assert plan.token_array()[0:10] == (
        "samtools",
        "markdup",
        "-@",
        "8",
        "-r",
        "-S",
        "-d",
        "100",
        "--read-coords",
        "([0-9]+)_([0-9]+)",
    )
