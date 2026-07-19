"""Compact ownership and evidence checks for the wrapped variant/assembly wave."""

from __future__ import annotations

from bionodulo.nodes.builtin.wrapped_variant_assembly_family import evidence
from bionodulo.nodes.builtin.wrapped_variant_assembly_family.lofreq import LoFreqAlnQualNode
from bionodulo.nodes.registry import NodeRegistry


def test_wrapped_variant_assembly_ids_have_one_focused_owner_and_pinned_evidence() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    expected = set(evidence.NODE_TO_TOOL)
    assert len(expected) == 56

    for node_id in expected:
        node_class = registry.get(node_id)
        assert node_class.__module__.startswith(
            "bionodulo.nodes.builtin.wrapped_variant_assembly_family."
        )
        authority = evidence.TOOL_EVIDENCE[evidence.NODE_TO_TOOL[node_id]]
        assert node_class.VERSION == authority.version
        assert node_class.SOURCE_URL == authority.source_url
        assert node_class.AUDIT_STATUS == "contract-checked-no-binary-execution"
        assert authority.commit or authority.source_sha256 or authority.container_digest


def test_lofreq_alnqual_uses_documented_standalone_flags_and_stdout_capture() -> None:
    inputs = {
        "reads": "reads.bam",
        "reference": "reference.fa",
        "extended_baq": False,
        "recompute_all": True,
    }
    assert LoFreqAlnQualNode.render_command(inputs) == [
        "lofreq",
        "alnqual",
        "-b",
        "-e",
        "-r",
        "reads.bam",
        "reference.fa",
    ]
    assert "" not in LoFreqAlnQualNode.render_command(inputs)
    assert LoFreqAlnQualNode.SHELL is False
    assert LoFreqAlnQualNode.STDOUT_OUTPUT_INDEX == 0
