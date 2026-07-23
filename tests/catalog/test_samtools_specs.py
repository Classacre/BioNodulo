from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.catalog.tools.samtools import SPECS, collate, fixmate, flagstat, index, markdup, sort, view
from bionodulo.nodes.catalog.tools.samtools.artifacts import SAMTOOLS_ARTIFACT_REGISTRY
from bionodulo.nodes.contract.execution import ArgvPlan


MODULES = (view, collate, fixmate, sort, markdup, index, flagstat)


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
