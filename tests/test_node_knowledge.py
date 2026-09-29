"""Knowledge metadata stays descriptive and survives the real registry path."""

from __future__ import annotations

import json

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.knowledge import validate_knowledge
from bionodulo.nodes.registry import NodeRegistry


EVIDENCE = {
    "url": "https://example.org/manual", "checked_at": "2026-09-25",
    "note": "The manual describes the intended follow-up operation.",
}


class KnowledgeNode(BaseNode):
    NODE_ID = "knowledge_example"
    DISPLAY_NAME = "Knowledge example"
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("table",)
    KNOWLEDGE = {
        "schema_version": 1,
        "tool_id": "https://bio.tools/example",
        "topics": [{"uri": "http://edamontology.org/topic_0091", "label": "Bioinformatics"}],
        "operations": [{"uri": "http://edamontology.org/operation_2428", "label": "Validation"}],
        "relations": [{
            "target_node_id": "followup_node", "kind": "complements",
            "source_port": "table", "target_port": "table",
            "evidence": EVIDENCE,
        }],
        "citation_evidence": [{
            "identifier": "10.1234/example", "source_url": "https://doi.org/10.1234/example",
            "checked_at": "2026-09-25", "note": "Tool publication listed by the authors.",
        }],
        "reviewed_at": "2026-09-25", "introduced_at": "2026-09-24",
    }

    async def run(self, **kwargs: object) -> tuple[object, ...]:
        return ()


def test_knowledge_round_trips_through_node_metadata_and_registry_object_info() -> None:
    registry = NodeRegistry.create_isolated()
    registry.register(KnowledgeNode)
    direct = KnowledgeNode.metadata()
    listed = registry.object_info()[KnowledgeNode.NODE_ID]
    single = registry.object_info(KnowledgeNode.NODE_ID)

    expected = validate_knowledge(KnowledgeNode.KNOWLEDGE, node_id=KnowledgeNode.NODE_ID)
    assert direct["knowledge"] == listed["knowledge"] == single["knowledge"] == expected
    assert json.loads(json.dumps(listed))["knowledge"] == expected
    assert listed["name"] == KnowledgeNode.NODE_ID
    assert listed["output"] == ["TSV"]
    assert listed["knowledge"]["relations"][0]["source_port"] == "table"
    listed["knowledge"]["relations"][0]["evidence"]["note"] = "changed"
    assert KnowledgeNode.KNOWLEDGE["relations"][0]["evidence"]["note"] == EVIDENCE["note"]


def test_absent_knowledge_does_not_change_existing_node_metadata() -> None:
    class PlainNode(BaseNode):
        NODE_ID = "knowledge_plain"

        async def run(self, **kwargs: object) -> tuple[object, ...]:
            return ()

    registry = NodeRegistry.create_isolated()
    registry.register(PlainNode)
    assert "knowledge" not in PlainNode.metadata()
    assert "knowledge" not in registry.object_info(PlainNode.NODE_ID)


@pytest.mark.parametrize("patch,match", [
    ({"tool_id": "javascript:alert(1)"}, "HTTP"),
    ({"tool_id": "http://127.0.0.1/tool"}, "public DNS host"),
    ({"tool_id": "https://8.8.8.8/tool"}, "public DNS host"),
    ({"reviewed_at": "2026-02-30"}, "valid ISO date"),
    ({"relations": [{"target_node_id": "other", "kind": "compatible_with", "evidence": EVIDENCE}]}, "unknown"),
    ({"topics": [{"uri": "http://edamontology.org/operation_2428", "label": "Validation"}]}, "EDAM topic"),
    ({"operations": [{"uri": "http://edamontology.org/operation_2428", "label": "Validation"}] * 2}, "duplicate URI"),
    ({"relations": [{"target_node_id": "knowledge_example", "kind": "complements", "evidence": EVIDENCE}]}, "itself"),
])
def test_invalid_knowledge_is_rejected_at_registration(patch: dict[str, object], match: str) -> None:
    class InvalidNode(KnowledgeNode):
        KNOWLEDGE = {"schema_version": 1, **patch}

    with pytest.raises(ValueError, match=match):
        NodeRegistry.create_isolated().register(InvalidNode)


def test_duplicate_relation_and_citation_evidence_are_rejected() -> None:
    relation = {"target_node_id": "other", "kind": "complements", "evidence": EVIDENCE}
    citation = {"identifier": "doi:10.1234/example", "source_url": "https://doi.org/10.1234/example",
                "checked_at": "2026-09-25", "note": "Author page."}
    with pytest.raises(ValueError, match="duplicate relation"):
        validate_knowledge({"schema_version": 1, "relations": [relation, relation]})
    with pytest.raises(ValueError, match="duplicate entry"):
        validate_knowledge({"schema_version": 1, "citation_evidence": [citation, citation]})
